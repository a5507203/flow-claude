# Planner.md MCP Tool Updates

This document shows the key workflow changes to use new MCP tools instead of manual git commands.

## Phase 1: Initial Plan Creation

### OLD Step 2 (Manual Git Commands):
```bash
git checkout -b plan/session-20250106-140530
git commit --allow-empty -m "[long commit message]"
git checkout main
```

### NEW Step 2 (MCP Tool):
```python
result = mcp__git__create_plan_branch({
    "session_id": "session-20250106-140530",
    "user_request": "Add user authentication with email/password",
    "architecture": "MVC architecture with Flask backend...",
    "design_patterns": "Repository Pattern...",
    "technology_stack": "Python 3.10, Flask 2.3...",
    "tasks": [
        {
            "id": "001",
            "description": "Create User model with email and password fields",
            "status": "pending",
            "preconditions": [],
            "provides": ["User model class (models.user.User)", ...],
            "files": ["models/user.py", "tests/test_user_model.py"],
            "estimated_time": "8 minutes",
            "priority": "high"
        },
        # ... more tasks
    ],
    "estimated_total_time": "45 minutes",
    "dependency_graph": "Wave 1: task-001\nWave 2: task-002..."
})
```

**Benefits:**
- ✅ Instruction files automatically copied
- ✅ Format guaranteed correct
- ✅ Atomic operation
- ✅ 5 git commands → 1 MCP call

---

### OLD Step 4 (Manual Task Branch Creation):
```bash
git checkout main
git checkout -b task/001-user-model
git commit --allow-empty -m "[task metadata]"
git checkout main
```

### NEW Step 4 (MCP Tool):
```python
result = mcp__git__create_task_branch({
    "task_id": "001",
    "branch_slug": "user-model",
    "description": "Create User model with email and password fields",
    "preconditions": [],
    "provides": [
        "User model class (models.user.User)",
        "User.email field (unique, indexed)",
        "User.password_hash field",
        "User.set_password(password) method",
        "User.verify_password(password) method"
    ],
    "files": ["models/user.py", "tests/test_user_model.py"],
    "session_goal": "Add user authentication with email/password",
    "session_id": "session-20250106-140530",
    "plan_branch": "plan/session-20250106-140530",
    "plan_version": "v1",
    "depends_on": [],
    "enables": ["task-002"],
    "parallel_with": [],
    "completed_tasks": [],
    "estimated_time": "8 minutes",
    "priority": "high"
})
```

**Benefits:**
- ✅ Instruction files automatically copied
- ✅ All metadata fields guaranteed
- ✅ 4 git commands → 1 MCP call

---

## Phase 2: Update Plan & Create Next Wave

### OLD Step 2 (Manual Plan Update):
```bash
git checkout plan/session-20250106-140530
git commit --allow-empty -m "Update plan: Wave 1 complete
[full updated plan with all tasks, some marked completed]
"
git checkout main
```

### NEW Step 2 (MCP Tool):
```python
result = mcp__git__update_plan_branch({
    "plan_branch": "plan/session-20250106-140530",
    "completed_task_ids": ["001"],
    "new_tasks": [
        # New tasks for Wave 2+ if any
    ],
    "architecture_updates": """User model implemented with bcrypt cost factor 12
Email field uses SQLAlchemy unique constraint + index
password_hash stored using bcrypt, never plain password"""
})

# Returns:
# {
#   "success": true,
#   "plan_version": "v2",
#   "commit_sha": "def456...",
#   "total_tasks": 5,
#   "completed_tasks": 1
# }
```

**Benefits:**
- ✅ Automatically marks tasks complete
- ✅ Appends architecture learnings
- ✅ Auto-increments version (v1→v2→v3)
- ✅ Preserves all existing metadata
- ✅ 3 git commands → 1 MCP call

---

### NEW Step 4 (Same as Phase 1):
Use `mcp__git__create_task_branch` for Wave N tasks (same format as Phase 1 Step 4)

---

## Key Sections to Update in planner.md

1. **Lines ~663-807**: Phase 1 Step 2 - Replace git workflow with `mcp__git__create_plan_branch`
2. **Lines ~816-865**: Phase 1 Step 4 - Replace git workflow with `mcp__git__create_task_branch`
3. **Lines ~927-1025**: Phase 2 Step 2 - Replace git workflow with `mcp__git__update_plan_branch`
4. **Lines ~1047-1095**: Phase 2 Step 4 - Replace git workflow with `mcp__git__create_task_branch`
5. **Lines ~475-487**: Git Branch Structure section - Add note about MCP tools
6. **Lines ~512-525**: Task Branches workflow - Add note about MCP tools

---

## Summary of Changes

**Before (Manual Git):**
- Plan branch: 5 git commands
- Task branch: 4 git commands
- Plan update: 3 git commands
- Total per wave: ~5 + (4 × num_tasks) + 3 commands

**After (MCP Tools):**
- Plan branch: 1 MCP call
- Task branch: 1 MCP call
- Plan update: 1 MCP call
- Total per wave: ~1 + num_tasks + 1 calls

**Performance improvement:** 5-10x fewer tool calls per wave
**Reliability improvement:** Instruction files and metadata format guaranteed
