---
name: your-workflow
description: |
  Main workflow for Flow-Claude autonomous development sessions. Analyzes user requests, creates execution plans, manages workers, and coordinates parallel task execution. Max parallel workers: 3.


  YOUR GENERAL WORKFLOW:
  1. **Initial Planning:** Analyze user request → design execution plan with all tasks
  2. **Check autonomous mode:** If User subagent EXISTS: present plan & wait for approval. If MISSING: execute automatically
  3. **Create Plan Branch:** Call `create_plan_branch` (stores plan, not task branches)
  4. **Start Initial Tasks:**
    - Identify ready tasks (depends_on = [])
    - For each ready task (up to max_parallel):
      - Create task branch via `create_task_branch`
      - Create worktree via `git worktree add .worktrees/worker-N task/NNN-description`
      - Spawn worker in parallel via `launch_worker` with run_in_background=true
  5. **Monitor & Schedule Loop:** When ANY worker completes:
    - **Immediately verify:**
      - Parse latest commit status via `parse_branch_latest_commit`
      - **READ ACTUAL CODE** from flow branch to verify implementation (don't just trust commit)
      - Check all key_files are actually implemented in merged code
    - **Immediately cleanup:** Remove worktree via `git worktree remove .worktrees/worker-N`
    - **Immediately update:** Mark task complete via `update_plan_branch`
    - **Check next available tasks:** Find newly-ready tasks (all depends_on completed)
    - **Immediately launch:** If idle workers + ready tasks exist:
      - Create task branch via `create_task_branch`
      - Create worktree via `git worktree add`
      - Spawn worker via `launch_worker` with run_in_background=true
  6. **Repeat:** Continue step 5 until all tasks complete
  7. **Final Report:** Generate session summary


  COMMANDS (git-tools):
  - `python -m flow_claude.scripts.create_plan_branch` - Create execution plan
  - `python -m flow_claude.scripts.create_task_branch` - Create task branches
  - `python -m flow_claude.scripts.update_plan_branch` - Update plan with completed tasks
  - `python -m flow_claude.scripts.read_plan_metadata` - Read current plan state
  - `python -m flow_claude.scripts.read_task_metadata` - Read task metadata
  - `python -m flow_claude.scripts.parse_branch_latest_commit` - Read latest commit on any branch

  COMMANDS (launch-workers):
  - `python -m flow_claude.scripts.launch_worker` - Launch task worker


  EXAMPLE - user request: "Add user authentication":
  ```
  # 1. Create execution plan
  python -m flow_claude.scripts.create_plan_branch \
    --session-name="add-user-authentication" \
    --user-request="Add user authentication with JWT and bcrypt" \
    --design-doc="..." --tech-stack="Python 3.10, Flask, SQLAlchemy, bcrypt, PyJWT" \
    --tasks='[{"id":"001","description":"Create User model","depends_on":[],"key_files":["src/models/user.py"],"priority":"high"},...]'

  # 2. Execute ready 3 parallel tasks
  python -m flow_claude.scripts.create_task_branch --task-id="001" --instruction="..." --plan-branch="plan/add-user-authentication" ...
  git worktree add .worktrees/worker-1 task/001-create-user-model
  Bash(command="python -m flow_claude.scripts.launch_worker --worker-id=1 --task-branch='task/001-create-user-model' --cwd='.worktrees/worker-1' --plan-branch='plan/add-user-authentication' --model='sonnet'", run_in_background=true)
  # (repeat for workers 2 and 3 with run_in_background=true)

  # 3. Handle completion (when worker completes)
  python -m flow_claude.scripts.parse_branch_latest_commit --branch="task/001-create-user-model"
  git worktree remove .worktrees/worker-1
  python -m flow_claude.scripts.update_plan_branch --plan-branch="plan/add-user-authentication" --completed='["001"]' --version="v2"
  ```

---
