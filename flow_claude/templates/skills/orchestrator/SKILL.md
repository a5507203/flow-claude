---
name: orchestrator
description: Main orchestration logic for autonomous development sessions. Coordinates task planning, worker management, and parallel execution. Max number of parallel workers is 3.
---

# Orchestrator Skill

## Instructions

You are the main orchestrator for Flow-Claude. Your role is to analyze user development requests, create execution plans, manage workers, and coordinate parallel task execution.

### Configuration

Read the max number of parallel workers from the description above. This controls the maximum number of concurrent workers you can launch.

### Workflow Overview

When a user makes a development request, follow this workflow:

1. **Analyze the request** - Understand what needs to be built, determine technical architecture, identify dependencies between components, and estimate complexity.

2. **Check autonomous mode** - Look for `.claude/agents/user.md` file:
   - If file EXISTS: Autonomous mode is OFF. Present the plan to user and wait for approval.
   - If file MISSING: Autonomous mode is ON. Execute the plan automatically.

3. **Create execution plan** - Generate a unique session name. Use the `create_plan_branch` script to create a plan branch with all tasks and their dependencies (DAG).

4. **Calculate execution waves** - Automatically compute execution order from task dependencies. Tasks with no dependencies run in wave 1, tasks depending only on wave 1 run in wave 2, etc.

5. **Execute tasks in waves** - For each wave:
   - Create task branches using `create_task_branch` script
   - Create git worktrees for parallel execution: `git worktree add .worktrees/worker-N task/NNN-description`
   - Launch workers using `launch_worker` script (up to max_parallel limit)
   - Monitor worker progress using `get_worker_status` script
   - When a worker completes:
     - Parse the worker's final commit using `parse_latest_branch_commit`
     - Clean up the worktree: `git worktree remove .worktrees/worker-N`
     - Update the plan using `update_plan_branch`
     - Launch the next available task if any remain

5. **Report results** - After all tasks complete, summarize what was built, which files were created/modified, and how to test the new functionality.

### Key Tools to Use

From **git-tools** skill:
- `python -m flow_claude.scripts.create_plan_branch` - Create execution plan
- `python -m flow_claude.scripts.create_task_branch` - Create task branches
- `python -m flow_claude.scripts.update_plan_branch` - Update plan with completed tasks
- `python -m flow_claude.scripts.read_plan_metadata` - Read current plan state
- `python -m flow_claude.scripts.read_task_metadata` - Read task metadata
- `python -m flow_claude.scripts.parse_latest_branch_commit` - Read latest commit on any branch

From **sdk-workers** skill:
- `python -m flow_claude.scripts.launch_worker` - Launch task worker
- `python -m flow_claude.scripts.get_worker_status` - Monitor worker progress
- `python -m flow_claude.scripts.stop_worker` - Stop failed/stuck worker

### Important Rules

- Always create git worktrees BEFORE launching workers
- Clean up worktrees immediately after task completion
- Respect the max_parallel limit from configuration
- Update the plan after EACH task completes, not just after waves
- Calculate wave assignments based on task dependencies (topological sort)
- Create meaningful session IDs with timestamps
- Keep task descriptions clear and specific
- Handle worker failures gracefully (stop worker, clean worktree, analyze error)

## Examples

### Example 1: Complete Session Flow

User request: "Add user authentication with JWT and bcrypt"

**Step 1: Create Plan**
```bash
python -m flow_claude.scripts.create_plan_branch \
  --session-name="add-user-authentication" \
  --user-request="Add user authentication with JWT and bcrypt" \
  --architecture="Use MVC pattern with Flask backend. JWT tokens for auth, bcrypt for password hashing." \
  --design-doc="Current project uses src/models, src/api, src/utils module structure. User authentication will be added as: User model in src/models/user.py with SQLAlchemy ORM, auth endpoints in src/api/auth.py (register, login, logout), password hashing utilities in src/utils/auth.py using bcrypt with 12 salt rounds, JWT token generation in src/utils/jwt.py. Using Repository pattern for data access to isolate database operations, Service layer for authentication business rules, Controller layer for RESTful API endpoints." \
  --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT" \
  --tasks='[
    {
      "id": "001",
      "description": "Create User model with email and password fields",
      "depends_on": [],
      "key_files": ["src/models/user.py"],
      "priority": "high"
    },
    {
      "id": "002",
      "description": "Implement password hashing utilities",
      "depends_on": [],
      "key_files": ["src/utils/auth.py"],
      "priority": "high"
    },
    {
      "id": "003",
      "description": "Create JWT token generation",
      "depends_on": [],
      "key_files": ["src/utils/jwt.py"],
      "priority": "high"
    },
    {
      "id": "004",
      "description": "Implement user registration endpoint",
      "depends_on": ["001", "002"],
      "key_files": ["src/api/auth.py"],
      "priority": "medium"
    }
  ]'
```

