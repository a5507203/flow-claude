# /flow — CostPar Orchestrator Skill

**CostPar** (Cost-aware Parallelizability scheduler) is a Claude Code skill that automatically decides whether to parallelize multi-agent task execution. The core insight: parallel execution isn't always faster — it introduces alignment overhead (inconsistent naming, interfaces, formatting) and re-exploration costs. CostPar uses a token-cost inequality to determine, per dependency layer, whether the parallel speedup outweighs these costs.

## Install

```bash
git clone https://github.com/a5507203/flow-claude.git ~/.claude/skills/flow
```

Or for a single project:
```bash
git clone https://github.com/a5507203/flow-claude.git .claude/skills/flow
```

## Usage

```
/flow <task description>
```

Claude will decompose the request into a task DAG, run the scheduler to decide parallel vs serial per dependency layer, then execute — spawning Agent tool workers for parallel layers and writing serial layers directly.

## How the scheduler works

For each dependency layer L_k, the scheduler computes a cost ratio:

```
ρ̂_k = T_ser(L_k) / T_par(L_k)

where:
  T_ser = Σ τ_i                    (sum of per-task output tokens)
  T_par = max(τ_i) + Ĉ_alg(L_k)   (critical path + alignment cost)
```

If ρ̂_k > α (default 1.9), the layer runs in **parallel**; otherwise **serial**.

The scheduler is a deterministic Python function (`run_scheduler.py`) — no LLM calls, runs in <100ms.

## Execution model

Workers run via the Agent tool with `isolation: "worktree"`. Before launching parallel workers:

1. The orchestrator writes `CONVENTIONS.md` and commits it (`git add && git commit`) so worktrees can access it.
2. Each worker reads `CONVENTIONS.md` as its first action, then writes its assigned file(s).
3. Between layers, all outputs are committed so the next layer's worktrees can access prior outputs.

## Deviation from the paper: C_exp ≠ 0

The cost model assumes re-exploration cost C_exp ≈ 0, justified by **context forking**: workers inherit the orchestrator's full conversation state via Claude Agent SDK session fork.

This skill cannot use context forking because:

- After June 15, 2026, Claude Agent SDK and `claude -p` no longer consume subscription credits.
- To keep the skill usable on subscription, all execution must happen within the Claude Code interactive session.
- The only way to spawn parallel workers in an interactive session is the **Agent tool**, which starts each worker from scratch — no context inheritance.

### How we compensate

Instead of context forking, we use **file-based convention passing** via git:

1. The orchestrator writes `CONVENTIONS.md` and commits it to git.
2. Agent tool workers run in `isolation: "worktree"` — they check out the committed state, so `CONVENTIONS.md` is available without searching.
3. Each worker reads `CONVENTIONS.md` once (~1s overhead per worker).

The scheduler formula is unchanged — the Ĉ_alg estimates account for the convention writing and worker parsing overhead.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition — orchestration instructions for Claude |
| `run_scheduler.py` | CLI wrapper for the scheduler, called via Bash |
| `README.md` | This file |

## Standalone scheduler usage

```bash
python3 .claude/skills/flow/run_scheduler.py \
  --tasks-json '[{"id":"001","description":"...","estimated_output_tokens":8000,"depends_on":[]}]' \
  --layer-convention-tokens '{"L0": 2000, "L1": 5000}'

# Options
--layer-convention-tokens JSON   # per-layer Ĉ_alg(L_k)
--convention-tokens INT          # fallback for layers not in the dict
--max-parallel N                 # max concurrent workers
--margin FLOAT                   # α, default 1.9
--threshold INT                  # small-task serial threshold, default 200
--compact                        # single-line JSON output
```

## Benchmark results

Evaluated on 9 benchmarks spanning code generation, document authoring, and structured planning. Throughput measured as deliverable words per second (excluding intermediate artifacts). The CC baseline is vanilla Claude Code without the `/flow` skill or any additional orchestration.

### Opus 4.6

| Benchmark | Type | Wall time | Words | Words/s | CC baseline | Speedup |
|-----------|------|-----------|-------|---------|-------------|---------|
| ArcadeBox | Code/JS | 4m 46s | 17,261 | 60.4 | 17.5 | 3.5x |
| LinAlgBook | MD | 2m 37s | 6,697 | 42.7 | 22.6 | 1.9x |
| CloudDocs | MD | 7m 8s | 18,970 | 44.3 | 29.6 | 1.5x |
| MathRef | MD | 8m 17s | 23,927 | 48.1 | 26.7 | 1.8x |
| CompressKit | Code/Python | 7m 16s | 6,419 | 14.7 | 3.7 | 4.0x |
| ShopFlow | Code/Flask | 10m 44s | 12,630 | 19.6 | 11.0 | 1.8x |
| PixelCraft | Code/Pygame | 9m 57s | 10,795 | 18.1 | 5.0 | 3.6x |
| SlideKit | HTML | 14m 54s | 32,678 | 36.6 | 19.9 | 1.8x |
| ClimateAnalysis | Code+MD | 13m 0s | 14,629 | 18.8 | 13.5 | 1.4x |
| **Mean** | | | | **33.7** | **16.6** | **2.4x** |

### Sonnet 4.6

| Benchmark | Type | Wall time | Words | Words/s | CC baseline | Speedup |
|-----------|------|-----------|-------|---------|-------------|---------|
| ArcadeBox | Code/JS | 5m 35s | 19,712 | 58.8 | 17.5 | 3.4x |
| LinAlgBook | MD | 2m 37s | 7,877 | 50.2 | 22.6 | 2.2x |
| CloudDocs | MD | 7m 53s | 21,021 | 44.4 | 29.6 | 1.5x |
| MathRef | MD | 9m 2s | 26,266 | 48.5 | 26.7 | 1.8x |
| CompressKit | Code/Python | 9m 18s | 8,541 | 15.3 | 3.7 | 4.1x |
| ShopFlow | Code/Flask | 11m 34s | 13,925 | 20.1 | 11.0 | 1.8x |
| PixelCraft | Code/Pygame | 13m 46s | 16,075 | 19.5 | 5.0 | 3.9x |
| SlideKit | HTML | 22m 45s | 34,843 | 25.5 | 19.9 | 1.3x |
| ClimateAnalysis | Code+MD | 8m 17s | 12,848 | 25.9 | 13.5 | 1.9x |
| **Mean** | | | | **34.2** | **16.6** | **2.4x** |

### Comparison with baselines

| Method | Mean throughput (w/s) | Mean speedup |
|--------|----------------------|-------------|
| `/flow` skill (Opus 4.6) | 33.7 | 2.4x |
| `/flow` skill (Sonnet 4.6) | 34.2 | 2.4x |
| CostPar SDK fork (Sonnet 4.6) | 38.1 | 2.3x |
| Claude Code (no orchestration) | 16.6 | 1.0x |

The `/flow` skill achieves **2.4x mean throughput** over unorchestrated Claude Code across 9 benchmarks, matching the SDK-based implementation — while running entirely on subscription credits.
