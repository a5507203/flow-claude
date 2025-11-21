# Flow-Claude

**Turn complex development requests into parallel, autonomous execution.**

Flow-Claude extends Claude Code with git-driven task orchestration. Break down large features into parallel subtasks, execute them simultaneously, and merge results automatically.

---

## Why Flow-Claude?

- **Faster Development** - Parallel workers execute independent tasks simultaneously
- **Git as Database** - All state stored in commits, fully auditable and recoverable
- **Zero Context Switching** - Orchestrator manages everything, you just describe what you want
- **Claude Code Native** - Works seamlessly within Claude Code UI

---

## Features

- **Autonomous Task Execution** - Break down complex requests into parallel tasks
- **Git-First Architecture** - All state managed through structured git commits and branches
- **Parallel Workers** - Execute independent tasks simultaneously in isolated git worktrees
- **Dynamic Replanning** - Adapt execution plan based on implementation discoveries

---

## Quick Start

```bash
# 1. Install
pip install flow-claude

# 2. Initialize your project
cd /path/to/your/project
flow init

# 3. Open Claude Code
claude

# 4. Make a request
"Add user authentication with JWT and bcrypt"
```

> See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

---

## How It Works

```
Your Request
     ↓
┌─────────────────────────────────────┐
│         Orchestrator                │
│  • Analyzes request                 │
│  • Designs execution plan           │
│  • Manages parallel workers         │
└─────────────────────────────────────┘
     ↓
┌─────────┐  ┌─────────┐  ┌─────────┐
│Worker 1 │  │Worker 2 │  │Worker 3 │
│(task/001)│  │(task/002)│  │(task/003)│
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  ↓
           flow branch
        (merged results)
```

### Git Branch Structure

```
main/master (production)
    ↑
flow (development base)
    ├── plan/session-* (execution plans)
    ├── task/001-*
    ├── task/002-*
    └── task/003-*
```

---

## Configuration

| Command | Description |
|---------|-------------|
| `\auto` | Toggle autonomous mode (ON = no approval needed) |
| `\parallel N` | Set max parallel workers (1-10, default: 3) |

---

## Example

**Request:**
```
"Build a REST API for blog posts with CRUD operations"
```

**Flow-Claude will:**

1. **Plan** - Create 3 parallel tasks:
   - Task 001: Create Post model
   - Task 002: Implement CRUD service
   - Task 003: Create API endpoints

2. **Execute** - Launch workers in parallel

3. **Merge** - All changes merged to `flow` branch

---

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Installation & setup guide
- [DESIGN_PIPELINE.md](DESIGN_PIPELINE.md) - Architecture details

---

## Requirements

- Python ≥ 3.10
- Git
- [Claude Code](https://www.claude.com/product/claude-code)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

- [GitHub Issues](https://github.com/a5507203/flow-claude/issues)
- [Quick Start Guide](QUICKSTART.md)
- [Design Pipeline](DESIGN_PIPELINE.md)

---

**Ready to supercharge your development?**

```bash
pip install flow-claude && cd your-project && flow init
```
