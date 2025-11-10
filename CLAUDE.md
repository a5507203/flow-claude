# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flow-Claude is a git-driven autonomous development system that uses the Claude Agent SDK to decompose development requests into fine-grained tasks and execute them autonomously. All state is stored in git commits - no external files or databases.

**Key Innovation**: Git is the single source of truth. Plans, tasks, progress, and results are all stored as structured commit messages in git branches.

## Installation & Setup

```bash
# Install in development mode
pip install -e .

# The package provides two entry points:
# - flow-claude: Main CLI (flow_claude/cli.py)
# - flow: Alternative entry point (flow_claude/commands/flow_cli.py)
```

**Prerequisites**:
- Python 3.10+
- Claude Code CLI installed and authenticated (`claude auth login`)
- Git repository (will auto-initialize if missing)

## Common Commands

```bash
# Development session (main command)
flow-claude develop "your development request here"

# With different models
flow-claude develop "request" --model opus
flow-claude develop "request" --model haiku

# Parallel execution (default: 3 workers)
flow-claude develop "request" --max-parallel 5

# Sequential execution
flow-claude develop "request" --max-parallel 1

# Verbose/debug logging
flow-claude develop "request" --verbose
flow-claude develop "request" --debug

# Interactive mode (default: enabled)
# After completion, prompts for follow-up requests
flow-claude develop "request" --interactive

# Disable interactive mode for one-shot execution
flow-claude develop "request" --no-interactive

# Permission modes
flow-claude develop "request" --permission-mode ask  # Confirm edits
flow-claude develop "request" --permission-mode deny  # Dry run

# Run tests
pytest tests/test_parsers.py -v

# Lint
ruff check flow_claude/
```

## Architecture (V6.6+)

### Four-Agent Hierarchy

1. **Orchestrator** (main agent)
   - Coordinates wave-based ping-pong execution
   - Spawns planner and worker subagents
   - Manages git worktrees for parallel execution
   - Cannot directly create branches (SDK constraint)

2. **Planner** (subagent)
   - Creates execution plans on `plan/session-*` branches
   - Creates task branches using MCP git tools
   - Updates plans between waves
   - Cannot spawn workers (only orchestrator can spawn subagents)

3. **User Proxy** (subagent, optional)
   - Handles user confirmations and decisions
   - Only registered if `auto_mode=True`
   - Uses fast `haiku` model

4. **Workers** (subagents, 1-N)
   - Execute individual tasks on `task/*` branches
   - Run in git worktrees for parallel execution
   - Signal completion via commits

### Branch Structure

```
main/master     # Production code
├── flow        # Base branch for development sessions
│   └── plan/session-YYYYMMDD-HHMMSS  # Plan branch (session metadata)
│       ├── task/001-description      # Task branch 1
│       ├── task/002-description      # Task branch 2
│       └── task/003-description      # Task branch 3
```

**Critical**: The `flow` branch is created on first run and serves as the base for all sessions. Users select which branch to use as the base when `flow` is first created.

### Wave-Based Execution Pattern

The orchestrator coordinates a **ping-pong loop** between planner and workers:

1. **Orchestrator → Planner**: "Create plan and Wave 1 branches"
2. **Planner returns**: Creates branches, returns to orchestrator
3. **Orchestrator**: Creates git worktrees for parallel execution
4. **Orchestrator → Workers**: Spawns all workers in parallel (one message)
5. **Workers return**: Complete tasks, merge to flow, return to orchestrator
6. **Orchestrator → Planner**: "Wave N complete. Prepare Wave N+1."
7. Repeat until all waves complete

**Why**: The planner cannot spawn workers (SDK constraint). Only the orchestrator can spawn subagents.

### Git Worktrees for Parallelization

To avoid branch checkout conflicts, workers use git worktrees:

