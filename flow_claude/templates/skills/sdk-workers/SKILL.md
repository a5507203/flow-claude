---
name: sdk-workers
description: Worker management for parallel task execution. Provides 2 tools for launching workers and parsing their progress in git worktrees.
---

# SDK Workers Skill

## Instructions

This skill provides 2 command-line tools for managing worker agents that execute tasks in parallel using git worktrees. Each worker runs in an isolated git worktree to avoid branch checkout conflicts.

### Available Commands

- `launch_worker` - Launch a worker agent to execute a specific task
- `parse_worker_commit` - Parse worker's progress from commits

### Worker Lifecycle

The typical worker lifecycle follows this pattern:

1. **Preparation** - Create task branch and git worktree
2. **Launch** - Start the worker agent in the worktree
3. **Monitor** - Orchestrator monitors worker output through SDK message stream
4. **Completion** - Clean up worktree after task finishes

### Important Rules

- Always create the git worktree BEFORE launching a worker
- Each worker must have its own unique worktree directory
- Clean up worktrees immediately after task completion to save disk space
- Orchestrator monitors workers through SDK agent message stream (no polling needed)
- Handle worker failures gracefully (orchestrator kills worker, clean worktree, analyze error)
- Respect the max_parallel limit from the orchestrator skill configuration
- Reuse worker IDs after workers complete (use sequential numbers: 1, 2, 3)

### Creating Worktrees

Before launching a worker, create a git worktree:
```bash
git worktree add .worktrees/worker-N task/NNN-description
```

After the worker completes, clean it up:
```bash
git worktree remove .worktrees/worker-N
```

If a worktree is locked or won't remove:
```bash
git worktree remove --force .worktrees/worker-N
```

### Command Output Format

All commands return JSON with a `success` field:
- Success: `{"success": true, ...worker data...}`
- Failure: `{"success": false, "error": "error message"}`

## Examples

### Example 1: Launching a Worker

```bash
# First create the task branch
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" \
  --description="Create User model" \
  --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" \
  --preconditions='[]' \
  --provides='["User model"]' \
  --files='["src/models/user.py"]'

# Create git worktree
git worktree add .worktrees/worker-1 task/001-create-user-model

# Launch the worker
python -m flow_claude.scripts.launch_worker \
  --worker-id="1" \
  --task-branch="task/001-create-user-model" \
  --cwd=".worktrees/worker-1" \
  --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" \
  --model="sonnet" \
  --instructions="You are a development worker. Implement the task described in the task branch metadata. Follow best practices and write clean code."
```

**Output:**
```json
{
  "success": true,
  "worker_id": "1",
  "task_branch": "task/001-create-user-model",
  "message": "Worker-1 launched (placeholder - requires SDK integration)"
}
```

### Example 2: Handling Worker Completion

```bash
# When orchestrator detects a worker has completed (through SDK message stream):

# 1. Parse the worker's final commit to verify completion
python -m flow_claude.scripts.parse_worker_commit --branch="task/002-password-hashing"

# 2. Clean up the worktree
git worktree remove .worktrees/worker-2

# 3. Update the plan
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch="plan/session-20250119-143000" \
  --completed='["002"]' \
  --version="v2"

# 4. Launch next task if available (reusing worker ID)
git worktree add .worktrees/worker-2 task/004-registration-endpoint
python -m flow_claude.scripts.launch_worker \
  --worker-id="2" \
  --task-branch="task/004-registration-endpoint" \
  --cwd=".worktrees/worker-2" \
  --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" \
  --model="sonnet"
```

### Example 3: Parallel Execution (3 Workers)

```bash
# Launch 3 workers in parallel for wave 1 tasks

# Create all task branches
python -m flow_claude.scripts.create_task_branch --task-id="001" ...
python -m flow_claude.scripts.create_task_branch --task-id="002" ...
python -m flow_claude.scripts.create_task_branch --task-id="003" ...

# Create all worktrees
git worktree add .worktrees/worker-1 task/001-create-user-model
git worktree add .worktrees/worker-2 task/002-password-hashing
git worktree add .worktrees/worker-3 task/003-jwt-tokens

# Launch all workers
python -m flow_claude.scripts.launch_worker \
  --worker-id="1" --task-branch="task/001-create-user-model" \
  --cwd=".worktrees/worker-1" --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" --model="sonnet"

python -m flow_claude.scripts.launch_worker \
  --worker-id="2" --task-branch="task/002-password-hashing" \
  --cwd=".worktrees/worker-2" --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" --model="sonnet"

python -m flow_claude.scripts.launch_worker \
  --worker-id="3" --task-branch="task/003-jwt-tokens" \
  --cwd=".worktrees/worker-3" --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" --model="sonnet"

# Orchestrator monitors all workers through SDK message stream
```

### Example 4: Handling Errors

**Error: Worktree doesn't exist**
```bash
python -m flow_claude.scripts.launch_worker \
  --worker-id="1" --task-branch="task/001-..." \
  --cwd=".worktrees/worker-1" ...
```

**Output:**
```json
{
  "success": false,
  "error": "Worktree directory does not exist: .worktrees/worker-1"
}
```

**Solution:** Create the worktree first with `git worktree add`

**Error: Worker already running**
```bash
python -m flow_claude.scripts.launch_worker \
  --worker-id="1" --task-branch="task/001-..." \
  --cwd=".worktrees/worker-1" ...
```

**Output:**
```json
{
  "success": false,
  "error": "Worker 1 already running"
}
```

**Solution:** Use a different worker ID or wait for the current worker to complete

### Example 5: Cleaning Up Stale Worktrees

```bash
# List all worktrees
git worktree list

# If you see stale worktrees that won't remove:
git worktree remove --force .worktrees/worker-N

# If that fails, manually delete and prune:
rm -rf .worktrees/worker-N
git worktree prune
```
