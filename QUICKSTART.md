# Flow-Claude Quick Start

Get started in 2 minutes.

---

## Prerequisites

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

## Installation

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

---

## Usage

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

## Commands

| Command | Description |
|---------|-------------|
| `\auto` | Toggle autonomous mode (ON = no approval needed) |
| `\parallel N` | Set max parallel workers (1-10, default: 3) |

---

## Example

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

---

## Verify Results

```bash
# See completed work
git log flow --oneline

# See execution plan
git log plan/session-* --format=%B -n 1
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Not a git repository" | Run `git init` first |
| Templates not found | Run `pip install -e .` from source, or reinstall |
| Permission errors | Check Claude Code is authenticated |

---

## MCP Servers

Flow-Claude uses MCP the same way as Claude Code.

**Example: Add Playwright MCP server**

```bash
claude mcp add playwright -- npx @playwright/mcp@latest
```

Or manually add to `.mcp.json` in your project:

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
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)

---

## Next Steps

- [README.md](README.md) - Full documentation
