---
name: git-tools
description: Git-based state management. Provides 6 command-line tools for managing execution plans and tasks using structured git commits.
---

# Git Tools Skill

## Instructions

This skill provides 6 command-line tools for managing Flow-Claude execution plans and tasks through structured git commits. All commands output JSON with a `success` field indicating whether the operation succeeded.

### Available Commands

**Planning Commands:**
- `create_plan_branch` - Create a new execution plan with all tasks and dependencies (DAG)
- `read_plan_metadata` - Read execution plan from latest commit
- `update_plan_branch` - Update plan with completed tasks and status changes

**Task Commands:**
- `create_task_branch` - Create a task branch with metadata
- `read_task_metadata` - Read task metadata from first commit on task branch
- `parse_branch_latest_commit` - Read latest commit message from any branch

### Command Usage Patterns

**When to use each command:**

- Use `create_plan_branch` at the start of a new development session after analyzing the user request
- Use `create_task_branch` before launching a worker for each task in the current wave
- Use `read_task_metadata` to read task requirements before or after worker execution
- Use `read_plan_metadata` to understand the overall plan structure and track progress
- Use `parse_branch_latest_commit` to monitor worker progress during execution
- Use `update_plan_branch` after each task completes to mark it done and update the plan version

### General Command Format

All commands follow this pattern:
```bash
python -m flow_claude.scripts.COMMAND_NAME --arg1=value1 --arg2=value2 ...
```

Arguments with JSON values must be properly quoted and escaped.

### Output Format

All commands return JSON with at minimum a `success` field:
- Success: `{"success": true, ...other data...}`
- Failure: `{"success": false, "error": "error message"}`

## Examples

### Example 1: Creating a Plan

```bash
python -m flow_claude.scripts.create_plan_branch \
  --session-name="add-user-authentication" \
  --user-request="Add user authentication with JWT and bcrypt" \
  --tasks='[
    {
      "id": "001",
      "description": "Create User model with email and password fields",
      "depends_on": []
    },
    {
      "id": "002",
      "description": "Implement password hashing utilities",
      "depends_on": []
    },
    {
      "id": "003",
      "description": "Implement user login endpoint",
      "depends_on": ["001", "002"]
    }
  ]' \
  --design-doc="Current project uses src/models, src/api, src/utils module structure. User authentication will be added as: User model in src/models/user.py with SQLAlchemy ORM, auth endpoints in src/api/auth.py (register, login, logout), password hashing utilities in src/utils/auth.py using bcrypt with 12 salt rounds, JWT token generation in src/utils/jwt.py. Using Repository pattern for data access to isolate database operations, Service layer for authentication business rules including password validation and token generation, Controller layer for RESTful API endpoints." \
  --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT"
```

**Output:**
```json
{
  "success": true,
  "branch": "plan/add-user-authentication",
  "session_name": "add-user-authentication"
}
```

### Example 2: Creating a Task Branch

```bash
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" \
  --instruction="Create User model with email and password fields" \
  --plan-branch="plan/add-user-authentication" \
  --depends-on='[]' \
  --context-paths='[]'
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "task_id": "001"
}
```

### Example 3: Reading Task Metadata

```bash
python -m flow_claude.scripts.read_task_metadata --branch="task/001-create-user-model"
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "message": "Initialize task/001-create-user-model\n\n## Task Metadata\nID: 001\nInstruction: Create User model with email and password fields\nStatus: pending\n\n## Context\nSession ID: add-user-authentication\nPlan Branch: plan/add-user-authentication"
}
```

### Example 4: Updating Plan After Task Completion

```bash
# After task 001 completes, update the plan with all tasks and their current status
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch="plan/add-user-authentication" \
  --user-request="Add user authentication with JWT and bcrypt" \
  --design-doc="User model in src/models/user.py, auth endpoints in src/api/auth.py, password hashing in src/utils/auth.py" \
  --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT" \
  --tasks='[
    {"id":"001","description":"Create User model","depends_on":[],"status":"completed"},
    {"id":"002","description":"Implement password hashing","depends_on":[],"status":"in_progress"},
    {"id":"003","description":"Implement login endpoint","depends_on":["001","002"],"status":"pending"}
  ]' \
  --version="v2"
```

**Output:**
```json
{
  "success": true,
  "plan_branch": "plan/add-user-authentication",
  "version": "v2",
  "total_tasks": 3,
  "completed": 1,
  "in_progress": 1,
  "pending": 1
}
```

### Example 5: Reading Plan Metadata

```bash
python -m flow_claude.scripts.read_plan_metadata --branch="plan/add-user-authentication"
```

**Output:**
```json
{
  "success": true,
  "branch": "plan/add-user-authentication",
  "message": "Initialize execution plan v1\n\n## Session Information\nSession name: add-user-authentication\nUser Request: Add user authentication with JWT and bcrypt\nPlan Version: v1\n\n## Design Doc\nCurrent project uses src/models, src/api, src/utils module structure...\n\n## Technology Stack\nPython 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT\n\n## Tasks\n### Task 001\nID: 001\nDescription: Create User model with email and password fields\nDepends on: None\n\n### Task 002\nID: 002\nDescription: Implement password hashing utilities\nDepends on: None\n\n### Task 003\nID: 003\nDescription: Implement user login endpoint\nDepends on: 001, 002"
}
```

### Example 7: Checking Worker Progress

```bash
python -m flow_claude.scripts.parse_branch_latest_commit --branch="task/001-create-user-model"
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "message": "Update task progress\n\nTask ID: 001\nStatus: in_progress\n\nCompleted:\n- Created SQLAlchemy model with User table\n- Added email validation\n\nIn Progress:\n- Writing unit tests"
}
```

### Example 8: Common Workflow Sequence

```bash
# 1. Create plan
python -m flow_claude.scripts.create_plan_branch --session-name="session-20250119-143000" --user-request="..." --design-doc="..." --tech-stack="..." --tasks='[...]'

# 2. Create task branches for wave 1
python -m flow_claude.scripts.create_task_branch --task-id="001" --instruction="..." --plan-branch="plan/..." --depends-on='[]' --context-paths='[]'
python -m flow_claude.scripts.create_task_branch --task-id="002" --instruction="..." --plan-branch="plan/..." --depends-on='[]' --context-paths='[]'

# 3. After task 001 completes, update plan with all tasks
python -m flow_claude.scripts.update_plan_branch --plan-branch="plan/add-user-authentication" --user-request="..." --design-doc="..." --tech-stack="..." --tasks='[{"id":"001",...,"status":"completed"},...]' --version="v2"

# 4. Read plan to see current state
python -m flow_claude.scripts.read_plan_metadata --branch="plan/add-user-authentication"

# 5. Check latest commit on task branch
python -m flow_claude.scripts.parse_branch_latest_commit --branch="task/001-create-user-model"
```

### Example 9: Handling Errors

```bash
# Try to create a plan branch that already exists
python -m flow_claude.scripts.create_plan_branch --session-name="add-user-authentication" ...
```

**Error Output:**
```json
{
  "success": false,
  "error": "Branch plan/session-20250119-143000 already exists"
}
```

Always check the `success` field before processing the output.