```bash
# Orchestrator creates worktrees before spawning workers
git worktree add .worktrees/worker-1 task/001-description
git worktree add .worktrees/worker-2 task/002-description

# Each worker works in its own worktree (no conflicts!)

# Orchestrator cleans up after wave completes
git worktree remove .worktrees/worker-1
git worktree remove .worktrees/worker-2
```

## MCP Git Tools

Custom MCP tools provide structured git operations:

**Read Operations**:
- `mcp__git__parse_task`: Parse task metadata from branch's first commit
- `mcp__git__parse_plan`: Parse execution plan from plan branch's latest commit
- `mcp__git__parse_worker_commit`: Parse worker's progress (design + TODO)
- `mcp__git__get_provides`: Query completed task capabilities from flow branch

**Write Operations** (planner only):
- `mcp__git__create_plan_branch`: Create plan branch with metadata commit + instruction files
- `mcp__git__create_task_branch`: Create task branch with metadata commit + instruction files
- `mcp__git__update_plan_branch`: Update plan with completed tasks, new wave tasks

**Architecture Note**: V6.7+ uses commit-only architecture. Plans, tasks, and progress are stored exclusively in commit messages. No `plan.yaml`, `design.md`, or `todo.md` files.

## Commit Message Formats

All metadata follows structured formats defined in `flow_claude/parsers.py`:

### Task Metadata (first commit on task branch)
```
Initialize task/001-description

## Task Metadata
ID: 001
Description: Create User model
Status: pending

## Dependencies
Preconditions:
  - Database connection established
Provides:
  - User model class
  - User.email field

## Files
Files to modify:
  - src/models/user.py

## Context
Session Goal: Add user authentication
Session ID: session-20250106-140530
Plan Branch: plan/session-20250106-140530
Plan Version: v1
Depends on: []
Enables: ['002', '003']

## Estimates
Estimated Time: 8 minutes
Priority: high
```

### Plan Commit (on plan branch)
```
Initialize execution plan v1

## Session Information
Session ID: session-20250106-140530
User Request: Add user authentication
Plan Version: v1

## Architecture
System uses MVC pattern with SQLAlchemy ORM...

## Design Patterns
Repository pattern for data access...

## Technology Stack
Python 3.10, Flask, SQLAlchemy, bcrypt

## Tasks
### Task 001
ID: 001
Description: Create User model
Preconditions: []
Provides:
  - User model class
Files:
  - src/models/user.py
Estimated Time: 8 minutes
Priority: high

## Estimates
Estimated Total Time: 45 minutes
Total Tasks: 5

## Dependency Graph
Wave 1: [001, 002] (parallel)
Wave 2: [003] (depends on 001, 002)
```

## Agent Instruction Files

Agents load prompts from instruction files. These are auto-created in the working directory on first run:

- `ORCHESTRATOR_INSTRUCTIONS.md` ← `flow_claude/prompts/orchestrator.md`
- `PLANNER_INSTRUCTIONS.md` ← `flow_claude/prompts/planner.md`
- `WORKER_INSTRUCTIONS.md` ← `flow_claude/prompts/worker.md`
- `USER_PROXY_INSTRUCTIONS.md` ← `flow_claude/prompts/user.md`

**Customization**: Users can modify these files per-project to customize agent behavior. Changes persist in the git repository.

## Key Code Locations

### Entry Points & CLI
- `flow_claude/cli.py:develop()` - Main command implementation (flow_claude/cli.py:158)
- `flow_claude/cli.py:run_development_session()` - Session orchestration (flow_claude/cli.py:484)
- `flow_claude/cli.py:handle_agent_message()` - Message processing and logging (flow_claude/cli.py:978)

### Git Operations
- `flow_claude/git_tools.py` - MCP tool definitions for git operations
- `flow_claude/parsers.py` - Commit message parsing utilities
- `flow_claude/git_tools.py:create_git_tools_server()` - MCP server factory (flow_claude/git_tools.py:1340)