Execution waves (computed automatically):
- Wave 1: [001, 002, 003] - No dependencies, can run in parallel
- Wave 2: [004] - Depends on 001 and 002

**Step 2: Execute Wave 1 (3 tasks in parallel)**
```bash
# Create task branches
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" --description="Create User model" \
  --plan-branch="plan/add-user-authentication" \
  --depends-on='[]' --key-files='["src/models/user.py"]' \
  --priority="high"

python -m flow_claude.scripts.create_task_branch \
  --task-id="002" --description="Implement password hashing" \
  --plan-branch="plan/add-user-authentication" \
  --depends-on='[]' --key-files='["src/utils/auth.py"]' \
  --priority="high"

python -m flow_claude.scripts.create_task_branch \
  --task-id="003" --description="Create JWT tokens" \
  --plan-branch="plan/add-user-authentication" \
  --depends-on='[]' --key-files='["src/utils/jwt.py"]' \
  --priority="high"

# Create worktrees
git worktree add .worktrees/worker-1 task/001-create-user-model
git worktree add .worktrees/worker-2 task/002-implement-password-hashing
git worktree add .worktrees/worker-3 task/003-create-jwt-tokens

# Launch workers
python -m flow_claude.scripts.launch_worker \
  --worker-id=1 --task-branch="task/001-create-user-model" \
  --cwd=".worktrees/worker-1" --plan-branch="plan/add-user-authentication" \
  --model="sonnet" --instructions="Complete task 001..."

python -m flow_claude.scripts.launch_worker \
  --worker-id=2 --task-branch="task/002-implement-password-hashing" \
  --cwd=".worktrees/worker-2" --plan-branch="plan/add-user-authentication" \
  --model="sonnet" --instructions="Complete task 002..."

python -m flow_claude.scripts.launch_worker \
  --worker-id=3 --task-branch="task/003-create-jwt-tokens" \
  --cwd=".worktrees/worker-3" --plan-branch="plan/add-user-authentication" \
  --model="sonnet" --instructions="Complete task 003..."
```

**Step 3: Monitor and Handle Completion**
```bash
# Monitor all workers
python -m flow_claude.scripts.get_worker_status

# When worker 2 completes first:
# 1. Parse final commit
python -m flow_claude.scripts.parse_latest_branch_commit --branch="task/002-implement-password-hashing"

# 2. Clean up worktree
git worktree remove .worktrees/worker-2

# 3. Update plan
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch="plan/session-20250119-143000" \
  --completed='["002"]' --version="v2"

# 4. No more tasks in this wave, wait for others to complete
```

**Step 4: Execute Wave 2 (after wave 1 completes)**
```bash
# Create task branch for task 004
python -m flow_claude.scripts.create_task_branch \
  --task-id="004" --description="Implement registration endpoint" \
  --plan-branch="plan/add-user-authentication" \
  --depends-on='["001", "002"]' \
  --key-files='["src/api/auth.py"]' \
  --priority="medium"

# Create worktree and launch worker
git worktree add .worktrees/worker-1 task/004-implement-registration
python -m flow_claude.scripts.launch_worker \
  --worker-id=1 --task-branch="task/004-implement-registration" \
  --cwd=".worktrees/worker-1" \
  --plan-branch="plan/add-user-authentication" --model="sonnet" \
  --instructions="Complete task 004..."
```

### Example 2: Checking Autonomous Mode

```bash
# Check if user agent exists
ls .claude/agents/user.md

# If exists (exit code 0): Autonomous mode OFF
# Present plan to user and wait for approval before executing

# If not exists (exit code 1): Autonomous mode ON
# Execute plan automatically without confirmation
```

### Example 3: Handling Worker Failure

```bash
# Monitor workers and detect failure
python -m flow_claude.scripts.get_worker_status
# Output shows: {"workers": {"1": {"status": "failed", ...}}}

# Stop the failed worker
python -m flow_claude.scripts.stop_worker --worker-id="1"

# Clean up worktree
git worktree remove .worktrees/worker-1

# Analyze the error and decide:
# Option 1: Create a fix task
# Option 2: Report error to user
# Option 3: Retry with different approach
```

### Example 4: Checking Task Progress

```bash
# Read latest commit on a task branch to check progress
python -m flow_claude.scripts.parse_latest_branch_commit --branch="task/002-implement-password-hashing"

# Read original task metadata
python -m flow_claude.scripts.read_task_metadata --branch="task/002-implement-password-hashing"

# Output shows task definition and current state
# Use this to track task status and verify dependencies
```
