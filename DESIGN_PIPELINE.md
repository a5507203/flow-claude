# Flow-Claude: Design Pipeline & Workflow

## 1. Architecture Overview

Flow-Claude is a **Git-driven autonomous development system** that executes complex development tasks through parallel Worker agents coordinated by an intelligent Orchestrator.

```
┌─────────────────────────────────────────────────────────┐
│                     User Request                        │
│         "Add user authentication with JWT"              │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Orchestrator (your-workflow)               │
│  • Analyze → Design Plan → Create Tasks → Coordinate    │
└────────────────────────┬────────────────────────────────┘
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
   ┌─────────┐     ┌─────────┐     ┌─────────┐
   │Worker 1 │     │Worker 2 │     │Worker 3 │
   │(worktree)│     │(worktree)│     │(worktree)│
   └────┬────┘     └────┬────┘     └────┬────┘
        │               │               │
        └───────────────┼───────────────┘
                        ↓
                  ┌───────────┐
                  │flow branch│ ← All completed work merges here
                  └───────────┘
```

---

## 2. Project Structure

```
src/flow_claude/
├── commands/                     # CLI entry points
│   ├── flow_cli.py              # Project initialization (flow init)
│   ├── toggle_auto.py           # Autonomous mode toggle (\auto)
│   └── set_parallel.py          # Parallel count setting (\parallel N)
│
├── scripts/                      # Git operation scripts (core functionality)
│   ├── create_plan_branch.py    # Create execution plan branch
│   ├── create_task_branch.py    # Create task branch
│   ├── update_plan_branch.py    # Update plan progress
│   ├── read_plan_metadata.py    # Read plan metadata
│   ├── read_task_metadata.py    # Read task metadata
│   ├── parse_branch_latest_commit.py  # Monitor progress
│   └── launch_worker.py         # Launch Worker (Claude SDK)
│
├── templates/                    # Template files (copied to project)
│   ├── skills/                  # Skill definitions
│   │   ├── your-workflow/       # Orchestrator main workflow
│   │   ├── launch-workers/      # Worker management
│   │   └── git-tools/           # Git operation tools
│   ├── agents/                  # Agent definitions
│   │   ├── user.md              # Autonomous decision agent
│   │   └── worker-template.md   # Worker workflow template
│   └── commands/                # Slash commands
│       ├── auto.md              # \auto command
│       └── parallel.md          # \parallel N command
│
└── setup_ui/                     # Interactive setup UI (Textual)
    ├── app.py
    ├── screens.py
    └── git_utils.py
```

---

## 3. Git Branch Structure (Git as Database)

```
main/master (production branch)
    ↑
flow (development base branch - auto-created)
    │
    ├── plan/session-YYYYMMDD-HHMMSS (execution plan)
    │   ├── Commit 1: Initial plan (v1)
    │   └── Commit 2: Updated plan (v2, after replanning)
    │
    ├── task/001-create-user-model
    │   ├── Commit 1: Task metadata
    │   ├── Commit 2: Design commit
    │   ├── Commit 3-N: Progress commits
    │   └── Merge: Merge to flow
    │
    ├── task/002-add-password-hash
    └── task/003-auth-endpoints
```

**All state stored in Git commits - no external database needed!**

---

## 4. Complete Workflow

### Phase 1: Initialization (One-time)

```bash
cd /path/to/project
flow init  # or python -m flow_claude.commands.flow_cli
```

**Actions performed:**
1. Create `flow` branch
2. Copy templates to `.claude/` directory
3. Update `CLAUDE.md`
4. Commit configuration to flow branch

### Phase 2: User Request

```
User: "Add user authentication with JWT and bcrypt"
```

### Phase 3: Orchestrator Analysis & Planning

```
┌─────────────────────────────────────────────────────────┐
│ Orchestrator executes:                                  │
│                                                         │
│ 1. Analyze request + codebase context                   │
│    - Read existing code structure                       │
│    - Understand architecture patterns                   │
│                                                         │
│ 2. Design execution plan                                │
│    - Break into ~10-minute tasks                        │
│    - Define dependencies (DAG)                          │
│    - Identify parallelizable tasks                      │
│                                                         │
│ 3. Check autonomous mode                                │
│    if user.md exists: consult User agent for approval   │
│    else: execute directly (autonomous = ON)             │
│                                                         │
│ 4. Create plan branch                                   │
│    python -m flow_claude.scripts.create_plan_branch \   │
│      --session-name="add-auth" \                        │
│      --user-request="..." \                             │
│      --tasks='[{id, description, depends_on}, ...]'     │
└─────────────────────────────────────────────────────────┘
```

### Phase 4: Launch Workers (Parallel)

```
┌─────────────────────────────────────────────────────────┐
│ For each ready task (depends_on = []):                  │
│                                                         │
│ A. Create task branch                                   │
│    python -m flow_claude.scripts.create_task_branch \   │
│      --task-id="001" \                                  │
│      --instruction="Create User model..." \             │
│      --depends-on='[]' \                                │
│      --key-files='["src/models/user.py"]'               │
│                                                         │
│ B. Create Git Worktree (isolated workspace)             │
│    git worktree add .worktrees/worker-1 task/001-...    │
│                                                         │
│ C. Launch Worker in background                          │
│    Bash(                                                │
│      command="python -m flow_claude.scripts.launch_worker│
│        --worker-id=1 \                                  │
│        --task-branch='task/001-...' \                   │
│        --cwd='.worktrees/worker-1'",                    │
│      run_in_background=true  # Key: parallel execution  │
│    )                                                    │
└─────────────────────────────────────────────────────────┘
```

