#!/usr/bin/env python3
"""CLI wrapper for CostPar parallelizability scheduler.

Usage:
    python run_scheduler.py --tasks-json '<json>' [--layer-convention-tokens '{"L0":3000,"L1":5000}']
    python run_scheduler.py --tasks-file plan.json [...]

Input JSON format (list of task dicts):
    [
        {"id": "001", "description": "...", "estimated_output_tokens": 8000, "depends_on": []},
        {"id": "002", "description": "...", "estimated_output_tokens": 3000, "depends_on": ["001"]},
        ...
    ]
"""

import argparse
import json
import sys
import os

# Add flow-claude to path: try relative first, then known absolute
_candidates = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "flow-claude"),
    os.path.expanduser("~/paper_projects/NIPS 2026/agent_projects/flow-claude"),
]
for _p in _candidates:
    _ap = os.path.abspath(_p)
    if os.path.isdir(os.path.join(_ap, "flow_claude")):
        sys.path.insert(0, _ap)
        break

from flow_claude.scheduler import ParallelizabilityScheduler


def main():
    parser = argparse.ArgumentParser(description="Run CostPar parallelizability scheduler on a task list")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tasks-json", type=str, help="Task list as JSON string")
    group.add_argument("--tasks-file", type=str, help="Path to JSON file with task list")

    parser.add_argument("--layer-convention-tokens", type=str, default=None,
                        help='Per-layer alignment cost as JSON, e.g. \'{"L0":2000,"L1":5000}\'')
    parser.add_argument("--convention-tokens", type=int, default=0,
                        help="Fallback alignment cost for layers without per-layer estimate")
    parser.add_argument("--max-parallel", type=int, default=6, help="Max concurrent workers (default: 6)")
    parser.add_argument("--margin", type=float, default=None, help="Override safety margin alpha (default: 1.9)")
    parser.add_argument("--threshold", type=int, default=None, help="Override SERIAL_THRESHOLD_TOKENS (default: 200)")
    parser.add_argument("--compact", action="store_true", help="Compact output (no pretty-print)")

    args = parser.parse_args()

    # Parse tasks
    if args.tasks_json:
        tasks = json.loads(args.tasks_json)
    else:
        with open(args.tasks_file) as f:
            tasks = json.load(f)

    # Parse layer convention tokens
    layer_convention_tokens = None
    if args.layer_convention_tokens:
        layer_convention_tokens = json.loads(args.layer_convention_tokens)

    # Override class constants if requested
    if args.margin is not None:
        ParallelizabilityScheduler.PARALLEL_MARGIN = args.margin
    if args.threshold is not None:
        ParallelizabilityScheduler.SERIAL_THRESHOLD_TOKENS = args.threshold
    else:
        ParallelizabilityScheduler.SERIAL_THRESHOLD_TOKENS = 200

    # Run scheduler
    scheduler = ParallelizabilityScheduler(
        max_parallel=args.max_parallel,
        scoring_mode="v7",
    )
    waves, group_decisions = scheduler.create_schedule(
        tasks,
        convention_planning_tokens=args.convention_tokens,
        layer_convention_tokens=layer_convention_tokens,
    )

    # Build output
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
