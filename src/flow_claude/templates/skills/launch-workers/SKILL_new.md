---
name: launch-workers
description: |
  Worker management for parallel task execution. Provides the `launch_worker` command-line tool for spawning worker agents in git worktrees.

  IMPORTANT: Always run launch_worker with `run_in_background=true` using the Bash tool so workers execute in parallel without blocking, the timeout should be 60 mins for safety.

  WORKER LIFECYCLE:
  1. Progressive commit - worker commits all progress to the task branch
  2. Completion - worker merges changes to Flow branch
---

# Launch Workers Skill

## All Contents

### Overview

This skill provides worker management for parallel task execution using the `launch_worker` command-line tool for spawning worker agents in git worktrees.

**IMPORTANT**: Always run launch_worker with `run_in_background=true` using the Bash tool so workers execute in parallel without blocking. The timeout should be 60 mins for safety.

**Worker Lifecycle**:
1. Progressive commit - worker commits all progress to the task branch
2. Completion - worker merges changes to Flow branch

### Example: Launch Single Worker (~10 minute task)

```bash
# Create task branch for self-contained feature
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" \
  --instruction="Build user registration endpoint with validation. Use Write tool to create: 1) src/api/register.py with POST /api/register endpoint (accept email/password, validate email format, check password strength, hash password with bcrypt), 2) tests/test_register.py with tests for valid registration, duplicate email, weak password, invalid email format. Use Read tool to check existing src/models/user.py and src/utils/validation.py. Return proper JSON responses with 201 for success, 400 for validation errors. Estimated time: 10 minutes." \
  --plan-branch="plan/add-user-features" \
  --depends-on='[]' \
  --context-paths='[]'

# Create worktree
git worktree add .worktrees/worker-1 task/001-build-registration-endpoint


#Launch skill_manager

python -m flow_claude.scripts.launch_skills_manager\
--plan-branch="plan/add-user-features" \
--tasks='[
  {"task_branch": "task/001-build-registration-endpoint", "worker_path": ".worktrees/worker-1", "worker_id": "1"}
]'

# After seeing line: {"success": true, "task_branch": "task/001-build-registration-endpoint", ...}

# Launch worker in background (use Bash tool with run_in_background=true)
Bash(
  command="python -m flow_claude.scripts.launch_worker --worker-id=1 --task-branch='task/001-build-registration-endpoint' --cwd='.worktrees/worker-1' --plan-branch='plan/add-user-features' --model='sonnet'",
  run_in_background=true
)
```

### Example: Launch 3 Parallel Workers (each ~10 min, self-contained, independent)

```bash
# Task 001: Self-contained login endpoint (no dependencies on other tasks)
python -m flow_claude.scripts.create_task_branch --task-id="001" --instruction="Create login endpoint. Use Write tool to create src/api/login.py with POST /api/login endpoint that accepts email/password, validates credentials against database, generates JWT token on success, returns token with 200 or error with 401. Use Read tool to check existing src/models/user.py for User model and src/utils/jwt.py for token generation. Write tests/test_login.py with tests for valid login, invalid password, non-existent user. ~10 minutes." --plan-branch="plan/add-user-features" --depends-on='[]' --context-paths='[]'

# Task 002: Self-contained profile endpoint (independent from login/register)
python -m flow_claude.scripts.create_task_branch --task-id="002" --instruction="Create user profile endpoints. Use Write tool to create src/api/profile.py with GET /api/profile/:id to fetch user data and PUT /api/profile/:id to update user profile (name, bio, avatar_url). Add authentication check using existing JWT middleware. Use Read tool to check src/models/user.py. Write tests/test_profile.py with tests for get profile, update profile, unauthorized access. ~10 minutes." --plan-branch="plan/add-user-features" --depends-on='[]' --context-paths='[]'

# Task 003: Self-contained password reset (independent from other auth features)
python -m flow_claude.scripts.create_task_branch --task-id="003" --instruction="Create password reset flow. Use Write tool to create src/api/password_reset.py with POST /api/password-reset/request (send reset email with token) and POST /api/password-reset/confirm (verify token and update password). Use Read tool to check existing src/services/email.py for sending emails and src/models/user.py. Write tests/test_password_reset.py with tests for request reset, invalid email, confirm reset, expired token. ~10 minutes." --plan-branch="plan/add-user-features" --depends-on='[]' --context-paths='[]'

# Create worktrees
git worktree add .worktrees/worker-1 task/001-create-login-endpoint
git worktree add .worktrees/worker-2 task/002-create-profile-endpoints
git worktree add .worktrees/worker-3 task/003-create-password-reset-flow


#Launch skill_manager
python -m flow_claude.scripts.launch_skills_manager\
  --plan-branch="plan/add-user-authentication" \
  --tasks='[
    {"task_branch": "task/001-create-login-endpoint", "worker_path": ".worktrees/worker-1", "worker_id": "1"},
    {"task_branch": "task/002-create-profile-endpoints", "worker_path": ".worktrees/worker-2", "worker_id": "2"},
    {"task_branch": "task/003-create-password-reset-flow", "worker_path": ".worktrees/worker-3", "worker_id": "3"}
  ]'


Output format example (NDJSON - one JSON per line):
{"success": true, "task_branch": "task/001-create-login-endpoint", "worker_path": ".worktrees/worker-1", "worker_id": "1", ...}
{"success": true, "task_branch": "task/002-create-profile-endpoints", "worker_path": ".worktrees/worker-2", "worker_id": "2", ...}
{"success": false, "task_branch": "task/003-create-password-reset-flow", "error": "...", "worker_id": "3"}

# Launch workers in parallel once skill_files are created - each task is self-contained and independent
After seeing line: {"success": true, "task_branch": "task/001-create-login-endpoint", ...}
Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=1 --task-branch='task/001-create-login-endpoint' --cwd='.worktrees/worker-1' --plan-branch='plan/add-user-features' --model='sonnet'", run_in_background=true)

After seeing line: {"success": true, "task_branch": "task/create-profile-endpoints", ...}
Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=2 --task-branch='task/002-create-profile-endpoints' --cwd='.worktrees/worker-2' --plan-branch='plan/add-user-features' --model='sonnet'", run_in_background=true)

After seeing line: {"success": true, "task_branch": "task/create-password-reset-flow", ...}
Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=3 --task-branch='task/003-create-password-reset-flow' --cwd='.worktrees/worker-3' --plan-branch='plan/add-user-features' --model='sonnet'", run_in_background=true)
```