### Phase 5: Worker Execution (Independent & Parallel)

```
┌─────────────────────────────────────────────────────────┐
│ Each Worker executes independently:                     │
│                                                         │
│ 1. Read task metadata (read_task_metadata)              │
│ 2. Create design commit                                 │
│    - Plan implementation approach                       │
│    - TODO checklist                                     │
│                                                         │
│ 3. Incremental implementation                           │
│    - Create/modify files                                │
│    - Run tests                                          │
│    - Commit progress (mark TODO [x])                    │
│                                                         │
│ 4. Merge to flow branch                                 │
│    git checkout flow                                    │
│    git merge --no-ff task/001-...                       │
│                                                         │
│ 5. Signal completion                                    │
│    git commit --allow-empty -m "TASK_COMPLETE: task/001"│
└─────────────────────────────────────────────────────────┘
```

### Phase 6: Orchestrator Monitoring Loop

```
┌─────────────────────────────────────────────────────────┐
│ When any Worker completes:                              │
│                                                         │
│ A. Verify implementation quality                        │
│    - Read code to check quality                         │
│    - Confirm merged to flow                             │
│                                                         │
│ B. Cleanup Worktree                                     │
│    git worktree remove .worktrees/worker-N              │
│                                                         │
│ C. Update plan                                          │
│    - Mark task as completed                             │
│    - Check if replanning needed                         │
│    - Add newly discovered tasks                         │
│                                                         │
│ D. Launch next batch of ready tasks                     │
│    nextReady = tasks where all depends_on completed     │
│                                                         │
│ E. Repeat until all tasks complete                      │
└─────────────────────────────────────────────────────────┘
```

### Phase 7: Completion

```
- All tasks merged to flow branch
- Final plan version committed
- Session summary displayed
```

---

## 5. Core Component Roles

| Component | Role | Responsibilities |
|-----------|------|------------------|
| **Orchestrator** | Main Coordinator | Analyze requests, design plans, manage Workers, monitor progress |
| **User Agent** | Decision Agent | Approve plans, technology choices, error recovery decisions |
| **Worker** | Task Executor | Independently implement tasks, test, merge to flow |
| **Git Scripts** | State Management | Create/read/update plan and task branches |

---

## 6. Design Patterns

### 6.1 Git as Database

```python
# Read plan
git log plan/session-name --format=%B -n 1

# Read task metadata
git log --follow --reverse task/001-name --format=%B | head -1

# View completed tasks
git log flow --merges --oneline
```

**No external state files - fully recoverable from `git log`!**

### 6.2 Isolated Worktrees

```bash
# Each Worker has an independent workspace, no interference
.worktrees/
├── worker-1/  → task/001-create-user-model
├── worker-2/  → task/002-add-password-hash
└── worker-3/  → task/003-auth-endpoints
```

### 6.3 Task Dependencies (DAG)

```
001 (User model)  ←─┐
                     ├─→ 003 (Auth endpoints)
002 (Password hash)─┘
```

- Wave 1: Launch 001, 002 (no dependencies)
- Wave 2: Launch 003 after 001, 002 complete

### 6.4 Progressive Commits

```
Design commit    → Plan what to do
Progress commits → Do the actual work
Merge commit     → Integrate to main branch
```

---

## 7. CLI Commands

| Command | Function | Mechanism |
|---------|----------|-----------|
| `flow init` | Initialize project | Create flow branch, copy templates |
| `\auto` | Toggle autonomous mode | Create/delete `user-proxy.md` |
| `\parallel N` | Set parallel count | Update count in skill description |

---

## 8. Data Flow Diagram

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│  User    │───→│ Orchestrator │───→│ Plan Branch  │
│ Request  │    └──────┬───────┘    └──────────────┘
└──────────┘           │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │Task 001  │  │Task 002  │  │Task 003  │
   │Branch    │  │Branch    │  │Branch    │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
   ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐
   │Worker 1  │  │Worker 2  │  │Worker 3  │
   │Worktree  │  │Worktree  │  │Worktree  │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
        └─────────────┼─────────────┘
                      ↓
               ┌────────────┐
               │flow branch │ ← Final results
               └────────────┘
```

---

## 9. Technology Stack

- **claude-agent-sdk**: Worker async execution
- **click**: CLI framework
- **textual**: Interactive TUI
- **Git**: State management + version control

---

## 10. Design Principles

1. **Git-First**: All state stored in Git commits
2. **Autonomous**: Workers execute independently, no approval waiting
3. **Parallel**: Maximize concurrent execution, respect dependencies
4. **Auditable**: Complete history queryable via `git log`
5. **Recoverable**: Can resume from any Git state
6. **Modular**: Skills/Agents/Commands are pluggable
