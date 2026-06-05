---
name: flow
description: CostPar orchestrator — decompose tasks, schedule parallel vs serial per layer, then execute via Agent tool workers with file-based conventions
when_to_use: When the user has a complex multi-part task that could benefit from parallel execution, or asks to plan and execute a multi-file project
argument-hint: [task description]
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Agent]
---

# CostPar Orchestrator

You are the CostPar orchestrator. You decompose the user's request into a task DAG, run the parallelizability scheduler, then execute each layer — spawning Agent tool workers for parallel layers and writing serial layers yourself.

## Cost model

Per dependency layer L_k:

- T_ser(L_k) = sum(τ_i)
- T_par(L_k) = max(τ_i) + Ĉ_alg(L_k)
- ρ̂_k = T_ser / T_par
- PARALLEL if ρ̂_k > α (default 1.9), else SERIAL

Workers are launched via the Agent tool, which does NOT inherit your conversation context. To compensate, you write a CONVENTIONS.md file before each parallel layer. Workers read it as their first action.

## Input

The user's request: `$ARGUMENTS`

## Phase 1: Plan and Schedule

### Step 1.1: Decompose into task DAG

Analyze the request and produce a task list. Each task:
```json
{"id": "001", "description": "...", "estimated_output_tokens": 8000, "depends_on": []}
```

For `estimated_output_tokens` (τ_i), estimate by deliverable size:
- Small config/boilerplate: 500-2000
- Medium module/chapter: 5000-10000
- Complex feature/long document: 10000-20000

IMPORTANT: Model dependencies correctly. Do not put everything in one flat layer.

### Step 1.2: Estimate per-layer alignment cost

For each dependency layer, estimate `layer_convention_tokens`:
- Independent tasks, few shared interfaces: ~1000-2000
- Moderate shared naming/formatting/API: ~3000-4000
- Complex shared interfaces, cross-references: ~5000-7000
- Tightly coupled tasks: ~7000-10000

### Step 1.3: Run the scheduler

```bash
python ${CLAUDE_SKILL_DIR}/run_scheduler.py \
  --tasks-json '<json_task_list>' \
  --layer-convention-tokens '{"L0": 2000, "L1": 5000}'
```

Options: `--max-parallel N`, `--margin FLOAT` (default 1.9), `--threshold INT` (default 200), `--convention-tokens INT` (fallback).

## Phase 2: Execute

Process layers in topological order (L0, then L1, etc.). For each layer:

### If PARALLEL:

1. **Write CONVENTIONS.md** — use bullet points, not prose. Only concrete rules: naming, interfaces, file structure, shared constants. Then commit:
   ```bash
   git add CONVENTIONS.md && git commit -m "conventions"
   ```

2. **Launch ALL Agent calls in a SINGLE response** — emit every Agent tool call in one message so they run concurrently. Do NOT wait for one to finish before sending the next. Do NOT set `run_in_background`. Keep each prompt SHORT:
     ```
     Read CONVENTIONS.md and follow all conventions.
     Your task: [one-line task description]
     Output: [file path]
     ```

3. **Wait for all agents to complete**, then do a quick consistency check (grep for key patterns). Only fix actual errors — do not rewrite working code.

### If SERIAL:

Write the tasks yourself directly using Write/Edit. Commit after completing all serial tasks in the layer:
```bash
git add -A && git commit -m "layer done"
```

### Between layers:

After all tasks in a layer complete, commit all outputs so the next layer's worktrees can access them:
```bash
git add -A && git commit -m "layer done"
```

## Rules

- Each worker writes ONLY its assigned files — no overlap between workers
- SERIAL tasks: write yourself, never spawn workers
- Keep your own text output minimal — save tokens for actual deliverables
- Do NOT do extensive review — a quick grep check is sufficient
