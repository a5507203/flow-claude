# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Flow-Claude** is a git-first autonomous development system using the Claude agent SDK. It orchestrates multi-agent collaboration with a ping-pong pattern to decompose development requests into fine-grained tasks (5-10 minutes each), execute them via planning and worker agents, and store all metadata in git commits.

### Core Philosophy

**Git as Single Source of Truth**: All task metadata, execution plans, and state are stored in git commits and branches. No external configuration files. The entire system state can be reconstructed from git history alone.


## Commands

### Setup and Installation

```bash
# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Flow-Claude

Flow-Claude runs INSIDE other git repositories (not from its own directory):

```bash
# Navigate to your project's git repository
cd /path/to/your/project

# Run Flow-Claude (interactive mode by default)
python -m flow_claude.cli develop "your development request" --verbose --debug

# Or if installed as package
flow-claude develop "your request"

# Disable interactive mode for CI/CD or scripts
flow-claude develop "your request" --no-interactive
```

### Multi-Round Conversations

**New in V6.7:** Flow-Claude now supports multi-round conversations! After completing a development request, you can provide follow-up requests to continue building.

```bash
# Start Flow-Claude in interactive mode (default)
$ flow-claude develop "Create a blog backend API"

[... executes waves, builds backend ...]

============================================================
SUCCESS: Development session complete!
============================================================

------------------------------------------------------------
INTERACTIVE MODE: Enter a follow-up request to continue,
                  or type 'q' / 'quit' / 'exit' to finish.
------------------------------------------------------------

Follow-up request: Create a React frontend for this backend

[NEW REQUEST] Starting new development round...
Request: Create a React frontend for this backend

[... executes new waves, builds frontend ...]

============================================================
SUCCESS: Development session complete!
============================================================

------------------------------------------------------------
INTERACTIVE MODE: Enter a follow-up request to continue,
                  or type 'q' / 'quit' / 'exit' to finish.
------------------------------------------------------------

Follow-up request: q

============================================================
Exiting Flow-Claude. Goodbye!
============================================================
```

**How it works:**
- After completing all waves, Flow-Claude prompts for a follow-up request
- Each follow-up creates a new session with a new plan branch
- All work accumulates on the main branch across sessions
- The orchestrator builds on existing codebase state
- No limit on number of follow-ups

**Use cases:**
- **Iterative development**: Build backend → Add frontend → Add features → Refactor
- **Incremental features**: Core functionality → Admin panel → Analytics → Reports
- **Exploration**: Try approach A → Try approach B → Combine best parts
- **Bug fixes**: Initial implementation → Fix discovered issues → Add tests

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parsers.py -v

# Run with coverage
pytest tests/ --cov=flow_claude --cov-report=html
```

### Code Quality

```bash
# Lint with ruff
ruff check flow_claude/

# Format code
ruff format flow_claude/

# Check formatting
ruff format flow_claude/ --check
```

## Architecture

### The Prompt-Driven Design

**99% of workflow logic lives in system prompts** (`prompts/`), not Python code. The Python code (`flow_claude/`) is minimal glue:

- `cli.py` (~860 lines): CLI entry point, creates agent YAML files dynamically in `.claude/agents/`
- `agents.py` (~50 lines): Agent definition helpers, loads prompts from `prompts/`
- `git_tools.py` (~120 lines): Custom MCP tools for git operations
- `parsers.py` (~150 lines): Parse structured git commit messages

**System prompts** (the real brains):
- `prompts/orchestrator.md` (~200 lines): Main agent workflow, ping-pong coordinator
- `prompts/planner.md` (~1200 lines): Planning workflow, breaks down requests, creates tasks
- `prompts/worker.md` (~1000 lines): Worker workflow, implements individual tasks

### Agent Architecture (V6.7 - Ping-Pong Pattern)

