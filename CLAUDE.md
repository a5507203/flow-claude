# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flow-Claude is a git-driven autonomous development system that uses the Claude Agent SDK to decompose development requests into fine-grained tasks and execute them autonomously. All state is stored in git commits - no external files or databases.

**Key Innovation**: Git is the single source of truth. Plans, tasks, progress, and results are all stored as structured commit messages in git branches.

## Installation & Setup

```bash
# Install in development mode
pip install -e .

# The package provides unified interactive CLI:
# - flow: Interactive session manager (recommended)
# - flow-claude: Alias to flow (same experience)
# Both commands use TextualCLI (flow_claude/commands/flow_cli.py)
```

**Prerequisites**:
- Python 3.10+
- Claude Code CLI installed and authenticated (`claude auth login`)
- Git repository (will auto-initialize if missing)

## Common Commands

```bash
# Start interactive session (main command)
flow

# Or use the alias
flow-claude

# The interactive CLI provides:
# - Continuous session loop
# - Enter development requests one after another
# - Type \exit or \q to quit
# - Type \help for available commands
# - Keyboard shortcuts (ESC for follow-ups, q for quit)

# Configure session options
flow --model opus              # Use different Claude model
flow --max-parallel 5          # Parallel execution (default: 3 workers)
flow --max-parallel 1          # Sequential execution
flow --verbose                 # Verbose logging
flow --debug                   # Debug mode with full details

# Within interactive session, use forward slash commands:
# /parallel  - Set max parallel workers
# /model     - Select Claude model
# /verbose   - Toggle verbose output
# /debug     - Toggle debug mode
# /auto      - Toggle autonomous mode
# /init      - Generate CLAUDE.md
# /help      - Show help
# /exit      - Exit Flow-Claude

# Run tests
pytest tests/test_parsers.py -v

# Lint
ruff check flow_claude/
```

## Architecture (V7)

### Three-Agent Hierarchy (Simplified)

1. **Orchestrator** (main agent)
   - Plans development sessions and creates execution plans
   - Creates plan and task branches using MCP git tools
   - Spawns worker subagents for parallel execution
   - Manages git worktrees for parallel execution
   - Adaptive planning: re-evaluates and updates plan after each task completion

2. **User Proxy** (subagent, optional)
   - Handles user confirmations and decisions
   - Only registered if `auto_mode=True`
   - Uses fast `haiku` model

3. **Workers** (subagents, 1-N)
   - Execute individual tasks on `task/*` branches
   - Run in git worktrees for parallel execution
   - Signal completion via commits

**V7 Changes:** Merged planner into orchestrator for simplified architecture, reduced ping-pong overhead, and lower API costs.

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

### Immediate Task Completion Pattern (V7 Adaptive Planning)

The orchestrator directly manages planning and execution with immediate per-task processing:

1. **Orchestrator**: Analyzes user request and creates execution plan with all tasks
2. **Orchestrator**: Creates plan branch and identifies initially ready tasks (no dependencies)
3. **Orchestrator**: For each ready task, creates task branch and worktree
4. **Orchestrator → Workers**: Spawns workers for ready tasks (up to max_parallel limit)
5. **Worker completes**: ANY worker finishes and notifies orchestrator
6. **Orchestrator immediately**:
   - Verifies the completed task's implementation
   - Updates plan, marks task complete
   - Removes that worker's worktree
   - Identifies newly-ready tasks (whose dependencies are now met)
   - Launches the idle worker on next available task
7. **Continue**: Each worker completion is processed immediately and independently
8. Repeat until all tasks complete

**V7 Simplification**: No more ping-pong between orchestrator and planner. Orchestrator handles both planning and coordination, reducing API calls and latency. Each task completion is handled immediately without waiting for other workers.

### Git Worktrees for Parallelization

To avoid branch checkout conflicts, workers use git worktrees:

```bash
# Orchestrator creates worktrees before spawning workers
git worktree add .worktrees/worker-1 task/001-description
git worktree add .worktrees/worker-2 task/002-description

# Each worker works in its own worktree (no conflicts!)

# Orchestrator cleans up immediately after each task completes
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

**Write Operations** (orchestrator only):
- `mcp__git__create_plan_branch`: Create plan branch with metadata commit + instruction files
- `mcp__git__create_task_branch`: Create task branch with metadata commit + instruction files
- `mcp__git__update_plan_branch`: Update plan with completed tasks and newly discovered tasks

**Architecture Note**: V7 uses commit-only architecture. Plans, tasks, and progress are stored exclusively in commit messages. No `plan.yaml`, `design.md`, or `todo.md` files.

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
Ready immediately: [001, 002] (no dependencies)
After 001 completes: [003] becomes available
After 002 completes: [004] becomes available
After 001 and 002 complete: [005] becomes available
```

## Agent Instruction Files

Agents load prompts from instruction files. These are auto-created in `.flow-claude/` directory on first run:

- `ORCHESTRATOR_INSTRUCTIONS.md` ← `flow_claude/prompts/orchestrator.md`
- `WORKER_INSTRUCTIONS.md` ← `flow_claude/prompts/worker.md`
- `USER_PROXY_INSTRUCTIONS.md` ← `flow_claude/prompts/user.md`

**Customization**: Users can modify these files per-project to customize agent behavior. Changes persist in the git repository.

**V7 Note**: `PLANNER_INSTRUCTIONS.md` removed - planner functionality merged into orchestrator.

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
- `flow_claude/agents.py:create_worker_agent()` - Worker agent factory (flow_claude/agents.py:108)

### Core Logic
- Agent definitions: `flow_claude/cli.py` (orchestrator + workers, V7: no separate planner)
- ClaudeAgentOptions setup with MCP git tools: `flow_claude/cli.py`
- Session loop handling follow-ups: `flow_claude/cli.py`
- Message handling and logging: `flow_claude/cli.py:handle_agent_message()`

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
New instruction files are auto-committed to flow branch (flow_claude/cli.py:340-418)

### Interactive Mode
Managed by TextualCLI (`textual_cli.py`). After each session completes, automatically prompts for the next development request. Maintains continuous session loop until user explicitly exits with `\exit` or `\q`.

### Safe Unicode Handling
`safe_echo()` handles Windows console encoding issues with emojis (flow_claude/cli.py:28-41)

### Agent Message Tracking
Maps `tool_use_id` to agent names for proper attribution in logs (flow_claude/cli.py:1000-1003, flow_claude/cli.py:1066-1068)

## Testing

- Parser tests should be in `tests/test_parsers.py`
- No tests currently exist in the repository
- When adding tests, use pytest with asyncio support (configured in pyproject.toml)

## Development Notes

- **V7 Architecture**: Orchestrator uses commit-only architecture for planning (MCP git tools only)
- Orchestrator creates all git branches and commits via MCP tools (no manual git commands)
- Workers use Read/Write/Edit freely for implementation
- All git state queries should use MCP tools, not raw git commands (when possible)
- Session state is recoverable from git history - no need for state files
- Windows compatibility: handles cmd.exe path length limits via SDK

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
2. Add to `create_git_tools_server()` tools list in `git_tools.py`
3. Add tool name to appropriate agent's `tools` list in `flow_claude/cli.py`:
   - Orchestrator: Add to `allowed_tools` list (for main agent access)
   - Workers: Add to worker agent definition
4. Update `allowed_tools` if orchestrator needs access

### Modifying Agent Behavior

1. Edit prompt files in `flow_claude/prompts/` directory
2. Changes apply to NEW sessions (instruction files copied on branch creation)
3. For existing projects: edit `*_INSTRUCTIONS.md` files in working directory

### Debugging Sessions

Use verbose/debug flags when starting flow:
```bash
flow --debug
```

Or toggle within interactive session:
```bash
# Type \debug to toggle debug mode
# Type \verbose to toggle verbose mode
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
