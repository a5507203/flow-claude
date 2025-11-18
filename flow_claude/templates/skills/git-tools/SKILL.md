---
name: git-tools
description: Git-based state management. Provides 7 command-line tools for managing execution plans and tasks using structured git commits.
---

# Git Tools Skill

## Instructions

This skill provides 7 command-line tools for managing Flow-Claude execution plans and tasks through structured git commits. All commands output JSON with a `success` field indicating whether the operation succeeded.

### Available Commands

**Planning Commands:**
- `create_plan_branch` - Create a new execution plan with all tasks and waves
- `parse_plan` - Read and parse an existing execution plan
- `update_plan_branch` - Update plan with completed tasks and new discoveries

**Task Commands:**
- `create_task_branch` - Create a task branch with metadata
- `parse_task` - Read task metadata from a task branch
- `parse_worker_commit` - Check worker's progress on a task

**Query Commands:**
- `get_provides` - Query what capabilities completed tasks have provided

### Command Usage Patterns

**When to use each command:**

- Use `create_plan_branch` at the start of a new development session after analyzing the user request
- Use `create_task_branch` before launching a worker for each task in the current wave
- Use `parse_task` to read task requirements before or after worker execution
- Use `parse_plan` to understand the overall plan structure and track progress
- Use `parse_worker_commit` to monitor worker progress during execution
- Use `update_plan_branch` after each task completes to mark it done and update the plan version
- Use `get_provides` before creating dependent tasks to verify preconditions are met

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
  --session-id="session-20250119-143000" \
  --user-request="Add user authentication with JWT and bcrypt" \
  --architecture="Use MVC pattern with Flask backend. JWT tokens for auth, bcrypt for password hashing. RESTful API endpoints." \
  --design-doc="Current project uses src/models, src/api, src/utils module structure. User authentication will be added as: User model in src/models/user.py with SQLAlchemy ORM, auth endpoints in src/api/auth.py (register, login, logout), password hashing utilities in src/utils/auth.py using bcrypt with 12 salt rounds, JWT token generation in src/utils/jwt.py. Using Repository pattern for data access to isolate database operations, Service layer for authentication business rules including password validation and token generation, Controller layer for RESTful API endpoints." \
  --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT" \
  --tasks='[
    {
      "id": "001",
      "description": "Create User model with email and password fields",
      "preconditions": [],
      "provides": ["User model", "User.email field", "User.password_hash field"],
      "files": ["src/models/user.py"],
      "estimated_time": "8 minutes",
      "priority": "high"
    },
    {
      "id": "002",
      "description": "Implement password hashing utilities",
      "preconditions": [],
      "provides": ["hash_password function", "verify_password function"],
      "files": ["src/utils/auth.py"],
      "estimated_time": "5 minutes",
      "priority": "high"
    },
    {
      "id": "003",
      "description": "Implement user login endpoint",
      "preconditions": ["User model", "hash_password function"],
      "provides": ["POST /api/login endpoint"],
      "files": ["src/api/auth.py"],
      "estimated_time": "12 minutes",
      "priority": "medium"
    }
  ]' \
  --waves='[
    {"wave": 1, "tasks": ["001", "002"], "reason": "No dependencies - can run in parallel"},
    {"wave": 2, "tasks": ["003"], "reason": "Depends on User model and hash_password"}
  ]'
```

**Output:**
```json
{
  "success": true,
  "branch": "plan/session-20250119-143000",
  "session_id": "session-20250119-143000"
}
```

### Example 2: Creating a Task Branch

```bash
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" \
  --description="Create User model with email and password fields" \
  --session-id="session-20250119-143000" \
  --plan-branch="plan/session-20250119-143000" \
  --preconditions='[]' \
  --provides='["User model", "User.email field", "User.password_hash field"]' \
  --files='["src/models/user.py"]' \
  --estimated-time="8 minutes" \
  --priority="high"
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "task_id": "001"
}
```

### Example 3: Parsing Task Metadata

```bash
python -m flow_claude.scripts.parse_task --branch="task/001-create-user-model"
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "task_id": "001",
  "description": "Create User model with email and password fields",
  "status": "pending",
  "preconditions": [],
  "provides": [
    "User model",
    "User.email field",
    "User.password_hash field"
  ],
  "files": ["src/models/user.py"],
  "session_id": "session-20250119-143000",
  "plan_branch": "plan/session-20250119-143000",
  "plan_version": "v1",
  "depends_on": [],
  "enables": ["003"],
  "estimated_time": "8 minutes",
  "priority": "high"
}
```

### Example 4: Updating Plan After Task Completion

```bash
# After task 001 completes, update the plan
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch="plan/session-20250119-143000" \
  --completed='["001"]' \
  --new-tasks='[]' \
  --version="v2"