```
Main Orchestrator (prompts/orchestrator.md)
  ├─→ Planner Subagent (prompts/planner.md)
  │    Round 1: Creates plan branch + Wave 1 task branches → returns
  │    Round N: Updates docs + creates Wave N task branches → returns
  │
  └─→ Worker Subagents (prompts/worker.md)
       worker-1, worker-2, worker-3...
       Execute individual tasks in parallel → return when complete
```

**Critical SDK Constraint**: The main orchestrator is the only agent that can spawn subagents. The planner cannot spawn workers. This creates a "ping-pong" pattern where control bounces between orchestrator, planner, and workers.

**Agent files**: Dynamically created in `.claude/agents/` with YAML frontmatter during each session (see `cli.py` lines 277-318).

### Git-Based Data Model

All data lives in git branches and commits:

**Plan Branch** (`plan/session-YYYYMMDD-HHMMSS`):
- Contains `plan.md` (task list with status tracking)
- Contains `system-overview.md` (architecture and design decisions)
- Updated after each wave completes

**Task Branches** (`task/001-description`):
- Initial commit: Task metadata (ID, description, preconditions, provides) in EXACT format for `parsers.py`
- Subsequent commits: Implementation work
- Final commit: `TASK_COMPLETE` signal

**Main Branch**:
- Merge commits contain task results and "Provides" metadata
- Merge messages include design decisions from worker's work
- Clean state after each wave

### Git Worktrees for Parallel Execution (V6.7)

**Critical for parallel workers**: Each worker operates in an isolated git worktree to avoid checkout conflicts.

**Orchestrator workflow** (see `cli.py` lines 577-599):
1. Planner creates task branches
2. Orchestrator creates worktrees:
   ```bash
   git worktree add .worktrees/worker-1 task/001-description
   git worktree add .worktrees/worker-2 task/002-description
   ```
3. Orchestrator spawns workers with worktree paths in their prompts
4. Workers execute in isolation (no `git checkout` needed - already on correct branch)
5. After wave completes, orchestrator cleans up:
   ```bash
   git worktree remove .worktrees/worker-1
   git worktree remove .worktrees/worker-2
   ```

### Custom MCP Tools

Seven custom tools exposed to agents via MCP protocol (`flow_claude/git_tools.py`):

**Query Tools** (read git state):
1. **`mcp__git__parse_task`**: Extracts task metadata from first commit on task branch
2. **`mcp__git__parse_plan`**: Parses execution plan from plan branch commit
3. **`mcp__git__get_provides`**: Queries available preconditions from main branch merges
4. **`mcp__git__parse_worker_commit`**: Parses worker's latest commit (design + TODO progress)

**Creation Tools** (atomically create branches):
5. **`mcp__git__create_plan_branch`**: Creates plan branch with instruction files + metadata commit
6. **`mcp__git__create_task_branch`**: Creates task branch with instruction files + metadata commit
7. **`mcp__git__update_plan_branch`**: Updates plan commit with completed tasks + new wave tasks

**Why creation tools are critical:**
- **Instruction files always included**: All 4 instruction files (ORCHESTRATOR_INSTRUCTIONS.md, PLANNER_INSTRUCTIONS.md, WORKER_INSTRUCTIONS.md, USER_PROXY_INSTRUCTIONS.md) are automatically copied from `flow_claude/prompts/` to every branch
- **Metadata format guaranteed**: Commit messages follow exact `parsers.py` format (no agent errors)
- **Atomic operations**: Branch creation + file copy + commit happen atomically (rollback on error)
- **Performance**: Reduces planner tool calls from ~10 per wave to 1-2 (5-10x faster)

These tools allow agents to query git history and create branches without complex subprocess orchestration in prompts.

### Parsing Utilities

`flow_claude/parsers.py` provides functions to parse structured commit messages:

- `parse_commit_message()`: Splits commit into `## Section` blocks
- `parse_task_metadata()`: Extracts ID, description, preconditions, provides, files
- `parse_plan_commit()`: Extracts execution plan details
- `extract_provides_from_merge_commits()`: Queries what's available on main

## Key Workflows

### Planning Phase (planner.md)

