---
description: Git-based state management for Flow-Claude
---

# Git Tools Skill

Provides 7 command-line tools for managing execution plans and tasks using structured git commits.

## Available Commands

### 1. parse_task
```bash
python -m flow_claude.scripts.parse_task --branch=task/001-description
```

### 2. parse_plan
```bash
python -m flow_claude.scripts.parse_plan --branch=plan/session-20250118-120000
```

### 3. get_provides
```bash
python -m flow_claude.scripts.get_provides
```

### 4. parse_worker_commit
```bash
python -m flow_claude.scripts.parse_worker_commit --branch=task/001-description
```

### 5. create_plan_branch
```bash
python -m flow_claude.scripts.create_plan_branch \
  --session-id=session-20250118-120000 \
  --user-request="Add user authentication" \
  --architecture="Use JWT tokens..." \
  --tasks='[...]'
```

### 6. create_task_branch
```bash
python -m flow_claude.scripts.create_task_branch \
  --task-id=001 \
  --description="Create User model" \
  --session-id=session-20250118-120000 \
  --plan-branch=plan/session-20250118-120000 \
  --preconditions='[]' \
  --provides='[]' \
  --files='[]'
```

### 7. update_plan_branch
```bash
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch=plan/session-20250118-120000 \
  --completed='["001"]' \
  --new-tasks='[...]' \
  --version=v2
```

All commands output JSON.
