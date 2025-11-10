# Flow-Claude UI Enhancements

## Overview

Enhanced the CLI UI to provide clear, structured display of key actions performed by planner and worker agents, making it easy to track what's happening during autonomous development.

## Key Improvements

### 1. Highlighted Key Actions

Important messages are now displayed in **highlighted panels** instead of plain text:

```
+------------------------------- [PLAN] Planner -------------------------------+
|  Creating plan with 5 tasks across 3 waves                                  |
+-----------------------------------------------------------------------------+
```

Automatically highlights messages containing:
- "Creating plan" / "Created plan"
- "Creating task branch" / "Created branch"
- "Starting wave" / "Wave complete"
- "Task complete"
- "Merging"
- "All tasks complete"

### 2. Structured Task Display

Tasks are shown with visual status indicators:

```
[X] Task 001: Setup database schema       (completed)
[~] Task 002: Create API endpoints        (in_progress)
[ ] Task 003: Add authentication          (pending)
[!] Task 004: Fix validation bug          (failed)
```

### 3. Wave Execution Info

Clear display of parallel vs sequential execution:

```
+----------------------------- Wave 1 Execution ------------------------------+
| Wave:      1                                                                |
| Tasks:     001, 002                                                         |
| Execution: Parallel                                                         |
+-----------------------------------------------------------------------------+
```

### 4. Git Operations Tracking

All git operations are clearly marked:

```
[GIT] Create: task/001-setup-database - from flow
[GIT] Merge: task/001-setup-database - into flow
```

### 5. MCP Git Tool Display

**Key Feature**: Git MCP tools are now **always visible** (even without verbose mode) because they represent critical planner/worker actions:

```
[GIT] Create Task Branch - Task 001: Setup PostgreSQL database with initial schema
[GIT] Create Plan Branch - session-20251111-120000
[GIT] Update Plan Branch - Wave 2
```

Parse operations are hidden by default (too noisy), shown only in debug mode.

### 6. Progress Summary

Clear progress tracking:

```
Progress: 2/5 (40%)
Current:  Implementing API endpoints
```

### 7. Agent-Specific Coloring

- **Orchestrator**: Cyan
- **Planner**: Blue
- **Worker**: Green
- **User Proxy**: Yellow
- **System**: Magenta
- **Git Operations**: Magenta

## Usage

### Normal Mode (Default)

Shows:
- All agent text messages
- Highlighted key actions
- Git MCP tool operations
- Errors, warnings, successes

### Verbose Mode (`--verbose`)

Additionally shows:
- All tool uses (Read, Write, Edit, Bash, etc.)
- Tool results
- Additional details

### Debug Mode (`--debug`)

Additionally shows:
- Tool input parameters (full JSON)
- Tool output/results (full, no truncation)
- Parse operations
- Internal state tracking

## Benefits

1. **Clear Progress Tracking**: See exactly which tasks are being created and executed
2. **Git Operations Visibility**: Understand branch creation, merges without checking git manually
3. **Parallel Execution Insight**: See which tasks run together in waves
4. **Problem Identification**: Failed tasks are clearly marked
5. **Reduced Noise**: Parse operations hidden, only important actions shown

## Windows Compatibility

All emojis are replaced with ASCII equivalents on Windows:
- `🎯` → `[ORCH]`
- `📋` → `[PLAN]`
- `⚙️` → `[WORK]`
- `✓` → `[OK]`
- `✗` → `[ERR]`
- `⎇` → `[GIT]`

Separators use `-` instead of `─` for encoding safety.

## Example Output

```
+---------------------------- Flow-Claude Session ----------------------------+
| Session:  session-20251111-120000                                           |
| Model:    sonnet                                                            |
| Workers:  3                                                                 |
| Branch:   flow                                                              |
+-----------------------------------------------------------------------------+

[REQUEST] Create user authentication system

[ORCH] Orchestrator: Processing your request...

+------------------------------ [PLAN] Planner -------------------------------+
|  Creating plan with 3 tasks across 2 waves                                  |
+-----------------------------------------------------------------------------+

[GIT] Create Plan Branch - session-20251111-120000
[GIT] Create Task Branch - Task 001: Setup database schema
[GIT] Create Task Branch - Task 002: Create auth endpoints
[GIT] Create Task Branch - Task 003: Add login UI

+----------------------------- Wave 1 Execution ------------------------------+
| Wave:      1                                                                |
| Tasks:     001, 002                                                         |
| Execution: Parallel                                                         |
+-----------------------------------------------------------------------------+

[X] Task 001: Setup database schema
[~] Task 002: Create auth endpoints

+------------------------------- [WORK] Worker -------------------------------+
|  Task complete: Database schema ready                                       |
+-----------------------------------------------------------------------------+

Progress: 2/3 (67%)
Current:  Adding login UI
```

## API for Custom Messages

The RichUI class provides methods that can be used by agents or other components:

```python
# Task display
ui.print_task_info("001", "Setup database", "completed")

# Wave info
ui.print_wave_info(wave_num=1, task_ids=["001", "002"])

# Git operations
ui.print_git_operation("create", "task/001-setup", "from flow")

# Progress
ui.print_progress_summary(completed=2, total=5, current_task="API endpoints")
```

## Files Modified

1. `flow_claude/cli_rich_ui.py` - Enhanced with new display methods
2. `flow_claude/cli.py` - Integrated RichUI, fixed control type handling
3. `flow_claude/cli_controller.py` - Updated to use Rich throughout
4. `pyproject.toml` - Added `rich>=13.0.0` dependency

## Testing

Run `python test_rich_ui.py` to see all UI features in action.
