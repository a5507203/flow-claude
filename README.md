# Flow-Claude 
---

A punch line (claude code, gi)

Flow-Claude extends Claude Code with git-driven task orchestration. Break down large features into parallel subtasks, execute them simultaneously, and merge results automatically.

---

### Key feature and Benfits

Flow+Claude subagent with GitHub as the version control and information hub (sinlge source of truth).

Claude automatically generates plans and creates both plan branches and task branches:

The plan branch defines the overall workflow and updates automatically whenever a task is completed.

Each task branch is used to execute an individual task. Tasks can run in parallel using Git worktrees.

This setup ensures smooth automation, parallel task execution, and continuous synchronization between planning and execution stages.

Works seamlessly within Claude Code UI

## related paper


## To be a conributor

submit an github issue (link) and contact team via yu.yao@sydney.edu.au and discord xxx

### desgin principle 

We design Flow-Claude as a lightweight tool that lives within the Claude CLI. As the Claude code model evolves, the benefits of the framework will also continue to grow. 

The framework itself should not become a blocker for future updates of the Claude model. Therefore our primary focus is communication efficiency and parallelism with minimum constraints.

Every new design should smoothly support the Claude CLI.



---





### workflow

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


---

## Install

Get started in 2 minutes.

---

### Prerequisites

- Python 3.10+
- Git
- Node.js 18+ (LTS recommended)
- npm 9+ or equivalent package manager
- Windows users: See [Windows Installation Guide](https://code.claude.com/docs/en/setup#windows-setup) for special instructions

> **IMPORTANT**: Claude Code must be installed first:
> ```bash
> # 1. Install Claude Code globally
> npm install -g @anthropic-ai/claude-code
>
> # 2. (Optional) Skip permissions check for faster setup
> claude --dangerously-skip-permissions
> ```
>
> See [Claude Code Setup](https://code.claude.com/docs/en/setup) for more details.

---


**Option 1: From PyPI**
```bash
pip install flow-claude
```

**Option 2: From Source**
```bash
git clone https://github.com/a5507203/flow-claude.git
cd flow-claude
pip install -e .
```

**Verify Installation:**
```bash
flow --help
```

Expected output:
```
Usage: flow [OPTIONS]

  Initialize Flow-Claude for Claude Code UI.

  Creates .claude/ directory structure with skills, commands, and agents.
  Run once per project, then use Claude Code UI for development.

Options:
  --help  Show this message and exit.
```

---

## Initialize Your Project

> **Warning**: For existing projects, backup your `.claude/` directory and `CLAUDE.md` first - `flow init` will overwrite them.

Navigate to your git repository and initialize Flow-Claude:

### Linux / macOS

```bash
cd /path/to/your/project
flow init
```
##TODO conda, global python envirment work, other don't know

### Windows

**Option 1: Using Python Module (Works Immediately)**
```bash
cd /path/to/your/project
python -m flow_claude.commands.flow_cli
```

**Option 2: Using `flow` Command (Requires PATH Setup)**

First, add Python Scripts to PATH:
```powershell
# Find your Python Scripts directory
python -c "import os, sys; print(os.path.join(sys.prefix, 'Scripts'))"

# Add to PATH (PowerShell - current session)
$env:PATH += ";C:\Users\YourUsername\AppData\Roaming\Python\Python3XX\Scripts"

# Or add permanently via System Environment Variables 
#TODO Link
```

Then run:
```bash
flow init
```

---

**What happens during initialization:**
- Creates `flow` branch from your main branch
- Creates `.claude/` directory with skills, commands, agents
- Creates/updates `CLAUDE.md` with Flow-Claude instructions
- Commits all changes to `flow` branch

### TODO dir structure
---




### Usage

1. **Open your project in Claude Code**
2. **Make a request** - Claude will automatically use Flow-Claude for complex tasks

```
"Add user authentication with JWT and bcrypt"
```

Flow-Claude will:
- Break down the task into parallel subtasks
- Create isolated git worktrees for each worker
- Execute tasks concurrently
- Merge results to the `flow` branch

---


### Example

```bash
# Initialize
cd my-project
flow init

# Open Claude Code
claude

# Ask:
"Refactor the API to use async/await and add comprehensive error handling"

# Flow-Claude creates:
# - plan/session-20250121-143000 (execution plan)
# - task/001-async-refactor
# - task/002-error-handling
# - task/003-update-tests
#
# Workers execute in parallel, merge to flow branch
```



### Example

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

## TODO if is a small tasks, main agent can decide to do it by itself


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

## Commands

| Command | Description |
|---------|-------------|
| `\auto` | Toggle autonomous mode (ON = no approval needed) |
| `\parallel N` | Set max parallel workers (1-10, default: 3) |

---

## MCP Servers and AgentSkills

#TODO main agent can auto decide what mcp tools and what agent skills are needed for workers


### MCP Servers install 

Flow-Claude uses MCP the same way as Claude Code.

How to setup up MCP can found
- [Claude Code](https://code.claude.com/docs/en/mcp)

**Example: Add Playwright MCP server**

```bash
claude mcp add playwright -- npx --scope project @playwright/mcp@latest
```

Or manually add to `.mcp.json` in your project root folder:

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

**References:**
- [Claude Code](https://www.claude.com/product/claude-code)


---
### skill install




---


### Requirements

- Python ≥ 3.10
- Git
- [Claude Code](https://www.claude.com/product/claude-code)

---

### License

MIT License - see [LICENSE](LICENSE) for details.

### Contributing

Contributions welcome! Please open an issue or submit a pull request.

### Support

- [GitHub Issues](https://github.com/a5507203/flow-claude/issues)
- [Quick Start Guide](QUICKSTART.md)
- [Design Pipeline](DESIGN_PIPELINE.md)

---

**Ready to supercharge your development?**

```bash
pip install flow-claude && cd your-project && flow init
```
