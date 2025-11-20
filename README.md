# Flow-Claude

Git-driven autonomous development system for Claude Code. Execute complex development tasks through parallel worker agents coordinated by an intelligent orchestrator.

## Features

- **Autonomous Task Execution**: Break down complex requests into parallel tasks
- **Git-First Architecture**: All state managed through structured git commits and branches
- **Parallel Workers**: Execute independent tasks simultaneously in isolated git worktrees
- **Dynamic Replanning**: Adapt execution plan based on implementation discoveries
- **Claude Code Native**: Seamless integration with Claude Code UI

## Installation

```bash
pip install flow-claude
```

## Quick Start

### 1. Initialize Your Project

Navigate to your git repository and run:

```bash
flow init
```

This creates the `.claude/` directory structure with skills, commands, and settings.

### 2. Open in Claude Code

Open your project in Claude Code UI.

### 3. Start Developing

Simply describe what you want to build:

```
"Add user authentication with JWT and bcrypt"
"Implement product search with Elasticsearch"
"Create REST API for order management"
```

The orchestrator will:
1. Analyze your request
2. Design an execution plan with ~10-minute tasks
3. Create independent, parallel-friendly tasks
4. Launch workers to execute tasks simultaneously
5. Merge results to the `flow` branch

## Architecture

### Branches

- `main`/`master`: Production code
- `flow`: Development base (auto-created)
- `plan/session-*`: Execution plans
- `task/*`: Individual task branches

### Workflow

```
User Request
    ↓
Orchestrator analyzes & plans
    ↓
Creates task branches (task/001-*, task/002-*, ...)
    ↓
Launches workers in parallel (git worktrees)
    ↓
Workers execute & commit progress
    ↓
Merge to flow branch
```

### Task Design

Each task is:
- **~10 minutes**: Right-sized for focused work
- **Self-contained**: Minimal dependencies on other tasks
- **Independent**: Can run in parallel without conflicts
- **Specific**: Clear instruction with MCP tool guidance

## Configuration

### Autonomous Mode

Toggle autonomous execution (default: OFF):

```
\auto
```

- **OFF**: Presents plan and waits for approval
- **ON**: Executes automatically

### Parallel Workers

Set maximum parallel workers (1-10, default: 3):

```
\parallel 5
```

## Commands

### CLI

```bash
# Initialize project
flow init

# Initialize with verbose output
flow init --verbose
```

### Python Module

```bash
# After pip install -e .
python -m flow_claude.commands.flow_cli
python -m flow_claude.commands.flow_cli --verbose
```

## Project Structure

```
your-project/
├── .claude/
│   ├── skills/
│   │   ├── git-tools/          # Git state management (6 commands)
│   │   ├── launch-workers/     # Worker spawning & management
│   │   └── your-workflow/      # Main orchestration workflow
│   ├── commands/
│   │   ├── auto.md             # Toggle autonomous mode
│   │   └── parallel.md         # Set max workers
│   ├── agents/
│   │   └── user.md             # User confirmation agent
│   └── settings.local.json     # Claude Code settings
├── .worktrees/                 # Worker git worktrees (auto-created)
│   ├── worker-1/
│   ├── worker-2/
│   └── worker-3/
└── CLAUDE.md                   # Project instructions
```

## Example Session

**Request:**
```
"Build a REST API for blog posts with CRUD operations"
```

**Flow-Claude will:**

1. **Plan** (3 independent tasks):
   - Task 001: Create Post model with SQLAlchemy (blog/models/post.py)
   - Task 002: Implement post CRUD service (blog/services/post_service.py)
   - Task 003: Create REST API endpoints (blog/api/posts.py)

2. **Execute** in parallel:
   - Worker 1 → Task 001
   - Worker 2 → Task 002
   - Worker 3 → Task 003

3. **Merge** all changes to `flow` branch

## Advanced Usage

### External MCP Tools

Workers can access MCP servers defined in `.mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

Workers automatically get access to required MCP tools based on task instructions.

### Monitoring Workers

Workers commit progress to their task branches. Monitor via:

```bash
git log task/001-create-post-model
```

### Manual Task Creation

```bash
python -m flow_claude.scripts.create_task_branch \
  --task-id="001" \
  --instruction="Create Post model. Use Write tool to create blog/models/post.py with SQLAlchemy Post model (title, content, author, created_at fields). Include tests in tests/test_post_model.py." \
  --plan-branch="plan/build-blog-api" \
  --depends-on='[]' \
  --key-files='["blog/models/post.py","tests/test_post_model.py"]' \
  --priority="high"
```

## Requirements

- Python ≥ 3.10
- Git repository
- Claude Code UI (for interactive use)

## Dependencies

- `claude-agent-sdk` ≥ 0.1.0
- `click` ≥ 8.1.0

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/flow-claude.git
cd flow-claude

# Install in editable mode
pip install -e .

# Run tests
pytest

# Lint
ruff check .
```

## License

[Your License Here]

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

- Issues: https://github.com/yourusername/flow-claude/issues
- Documentation: [Link to docs]

---

**Ready to start?** Run `flow init` in your project and describe what you want to build!
