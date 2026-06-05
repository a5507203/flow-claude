#!/usr/bin/env python3
"""Standalone CostPar parallelizability scheduler.

No external dependencies — all scheduler logic is self-contained.

Usage:
    python run_scheduler.py --tasks-json '<json>' [--layer-convention-tokens '{"L0":3000,"L1":5000}']
    python run_scheduler.py --tasks-file plan.json [...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Strategy(Enum):
    SERIAL = "serial"
    STAGED_PARALLEL = "staged_parallel"
    FULL_PARALLEL = "full_parallel"


@dataclass
class TaskNode:
    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    enables: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    estimated_output_tokens: int = 0
    strategy: Strategy = Strategy.FULL_PARALLEL


@dataclass
class GroupDecision:
    group_id: str
    task_ids: List[str]
    T_serial_tokens: int
    T_parallel_tokens: int
    plan_cost_tokens: int
    max_task_tokens: int
    ratio: float
    strategy: Strategy
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "task_ids": self.task_ids,
            "T_serial_tokens": self.T_serial_tokens,
            "T_parallel_tokens": self.T_parallel_tokens,
            "plan_cost_tokens": self.plan_cost_tokens,
            "max_task_tokens": self.max_task_tokens,
            "ratio": self.ratio,
            "strategy": self.strategy.value,
            "reasoning": self.reasoning,
        }


@dataclass
class ExecutionWave:
    wave_index: int
    task_ids: List[str]
    strategy: Strategy
    conventions_prompt: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"wave_index": self.wave_index, "task_ids": self.task_ids, "strategy": self.strategy.value}
        if self.conventions_prompt:
            d["conventions_prompt"] = self.conventions_prompt
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_time_to_seconds(time_str: str) -> float:
    if not time_str:
        return 0.0
    s = time_str.strip().lower()
    m = re.match(r'([\d.]+)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?)', s)
    if not m:
        try:
            return float(s) * 60
        except ValueError:
            return 480.0
    val = float(m.group(1))
    unit = m.group(2)
    if unit.startswith('s'):
        return val
    elif unit.startswith('m'):
        return val * 60
    else:
        return val * 3600


def _jaccard(a: set, b: set) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _tokenize(text: str) -> List[str]:
    _STOP = {
        'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'is', 'it', 'be', 'as', 'that',
        'this', 'are', 'was', 'will', 'must', 'should', 'can', 'do',
        'each', 'all', 'any', 'its', 'not', 'but', 'if', 'no', 'so',
    }
    words = re.findall(r'[a-z0-9_]+', text.lower())
    return [w for w in words if w not in _STOP and len(w) > 1]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class ParallelizabilityScheduler:
    """Token-cost inequality scheduler (v7).

    Per dependency layer:
        T_serial   = sum(estimated_output_tokens)
        T_parallel = C_align + max(estimated_output_tokens)
        If T_serial / T_parallel > PARALLEL_MARGIN → PARALLEL, else SERIAL
    """

    PARALLEL_MARGIN = 1.9
    TOKENS_PER_SECOND = 17
    CONVENTION_PLANNING_TOKENS_DEFAULT = 3000
    SERIAL_THRESHOLD_TOKENS = 200

    def __init__(self, max_parallel: int = 6):
        self.max_parallel = max_parallel
        self._cached_layer_groups: Dict[str, List[List[str]]] = {}

    def build_dag(self, tasks: List[Dict]) -> Dict[str, TaskNode]:
        dag: Dict[str, TaskNode] = {}
        for t in tasks:
            tid = t.get("id", "")
            if not tid:
                continue
            depends = t.get("depends_on", [])
            estimated_output_tokens = int(t.get("estimated_output_tokens", 0) or 0)
            if not estimated_output_tokens:
                time_s = _parse_time_to_seconds(t.get("estimated_time", ""))
                estimated_output_tokens = int(time_s * self.TOKENS_PER_SECOND)
            if not estimated_output_tokens:
                desc_words = len(t.get("description", "").split())
                estimated_output_tokens = max(desc_words * 30, 500)

            dag[tid] = TaskNode(
                id=tid,
                description=t.get("description", ""),
                depends_on=depends or [],
                files=t.get("files", []) or [],
                estimated_output_tokens=estimated_output_tokens,
            )

        for node in dag.values():
            for dep_id in node.depends_on:
                if dep_id in dag and node.id not in dag[dep_id].enables:
                    dag[dep_id].enables.append(node.id)

        return dag

    def _topological_layers(self, dag: Dict[str, TaskNode]) -> List[List[str]]:
        in_degree: Dict[str, int] = {tid: 0 for tid in dag}
        for node in dag.values():
            for dep in node.depends_on:
                if dep in in_degree:
                    in_degree[node.id] += 1

        layers: List[List[str]] = []
        remaining = set(dag.keys())

        while remaining:
            layer = [tid for tid in remaining if in_degree.get(tid, 0) == 0]
            if not layer:
                layer = list(remaining)
            layers.append(sorted(layer))
            remaining -= set(layer)
            for tid in layer:
                for enabled in dag[tid].enables:
                    if enabled in in_degree:
                        in_degree[enabled] -= 1

        return layers

    def decide_strategies(
        self, dag: Dict[str, TaskNode],
        convention_planning_tokens: int = 0,
        layer_convention_tokens: Dict[str, int] = None,
    ) -> List[GroupDecision]:
        default_plan_cost = convention_planning_tokens or self.CONVENTION_PLANNING_TOKENS_DEFAULT
        _layer_tokens = layer_convention_tokens or {}
        layers = self._topological_layers(dag)
        self._cached_layer_groups = {}
        decisions: List[GroupDecision] = []
        group_idx = 0

        for layer_idx, layer in enumerate(layers):
            layer_key = ','.join(sorted(layer))
            plan_cost = _layer_tokens.get(f"L{layer_idx}", default_plan_cost)

            big = [tid for tid in layer if dag[tid].estimated_output_tokens >= self.SERIAL_THRESHOLD_TOKENS]
            small = [tid for tid in layer if dag[tid].estimated_output_tokens < self.SERIAL_THRESHOLD_TOKENS]
            groups = []

            if small:
                for tid in small:
                    dag[tid].strategy = Strategy.SERIAL
                small_total = sum(dag[tid].estimated_output_tokens for tid in small)
                decisions.append(GroupDecision(
                    group_id=f"g{group_idx}", task_ids=small,
                    T_serial_tokens=small_total, T_parallel_tokens=small_total,
                    plan_cost_tokens=0, max_task_tokens=max(dag[tid].estimated_output_tokens for tid in small),
                    ratio=1.0, strategy=Strategy.SERIAL,
                    reasoning=f"All tasks below serial threshold ({self.SERIAL_THRESHOLD_TOKENS})",
                ))
                groups.append(small)
                group_idx += 1

            if not big:
                self._cached_layer_groups[layer_key] = groups
                continue

            if len(big) == 1:
                dag[big[0]].strategy = Strategy.SERIAL
                tok = dag[big[0]].estimated_output_tokens
                decisions.append(GroupDecision(
                    group_id=f"g{group_idx}", task_ids=big,
                    T_serial_tokens=tok, T_parallel_tokens=tok,
                    plan_cost_tokens=0, max_task_tokens=tok,
                    ratio=1.0, strategy=Strategy.SERIAL,
                    reasoning="Single task — write directly",
                ))
                groups.append(big)
                group_idx += 1
                self._cached_layer_groups[layer_key] = groups
                continue

            tokens = [dag[tid].estimated_output_tokens for tid in big]
            T_serial = sum(tokens)
            max_t = max(tokens)
            T_parallel = plan_cost + max_t
            ratio = T_serial / T_parallel if T_parallel > 0 else float('inf')
            ratio = round(ratio, 3)

            if ratio > self.PARALLEL_MARGIN:
                strategy = Strategy.STAGED_PARALLEL
                reasoning = f"T_serial ({T_serial}) / T_parallel ({T_parallel}) = {ratio}x > margin {self.PARALLEL_MARGIN}x → PARALLEL"
            else:
                strategy = Strategy.SERIAL
                reasoning = f"T_serial ({T_serial}) / T_parallel ({T_parallel}) = {ratio}x <= margin {self.PARALLEL_MARGIN}x → SERIAL"

            for tid in big:
                dag[tid].strategy = strategy

            decisions.append(GroupDecision(
                group_id=f"g{group_idx}", task_ids=big,
                T_serial_tokens=T_serial, T_parallel_tokens=T_parallel,
                plan_cost_tokens=plan_cost, max_task_tokens=max_t,
                ratio=ratio, strategy=strategy, reasoning=reasoning,
            ))
            groups.append(big)
            group_idx += 1
            self._cached_layer_groups[layer_key] = groups

        return decisions

    def _build_conventions_prompt(self, group: List[str], dag: Dict[str, TaskNode]) -> str:
        task_descs = '\n'.join(f"- {dag[tid].description}" for tid in group)
        risk_hints = []
        all_exts = []
        for tid in group:
            for f in dag[tid].files:
                if '.' in f:
                    all_exts.append(f.rsplit('.', 1)[-1])
        if all_exts and len(set(all_exts)) == 1:
            risk_hints.append(
                f"All {len(group)} tasks produce .{list(set(all_exts))[0]} files — "
                f"notation, formatting, and style choices will diverge without explicit conventions"
            )
        descs = [dag[tid].description for tid in group]
        desc_tokens = [set(_tokenize(d)) for d in descs]
        if len(desc_tokens) >= 2:
            sims = []
            for i in range(len(desc_tokens)):
                for j in range(i + 1, len(desc_tokens)):
                    sims.append(_jaccard(desc_tokens[i], desc_tokens[j]))
            if sims and sum(sims) / len(sims) > 0.3:
                risk_hints.append(
                    f"Tasks have high description similarity (avg Jaccard={sum(sims)/len(sims):.2f}) "
                    f"— they produce similar content types with ambiguous style choices"
                )
        if not risk_hints:
            risk_hints.append("Multiple independent workers producing related outputs")
        risk_block = '\n'.join(f"  - {h}" for h in risk_hints)

        return (
            f"BEFORE launching any worker in this wave, you MUST write "
            f"CONVENTIONS.md at the repository root.\n\n"
            f"Tasks in this wave:\n{task_descs}\n\n\n"
            f"The scheduler detected HIGH HIDDEN CONSENSUS RISK because:\n"
            f"{risk_block}\n\n"
            f"You MUST write CONVENTIONS.md covering ALL ambiguous decisions "
            f"that independent workers might resolve differently. For each "
            f"convention, make ONE concrete choice and commit to it. Be "
            f"EXHAUSTIVE — cover notation, formatting, terminology, style, "
            f"structure, naming, and any domain-specific decisions.\n\n"
            f"Every worker must read CONVENTIONS.md as a precondition."
        )

    def generate_waves(self, dag: Dict[str, TaskNode]) -> List[ExecutionWave]:
        layers = self._topological_layers(dag)
        waves: List[ExecutionWave] = []
        wave_idx = 0

        for layer in layers:
            layer_key = ','.join(sorted(layer))
            groups = self._cached_layer_groups.get(layer_key)
            if groups is None:
                groups = [[tid] for tid in layer]

            parallel_tasks: List[str] = []
            serial_tasks: List[str] = []
            conventions_prompts: List[str] = []

            for group in groups:
                strategy = dag[group[0]].strategy
                if strategy == Strategy.SERIAL:
                    serial_tasks.extend(group)
                elif strategy == Strategy.STAGED_PARALLEL:
                    parallel_tasks.extend(group)
                    conventions_prompts.append(self._build_conventions_prompt(group, dag))
                else:
                    parallel_tasks.extend(group)

            if parallel_tasks:
                combined_prompt = '\n\n---\n\n'.join(conventions_prompts) if conventions_prompts else None
                merged_strategy = Strategy.STAGED_PARALLEL if conventions_prompts else Strategy.FULL_PARALLEL
                waves.append(ExecutionWave(
                    wave_index=wave_idx, task_ids=parallel_tasks,
                    strategy=merged_strategy, conventions_prompt=combined_prompt,
                ))
                wave_idx += 1

            for tid in serial_tasks:
                waves.append(ExecutionWave(wave_index=wave_idx, task_ids=[tid], strategy=Strategy.SERIAL))
                wave_idx += 1

        return waves

    def create_schedule(
        self, plan_tasks: List[Dict],
        convention_planning_tokens: int = 0,
        layer_convention_tokens: Dict[str, int] = None,
    ) -> Tuple[List[ExecutionWave], List[Dict]]:
        dag = self.build_dag(plan_tasks)
        if not dag:
            return [], []
        decisions = self.decide_strategies(dag, convention_planning_tokens, layer_convention_tokens)
        waves = self.generate_waves(dag)
        return waves, [d.to_dict() for d in decisions]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run CostPar parallelizability scheduler on a task list")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tasks-json", type=str, help="Task list as JSON string")
    group.add_argument("--tasks-file", type=str, help="Path to JSON file with task list")

    parser.add_argument("--layer-convention-tokens", type=str, default=None,
                        help='Per-layer alignment cost as JSON, e.g. \'{"L0":2000,"L1":5000}\'')
    parser.add_argument("--convention-tokens", type=int, default=0,
                        help="Fallback alignment cost for layers without per-layer estimate")
    parser.add_argument("--max-parallel", type=int, default=6, help="Max concurrent workers")
    parser.add_argument("--margin", type=float, default=None, help="Override safety margin alpha (default: 1.9)")
    parser.add_argument("--threshold", type=int, default=None, help="Override SERIAL_THRESHOLD_TOKENS (default: 200)")
    parser.add_argument("--compact", action="store_true", help="Compact output (no pretty-print)")

    args = parser.parse_args()

    if args.tasks_json:
        tasks = json.loads(args.tasks_json)
    else:
        with open(args.tasks_file) as f:
            tasks = json.load(f)

    layer_convention_tokens = None
    if args.layer_convention_tokens:
        layer_convention_tokens = json.loads(args.layer_convention_tokens)

    if args.margin is not None:
        ParallelizabilityScheduler.PARALLEL_MARGIN = args.margin
    if args.threshold is not None:
        ParallelizabilityScheduler.SERIAL_THRESHOLD_TOKENS = args.threshold

    scheduler = ParallelizabilityScheduler(max_parallel=args.max_parallel)
    waves, group_decisions = scheduler.create_schedule(
        tasks,
        convention_planning_tokens=args.convention_tokens,
        layer_convention_tokens=layer_convention_tokens,
    )

    schedule = []
    for w in waves:
        entry = {"wave": w.wave_index, "task_ids": w.task_ids, "strategy": w.strategy.value}
        if w.conventions_prompt:
            entry["conventions_prompt"] = w.conventions_prompt
        schedule.append(entry)

    result = {
        "schedule": schedule,
        "decisions": [d for d in group_decisions],
        "n_waves": len(waves),
        "params": {
            "alpha": ParallelizabilityScheduler.PARALLEL_MARGIN,
            "serial_threshold": ParallelizabilityScheduler.SERIAL_THRESHOLD_TOKENS,
            "max_parallel": args.max_parallel,
            "layer_convention_tokens": layer_convention_tokens,
        },
    }

    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