```

**Output:**
```json
{
  "success": true,
  "plan_version": "v2",
  "completed_count": 1,
  "new_tasks_count": 0,
  "branch": "plan/session-20250119-143000"
}
```

### Example 5: Querying Available Capabilities

```bash
# Check what capabilities are available from completed tasks
python -m flow_claude.scripts.get_provides
```

**Output:**
```json
{
  "success": true,
  "provides": [
    "User model",
    "User.email field",
    "User.password_hash field",
    "hash_password function",
    "verify_password function"
  ],
  "tasks_scanned": 2,
  "branch": "flow"
}
```

This tells you that tasks providing these capabilities have been completed and merged to the flow branch.

### Example 6: Parsing a Plan

```bash
python -m flow_claude.scripts.parse_plan --branch="plan/session-20250119-143000"
```

**Output:**
```json
{
  "success": true,
  "branch": "plan/session-20250119-143000",
  "session_id": "session-20250119-143000",
  "user_request": "Add user authentication with JWT and bcrypt",
  "plan_version": "v2",
  "architecture": "Use MVC pattern with Flask backend...",
  "design_doc": "Current project uses src/models, src/api, src/utils module structure. User authentication will be added as: User model in src/models/user.py with SQLAlchemy ORM, auth endpoints in src/api/auth.py...",
  "tech_stack": "Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT",
  "tasks": [
    {"id": "001", "description": "Create User model...", ...},
    {"id": "002", "description": "Implement password hashing...", ...},
    {"id": "003", "description": "Implement user login...", ...}
  ],
  "waves": [
    {"wave": 1, "tasks": ["001", "002"], "reason": "No dependencies"},
    {"wave": 2, "tasks": ["003"], "reason": "Depends on User model"}
  ],
  "estimated_total": "25 minutes",
  "completed_tasks": ["001"]
}
```

### Example 7: Checking Worker Progress

```bash
python -m flow_claude.scripts.parse_worker_commit --branch="task/001-create-user-model"
```

**Output:**
```json
{
  "success": true,
  "branch": "task/001-create-user-model",
  "task_id": "001",
  "status": "in_progress",
  "design": "Created SQLAlchemy model with User table. Fields: id (primary key), email (unique, indexed), password_hash (bcrypt).",
  "todo": [
    {"item": "Write model class", "status": "completed"},
    {"item": "Add email validation", "status": "in_progress"},
    {"item": "Write unit tests", "status": "pending"}
  ],
  "progress": "66%",
  "last_updated": "2025-01-19T14:32:15Z"
}
```

### Example 8: Common Workflow Sequence

```bash
# 1. Create plan
python -m flow_claude.scripts.create_plan_branch --session-id="session-20250119-143000" --tasks='[...]'

# 2. Create task branches for wave 1
python -m flow_claude.scripts.create_task_branch --task-id="001" ...
python -m flow_claude.scripts.create_task_branch --task-id="002" ...

# 3. After task 001 completes, update plan
python -m flow_claude.scripts.update_plan_branch --completed='["001"]' --version="v2"

# 4. Check what's available
python -m flow_claude.scripts.get_provides

# 5. Parse plan to see current state
python -m flow_claude.scripts.parse_plan --branch="plan/session-20250119-143000"
```

### Example 9: Handling Errors

```bash
# Try to create a plan branch that already exists
python -m flow_claude.scripts.create_plan_branch --session-id="session-20250119-143000" ...
```

**Error Output:**
```json
{
  "success": false,
  "error": "Branch plan/session-20250119-143000 already exists"
}
```

Always check the `success` field before processing the output.