When orchestrator invokes planner:

**Round 1 (Initial):**
1. Analyze codebase (reads README, source files)
2. Create `plan/session-*` branch with `plan.md` and `system-overview.md`
3. Break request into 5-10 minute tasks with dependency tracking
4. Create Wave 1 task branches (tasks with `Preconditions: []`)
5. Commit task metadata using EXACT format (required by parsers.py)
6. Return control to orchestrator with list of created branches

**Round N (Subsequent):**
1. Update `plan.md` with completed tasks
2. Update `system-overview.md` with learnings
3. Identify Wave N tasks (dependencies now satisfied)
4. Create Wave N task branches with proper metadata
5. Return control to orchestrator

**Critical Fix (2025-01-06):** Planner MUST commit metadata immediately after creating each task branch to avoid git checkout conflicts. See `prompts/planner.md` lines 412-465 for explicit git workflow.

### Worker Execution (worker.md)

Each worker follows this workflow:

1. Navigate to assigned worktree (`.worktrees/worker-N`)
2. Read task metadata from first commit
3. Understand session context from plan branch
4. Read preconditions from main branch
5. Create `design.md` (design decisions BEFORE coding)
6. Create `todo.md` (implementation checklist)
7. Implement incrementally (commit after EACH todo item)
8. Run tests and validate
9. Signal completion with `TASK_COMPLETE` commit
10. Return control to orchestrator

**Workers work in isolated worktrees** - no `git checkout` needed, branch is already checked out.

### Orchestrator Phase (orchestrator.md)

Main agent coordinates everything:

**The Wave-Based Loop:**
1. Invoke planner for Wave N
2. Read created task branches
3. Create git worktrees (one per task)
4. Spawn workers IN ONE MESSAGE for parallelization (with worktree paths)
5. Wait for workers to complete
6. Clean up worktrees
7. Check if more waves remain (read `plan.md`)
8. If yes: Invoke planner again (go to step 1)
9. If no: Report final results

## Commit Message Structure

Flow-Claude uses structured commit messages parsed by `parsers.py`:

```
Initialize task/001-user-model

## Task Metadata
ID: 001
Description: Create User model with email and password fields
Status: pending

## Dependencies
Preconditions: []
Provides:
  - User model class
  - User.email field (unique, indexed)
  - User.password_hash field

## Files
Files to modify:
  - src/auth/models.py (create)
  - tests/test_models.py (create)

## Context
Session Goal: Add user authentication
Session ID: session-20250115-103000
Plan Branch: plan/session-20250115-103000
Plan Version: v1
Depends on: []
Enables:
  - task-002 (auth service needs User model)

## Estimates
Estimated Time: 8 minutes
Priority: high
```

**Critical format details** (see `prompts/planner.md` lines 30-80):
- NO `Title:` field (parser ignores it)
- `## Dependencies` section with both `Preconditions:` and `Provides:`
- `## Files` section with `Files to modify:` subheading (exact phrase!)
- `## Estimates` as separate section
- Structured `Context` fields: `Depends on:`, `Enables:`

### Prompts

When revise agents prompts, the prompts should be clear and precise

## Important Design Constraints

### Task Granularity

Tasks MUST be 5-10 minutes each:
- Too small (< 5 min): Overhead not worth it
- Too large (> 10 min): Loses atomicity and parallelization benefits
- Sweet spot: 6-8 minutes

### Wave-Based Branch Creation

**Only Wave 1 branches are created initially.** Subsequent wave branches are created dynamically after dependencies are satisfied and merged to main. This is intentional to support dynamic replanning.

### Agent File Discovery

The SDK auto-discovers agents from `.claude/agents/` directory. Each agent file must have YAML frontmatter:

```markdown
---
name: worker-1
description: Executes individual development tasks
tools: Bash, Read, Write, Edit, Grep
---

[Agent system prompt here...]
```

The CLI (`cli.py`) dynamically creates these files at runtime based on `--max-parallel` flag (default: 3 workers).