### Agent Definitions
- `flow_claude/agents.py:create_planning_agent()` - Planner agent factory (flow_claude/agents.py:47)
- `flow_claude/agents.py:create_worker_agent()` - Worker agent factory (flow_claude/agents.py:108)

### Core Logic
- Agent definitions: `flow_claude/cli.py:636` (planner), `flow_claude/cli.py:668` (workers)
- ClaudeAgentOptions setup: `flow_claude/cli.py:691`
- Session loop with interventions: `flow_claude/cli.py:850`
- Multi-round conversation: `flow_claude/cli.py:924`

## Important Implementation Details

### Session ID Generation
Sessions use timestamped IDs: `session-YYYYMMDD-HHMMSS` (flow_claude/cli.py:557)

### Flow Branch Setup
On first run, if `flow` branch doesn't exist:
1. Shows available branches
2. Prompts user to select base branch
3. Creates `flow` branch from selected base
4. Subsequent sessions use existing `flow` branch
See: flow_claude/cli.py:222-313

### Auto-Commit Instruction Files
New instruction files are auto-committed to main/master branch (flow_claude/cli.py:315-393)

### Interactive Mode
After session completion, prompts for follow-up requests. Recursively calls `run_development_session()` with new request (flow_claude/cli.py:924-971)

### Safe Unicode Handling
`safe_echo()` handles Windows console encoding issues with emojis (flow_claude/cli.py:28-41)

### Agent Message Tracking
Maps `tool_use_id` to agent names for proper attribution in logs (flow_claude/cli.py:1000-1003, flow_claude/cli.py:1066-1068)

## Testing

- Parser tests should be in `tests/test_parsers.py`
- No tests currently exist in the repository
- When adding tests, use pytest with asyncio support (configured in pyproject.toml)

## Development Notes

- **DO NOT** use Write/Edit tools in planner prompts - planner uses commit-only architecture
- Workers use Read/Write/Edit freely for implementation
- All git state queries should use MCP tools, not raw git commands (when possible)
- Session state is recoverable from git history - no need for state files
- Windows compatibility: handles cmd.exe path length limits via SDK (flow_claude/cli.py:635)

## Dependencies

Core dependencies (pyproject.toml:14-19):
- `claude-agent-sdk>=0.1.0` - Claude Agent SDK
- `click>=8.1.0` - CLI framework
- `psutil>=5.9.0` - Process utilities
- `questionary>=2.1.0` - Interactive prompts (flow branch selection)

Dev dependencies (pyproject.toml:22-25):
- `pytest>=7.0.0`
- `pytest-asyncio>=0.21.0`
- `ruff>=0.1.0` - Linting

## Common Workflows

### Adding a New MCP Tool

1. Define tool in `flow_claude/git_tools.py` using `@tool` decorator
2. Add to `create_git_tools_server()` tools list (flow_claude/git_tools.py:1362-1374)
3. Add tool name to agent's `tools` list in `flow_claude/cli.py` (around lines 642-653 for planner, 672-677 for workers)
4. Update `allowed_tools` if needed (flow_claude/cli.py:694-706)

### Modifying Agent Behavior

1. Edit prompt files in `flow_claude/prompts/` directory
2. Changes apply to NEW sessions (instruction files copied on branch creation)
3. For existing projects: edit `*_INSTRUCTIONS.md` files in working directory

### Debugging Sessions

Use verbose/debug flags:
```bash
flow-claude develop "request" --debug
```

Debug output includes:
- Tool inputs (JSON, no truncation)
- Tool outputs (full, no truncation for errors/MCP tools)
- Agent identification in logs
- Git operations and branch creation

### Examining Session State

```bash
# View plan
git log plan/session-YYYYMMDD-HHMMSS --format=%B -n 1

# View task metadata
git log task/001-description --reverse --format=%B -n 1

# View completed tasks on flow branch
git log flow --merges --format=%B

# List all task branches
git branch --list 'task/*'

# Check current plan branch (stored in git config)
git config --get flow-claude.current-plan
```
