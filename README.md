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

## Benchmark

### Test task (ArcadeBox)

```
/flow Build a browser-based game arcade with 8 playable games. The arcade should have a main menu screen where the player selects a game, and each game runs in an HTML5 Canvas element with keyboard/mouse controls. All games share a persistent high score system stored in localStorage, and the arcade tracks global statistics (total games played, total time played, best scores).

Games to implement:
1. Tetris — 10x20 grid, 7 tetrominoes with SRS rotation and wall kicks, gravity with increasing speed, scoring 100/300/500/800 for 1/2/3/4 lines, ghost piece, next piece preview
2. Minesweeper — 3 difficulties (9x9/10, 16x16/40, 30x16/99), flood-fill reveal, safe first click, timer and mine counter
3. 2048 — 4x4 sliding tiles, merge animations, 90/10 spawn ratio, win at 2048 with continue option
4. Snake — grid-based movement, speed increases with length, food spawning, wall/self collision
5. Breakout — mouse+keyboard paddle, angle-based ball deflection, 5 rows of colored bricks, 3 lives, level progression
6. Sudoku — backtracking puzzle generator, 3 difficulties (35/28/22 givens), pencil marks, conflict highlighting, timer
7. Memory Match — 3 grid sizes (4x4/4x6/6x6), emoji pairs, flip animation, move counter
8. Gomoku — 15x15 board, human vs AI (minimax alpha-beta depth 3-4), pattern evaluation heuristic

Requirements: Pure HTML/CSS/JS, no frameworks. Canvas rendering at 60 FPS. Pause, restart, back-to-menu for each game. Each game file 300+ lines. Works by opening index.html directly.
```

### Results

| Method | Model | Wall time | Deliverable words | Words/s |
|--------|-------|-----------|-------------------|---------|
| **`/flow` skill** | **Opus 4.6** | **4m 46s** | **17,261** | **60.4** |
| **`/flow` skill** | **Sonnet 4.6** | **5m 35s** | **19,712** | **58.8** |
| CostPar (SDK fork) | Sonnet 4.6 | 7m 19s | 23,091 | 52.6 |
| Claude Code (no orchestration) | Sonnet 4.6 | 18m 25s | 19,338 | 17.5 |

The `/flow` skill achieves **3.4x throughput** over unorchestrated Claude Code and matches or exceeds the SDK-based implementation — while running entirely on subscription credits.
