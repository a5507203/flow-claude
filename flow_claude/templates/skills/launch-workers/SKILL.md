---
name: launch-workers
description: |
  Worker management for parallel task execution. Provides the `launch_worker` command-line tool for spawning worker agents in git worktrees.

  IMPORTANT: Always run launch_worker with `run_in_background=true` using the Bash tool so workers execute in parallel without blocking.

  WORKER LIFECYCLE:
  1. Progressive commit - worker commits all progress to the task branch
  2. Completion - worker merges changes to Flow branch


  EXAMPLE - Launch single worker:
  ```
  # Create task branch
  python -m flow_claude.scripts.create_task_branch \
    --task-id="001" \
    --instruction="Create User model. Use Write tool to create src/models/user.py with SQLAlchemy model." \
    --plan-branch="plan/add-user-authentication" \
    --depends-on='[]' --key-files='["src/models/user.py"]' --priority="high"

  # Create worktree
  git worktree add .worktrees/worker-1 task/001-create-user-model

  # Launch worker in background (use Bash tool with run_in_background=true)
  Bash(
    command="python -m flow_claude.scripts.launch_worker --worker-id=1 --task-branch='task/001-create-user-model' --cwd='.worktrees/worker-1' --plan-branch='plan/add-user-authentication' --model='sonnet'",
    run_in_background=true
  )
  ```

  EXAMPLE - Launch 3 parallel workers:
  ```
  # Create worktrees
  git worktree add .worktrees/worker-1 task/001-create-user-model
  git worktree add .worktrees/worker-2 task/002-password-hashing
  git worktree add .worktrees/worker-3 task/003-jwt-tokens

  # Launch all workers in background (each with run_in_background=true)
  Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=1 --task-branch='task/001-create-user-model' --cwd='.worktrees/worker-1' --plan-branch='plan/add-user-authentication' --model='sonnet'", run_in_background=true)
  Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=2 --task-branch='task/002-password-hashing' --cwd='.worktrees/worker-2' --plan-branch='plan/add-user-authentication' --model='sonnet'", run_in_background=true)
  Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=3 --task-branch='task/003-jwt-tokens' --cwd='.worktrees/worker-3' --plan-branch='plan/add-user-authentication' --model='sonnet'", run_in_background=true)
  ```
--- 