## Modifying Behavior

### To change planning logic:
Edit `prompts/planner.md` (1200 lines of workflow instructions)

### To change worker behavior:
Edit `prompts/worker.md` (1000 lines of implementation workflow)

### To change orchestration:
Edit `prompts/orchestrator.md` (200 lines of coordination logic)

### To change CLI behavior:
Edit `flow_claude/cli.py`, but most logic should stay in prompts

**Important**: The `initial_prompt` in `cli.py` (lines 577-599) takes precedence over file-based prompts. If orchestrator isn't following instructions in `orchestrator.md`, check the `initial_prompt`.

### To add new MCP tools:
1. Add function in `flow_claude/git_tools.py` with `@tool` decorator
2. Add tool to `create_git_tools_server()` tools list
3. Update agent frontmatter in `cli.py` to include new tool

## Common Pitfalls

1. **Running flow-claude from flow-claude repo**: Flow-Claude is meant to be run FROM other git repositories, not from its own repo. Create a test directory with `git init` and run from there.

2. **Modifying Python when you should modify prompts**: 99% of behavior changes belong in `prompts/`, not Python files.

3. **Missing .claude/agents/ files**: The CLI creates these dynamically. If missing, check `cli.py` lines 277-318.

4. **Planner creating wrong metadata for Wave 2+ branches**: If Wave 2+ branches have wrong metadata or git checkout conflicts, check that `prompts/planner.md` lines 412-465 have explicit git workflow with `git commit` and `git checkout main` after EACH branch creation.

5. **Workers not using worktrees**: If workers use `git checkout`, worktree isolation is broken. Check that `cli.py` initial_prompt includes worktree instructions (lines 577-599).

## File Locations Reference

```
flow-claude/
├── flow_claude/          # Python package (minimal glue)
│   ├── cli.py           # CLI entry, creates .claude/agents/ files
│   ├── agents.py        # Agent definition helpers
│   ├── git_tools.py     # Custom MCP tools
│   └── parsers.py       # Git commit parsing
│
├── prompts/             # System prompts (THE BRAINS)
│   ├── orchestrator.md  # Main agent (ping-pong coordinator)
│   ├── planner.md       # Planning agent workflow
│   └── worker.md        # Worker agent workflow
│
├── tests/               # Test suite
│   ├── test_parsers.py  # Unit tests for parsing
│   ├── test_git_tools.py
│   └── test_cli.py
│
├── QUICKSTART.md        # User-facing getting started guide
└── pyproject.toml       # Package configuration
```

## Understanding Git State

All state is queryable via git:

```bash
# View execution plan
git log plan/session-* --oneline

# View task metadata
git log task/001-* --reverse --format=%B -n 1

# View available provides
git log main --merges --format=%B | grep -A 20 "## Provides"

# Check task status
git log --all --branches='task/*' --grep="TASK_COMPLETE"

# Check if worktrees exist
git worktree list
```

## Debugging Tips

### Check orchestrator workflow
If orchestrator isn't creating worktrees or following ping-pong pattern, check `cli.py` lines 577-599 for the `initial_prompt`.

### Check planner branch creation
If Wave 2+ branches have wrong metadata:
1. Check `prompts/planner.md` lines 412-465
2. Ensure explicit `git commit` and `git checkout main` after EACH branch
3. Look for git checkout conflicts in logs

### Check worker isolation
If workers conflict on same files:
1. Verify worktrees created: `git worktree list`
2. Check worker prompts include worktree paths
3. Verify workers use `cd <worktree-path>`, not `git checkout`

## Version History

- **V6.1**: Initial git-first design
- **V6.2**: Added test-driven development, documentation-first workflow
- **V6.5**: Full autonomy, planner handles everything
- **V6.7** (current): Ping-pong pattern + git worktrees for parallel execution
  - Orchestrator coordinates planner and workers
  - Wave-based dynamic branch creation
  - Git worktree isolation for parallel workers
  - Fixed: Planner metadata commit workflow for Wave 2+
