# Flow-Claude Quick Start Guide

Get Flow-Claude running in 5 minutes!

---

## Prerequisites

- Python 3.10 or higher
- Node.js (for Claude Code CLI)
- Git repository
- Anthropic account (free signup at https://console.anthropic.com)

---

## Step 1: Install Node.js

If you don't have Node.js:

```bash
# Check if installed
node --version

# If not, install from https://nodejs.org/
# Or use package manager:
brew install node  # macOS
winget install OpenJS.NodeJS  # Windows
```

---

## Step 2: Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:
```bash
claude-code --version
```

---

## Step 3: Authenticate with Claude Code

```bash
claude-code auth login
```

This will:
1. Open your browser
2. Ask you to log in to your Anthropic account
3. Authorize Claude Code CLI

**You only need to do this once!**

Verify you're logged in:
```bash
claude-code auth status
```

---

## Step 4: Install Flow-Claude

```bash
cd flow-claude
pip install -e .
```

This installs Flow-Claude in development mode, making the `flow-claude` command available.

---

## Step 5: Verify Installation

```bash
flow-claude --help
```

You should see:
```
Usage: flow-claude [OPTIONS] COMMAND [ARGS]...

  Flow-Claude: Git-driven autonomous development using Claude agent SDK.

Commands:
  develop  Execute development request using planning and worker agents.
```

---

## Step 6: Run Your First Development Session

Navigate to a git repository:

```bash
cd /path/to/your/project
```

Run Flow-Claude:

```bash
flow-claude develop "add a simple hello world function"
```

---

## What Happens Next

Flow-Claude will:

1. **Create Execution Plan**
   - Analyzes your codebase
   - Creates `plan/session-YYYYMMDD-HHMMSS` branch
   - Commits execution plan with tasks

2. **Spawn Workers**
   - Creates task branches: `task/001-description`
   - Each branch has task metadata in first commit
   - Workers implement, test, and signal completion

3. **Validate and Merge**
   - Planning agent validates completed tasks
   - Runs tests and linting
   - Merges to main with structured commit

4. **Complete Session**
   - All tasks merged
   - Session summary displayed

---

## Example Session

```bash
$ flow-claude develop "add user authentication"

============================================================
🚀 Flow-Claude Development Session Starting...
============================================================

📝 Request: add user authentication
🤖 Model: sonnet
📁 Working Directory: /Users/you/project

[Planning Agent: Phase 1]
✅ Analyzed codebase
✅ Created plan branch: plan/session-20250101-120000
✅ Execution plan v1 with 3 tasks

[Planning Agent: Phase 2]
✅ Task 001 ready: Create User model
✅ Created branch: task/001-user-model
🔧 Worker executing task/001-user-model

[Worker-001]
✅ Read task metadata
✅ Implemented User model
✅ Wrote tests (5/5 passed)
✅ Signaled TASK_COMPLETE: 001

[Planning Agent: Phase 3]
✅ Detected completion: task/001
✅ Validated (tests pass, linting pass)
✅ Merged to main

... continues for all tasks ...

============================================================
✅ Development session complete!
============================================================

Summary:
  - Tasks: 3/3 completed
  - Duration: 28 minutes
  - All tests passing
```

---

## Verify Results

Check git history:

```bash
# See main branch commits
git log main --oneline --graph

# See plan branch
git log plan/session-20250101-120000 --format=%B -n 1

# See merge commits with provides
git log main --merges --format=%B
```

---

## Common Options

### Use Different Model

```bash
flow-claude develop "your request" --model opus
```

Options: `sonnet`, `opus`, `haiku`

### Set Max Turns

```bash
flow-claude develop "your request" --max-turns 50
```

### Permission Mode

```bash
# Ask for confirmation before edits
flow-claude develop "your request" --permission-mode ask

# Deny all edits (dry run)
flow-claude develop "your request" --permission-mode deny
```

---

## Troubleshooting

### "Not a git repository" Error

```bash
cd /path/to/your/project
git init
git add .
git commit -m "Initial commit"
```

### SDK Import Errors

```bash
pip install anthropic-claude-agent-sdk
```

### API Key Errors

```bash
# Check if key is set
echo $ANTHROPIC_API_KEY

# Set it
export ANTHROPIC_API_KEY="your-key-here"
```

### View Agent Activity

All git operations are visible:

```bash
# See all branches
git branch -a

# See task branches
git branch -a | grep task/

# See plan branches
git branch -a | grep plan/

# See task metadata
git log task/001-description --reverse --format=%B -n 1
```

---

## Understanding the Git Structure

After a session:

```
your-repo/
├── main branch
│   └── Merge commits (3 tasks merged)
│
├── plan/session-20250101-120000
│   └── Execution plan commit(s)
│
└── task/* branches (deleted after merge)
    ├── task/001-user-model (deleted)
    ├── task/002-password-hash (deleted)
    └── task/003-auth-service (deleted)
```

**All metadata in commits:**
- Task metadata: First commit on task branch
- Plan: Commits on plan branch
- Results: Merge commits on main

**No external files created!**

---

## Run Tests

Flow-Claude includes unit tests:

```bash
# Run parser tests
pytest tests/test_parsers.py -v

# Run all tests
pytest tests/ -v
```

---

## Next Steps

1. **Try on Real Project**
   - Navigate to your project
   - Run a simple feature request
   - Observe agent behavior

2. **Review Git History**
   - Check plan branch
   - Review task metadata
   - See merge commits

3. **Iterate**
   - Test different requests
   - Different models (opus vs sonnet)
   - Observe task granularity

4. **Read Documentation**
   - `README.md` - Full documentation
   - `DESIGN_V6.1.md` - Architecture details
   - `IMPLEMENTATION_PLAN.md` - How it works
   - `prompts/planner.md` - Planning workflow
   - `prompts/worker.md` - Worker workflow

---

## Example Requests

**Simple:**
```bash
flow-claude develop "add a utility function to validate email addresses"
```

**Medium:**
```bash
flow-claude develop "add logging to all API endpoints"
```

**Complex:**
```bash
flow-claude develop "refactor authentication to use OAuth2 with JWT"
```

**Bug Fix:**
```bash
flow-claude develop "fix the race condition in payment processing"
```

**Refactoring:**
```bash
flow-claude develop "convert database queries to use async/await"
```

---

## Getting Help

```bash
# Help for main command
flow-claude --help

# Help for develop command
flow-claude develop --help

# Version
flow-claude --version
```

---

## Key Features to Try

1. **Dynamic Replanning**
   - Request something that will need additional tasks
   - Watch planning agent detect blocks and update plan

2. **Context-Aware Workers**
   - Check how workers read session goals
   - See how they design interfaces for dependent tasks

3. **Git-First Architecture**
   - All data in git
   - No external files
   - Query state via git log

4. **Fine-Grained Tasks**
   - 5-10 minute tasks
   - Atomic and testable
   - Easy to review

---

You're ready to go! 🚀

Run your first session:

```bash
cd your-project
flow-claude develop "your development request here"
```

**Happy autonomous coding!**
