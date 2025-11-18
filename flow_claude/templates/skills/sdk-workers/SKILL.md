---
description: Worker management for parallel task execution
---

# SDK Workers Skill

Provides 3 tools for managing worker agents.

## Commands

### 1. launch_worker
```bash
python -m flow_claude.scripts.launch_worker \
  --worker-id=1 \
  --task-branch=task/001 \
  --cwd=.worktrees/worker-1 \
  --session-id=session-20250118-120000 \
  --plan-branch=plan/session-20250118-120000 \
  --model=sonnet \
  --instructions="..."
```

### 2. get_worker_status
```bash
python -m flow_claude.scripts.get_worker_status
python -m flow_claude.scripts.get_worker_status --worker-id=1
```

### 3. stop_worker
```bash
python -m flow_claude.scripts.stop_worker --worker-id=1
```

All commands output JSON.
