# Scripts Architecture - Complete

## 概述

所有功能都已拆分为独立的命令行脚本，每个脚本可以接受参数并输出 JSON。

---

## 文件结构

```
flow_claude/
├── scripts/                           # 所有可执行脚本
│   ├── __init__.py
│   ├── parsers.py                     # 共享解析函数
│   │
│   ├── parse_task.py                  # ✅ 测试通过
│   ├── parse_plan.py                  # ✅ 测试通过
│   ├── parse_worker_commit.py         # ✅ 测试通过
│   ├── get_provides.py                # ✅ 测试通过
│   ├── create_plan_branch.py          # ✅ 测试通过
│   ├── create_task_branch.py          # ✅ 测试通过
│   ├── update_plan_branch.py          # ✅ 测试通过
│   │
│   ├── launch_worker.py               # ✅ 测试通过
│   ├── get_worker_status.py           # ✅ 测试通过
│   └── stop_worker.py                 # ✅ 测试通过
│
└── templates/
    └── skills/
        ├── git-tools/
        │   └── SKILL.md               # ✅ 简洁的命令参考
        ├── sdk-workers/
        │   └── SKILL.md               # ✅ 简洁的命令参考
        └── orchestrator/
            └── SKILL.md               # ✅ 工作流说明
```

---

## 脚本列表

### Git Tools (7 个脚本)

#### 1. parse_task
解析任务元数据

```bash
python -m flow_claude.scripts.parse_task --branch=task/001-description
```

**输出**:
```json
{
  "success": true,
  "branch": "task/001-description",
  "id": "001",
  "description": "Create User model",
  "status": "pending",
  "preconditions": [],
  "provides": ["User model class"],
  "files": ["src/models/user.py"]
}
```

#### 2. parse_plan
解析执行计划

```bash
python -m flow_claude.scripts.parse_plan --branch=plan/session-20250118-120000
```

#### 3. parse_worker_commit
解析 worker 进度

```bash
python -m flow_claude.scripts.parse_worker_commit --branch=task/001-description
```

#### 4. get_provides
查询可用能力

```bash
python -m flow_claude.scripts.get_provides
```

#### 5. create_plan_branch
创建计划分支

```bash
python -m flow_claude.scripts.create_plan_branch \
  --session-id=session-20250118-120000 \
  --user-request="Add authentication" \
  --architecture="Use JWT..." \
  --tasks='[{"id":"001", "description":"...", ...}]'
```

#### 6. create_task_branch
创建任务分支

```bash
python -m flow_claude.scripts.create_task_branch \
  --task-id=001 \
  --description="Create User model" \
  --session-id=session-20250118-120000 \
  --plan-branch=plan/session-20250118-120000 \
  --preconditions='[]' \
  --provides='["User model"]' \
  --files='["src/models/user.py"]'
```

#### 7. update_plan_branch
更新计划分支

```bash
python -m flow_claude.scripts.update_plan_branch \
  --plan-branch=plan/session-20250118-120000 \
  --completed='["001", "002"]' \
  --new-tasks='[...]' \
  --version=v2
```

---

### SDK Workers (3 个脚本)

#### 1. launch_worker
启动 worker

```bash
python -m flow_claude.scripts.launch_worker \
  --worker-id=1 \
  --task-branch=task/001-description \
  --cwd=.worktrees/worker-1 \
  --session-id=session-20250118-120000 \
  --plan-branch=plan/session-20250118-120000 \
  --model=sonnet \
  --instructions="Execute task 001..."
```

#### 2. get_worker_status
查询 worker 状态

```bash
# 所有 workers
python -m flow_claude.scripts.get_worker_status

# 特定 worker
python -m flow_claude.scripts.get_worker_status --worker-id=1
```

#### 3. stop_worker
停止 worker

```bash
python -m flow_claude.scripts.stop_worker --worker-id=1
```

---

## 测试结果

```bash
✓ parse_task OK
✓ parse_plan OK
✓ parse_worker_commit OK
✓ get_provides OK
✓ create_plan_branch OK
✓ create_task_branch OK
✓ update_plan_branch OK
✓ launch_worker OK
✓ get_worker_status OK
✓ stop_worker OK
```

**10/10 脚本全部测试通过！**

---

## SKILL.md 模板

### git-tools/SKILL.md

```markdown
---
description: Git-based state management for Flow-Claude
---

# Git Tools Skill

Provides 7 command-line tools for managing execution plans and tasks.

## Available Commands

### 1. parse_task
```bash
python -m flow_claude.scripts.parse_task --branch=task/001-description
```

(其他 6 个命令...)
```

### sdk-workers/SKILL.md

```markdown
---
description: Worker management for parallel task execution
---

# SDK Workers Skill

Provides 3 tools for managing worker agents.

## Commands

### 1. launch_worker
```bash
python -m flow_claude.scripts.launch_worker ...
```

(其他 2 个命令...)
```

### orchestrator/SKILL.md

```markdown
---
max_parallel: 3
description: Main orchestration logic
---

# Orchestrator Skill

Coordinates autonomous development using git-tools and sdk-workers.

## Workflow

1. Analyze request
2. Check `.claude/agents/user.md` (exists = need confirmation)
3. Create plan: `python -m flow_claude.scripts.create_plan_branch ...`
4. Create tasks: `python -m flow_claude.scripts.create_task_branch ...`
5. Launch workers: `python -m flow_claude.scripts.launch_worker ...`
6. Monitor: `python -m flow_claude.scripts.get_worker_status`
7. Report results
```

---

## 技术细节

### Import 处理

所有脚本都使用 try/except 来处理相对导入：

```python
try:
    from .parsers import parse_task_metadata
except ImportError:
    from parsers import parse_task_metadata
```

这样既可以作为模块运行（`python -m flow_claude.scripts.xxx`），也可以直接运行。

### JSON 输出

所有脚本都输出标准 JSON 格式：

```json
{
  "success": true,
  ...
}
```

错误时：

```json
{
  "error": "Error message",
  "success": false
}
```

### 命令行参数

使用 `argparse` 提供友好的帮助信息：

```bash
python -m flow_claude.scripts.parse_task --help
```

---

## flow 初始化行为

运行 `flow` 命令时：

1. 创建 `.claude/skills/` 目录
2. 复制 `SKILL.md` 到每个 skill 目录
3. Scripts 在包内（`flow_claude/scripts/`），全局可用
4. 用户通过 `python -m flow_claude.scripts.xxx` 调用

---

## 使用示例

### 在 Claude Code UI 中调用

Orchestrator skill 可以直接运行这些命令：

```python
import subprocess
import json

# 解析任务
result = subprocess.run(
    ['python', '-m', 'flow_claude.scripts.parse_task', '--branch=task/001'],
    capture_output=True,
    text=True
)
task_data = json.loads(result.stdout)

# 创建计划
result = subprocess.run(
    ['python', '-m', 'flow_claude.scripts.create_plan_branch',
     '--session-id=session-123',
     '--user-request=Add auth',
     '--architecture=Use JWT',
     '--tasks={"id":"001", ...}'],
    capture_output=True,
    text=True
)
```

---

## 状态

✅ **完成**: Scripts 架构重新设计
✅ **测试**: 10/10 脚本可执行
✅ **文档**: SKILL.md 模板简洁清晰
✅ **集成**: flow_cli.py 正确复制文件

**准备就绪！**
