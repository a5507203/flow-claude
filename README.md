# Flow-Claude (Flow for Claude Code)

Flow-Claude is for Claude Code users working on long development tasks. 
- Break down requirements into parallel tasks, 
- execute them simultaneously without stopping, 
- auto-commit every change to Git, 
- and merge results automatically. 





## Related Paper

Niu, B., Song, Y., Lian, K., Shen, Y., Yao, Y., Zhang, K., & Liu, T. Flow: Modularized Agentic Workflow Automation. ICLR 2025

[Paper PDF](https://openreview.net/pdf?id=sLKDbuyq99)

## Design Principle

We design Flow-Claude as a lightweight tool that lives within the Claude CLI. As the Claude code model evolves, the benefits of the framework will also continue to grow.

The framework itself should not become a blocker for future updates of the Claude model. Therefore our primary focus is communication efficiency and parallelism with minimum constraints.

Every new design should smoothly support the Claude CLI.

---


## Installation

### Prerequisites


Claude Code must be installed first:
> ```bash
> npm install -g @anthropic-ai/claude-code
> ```
>
See [Claude Code Setup](https://code.claude.com/docs/en/setup) for more details.

---

**Install Flow-Claude From PyPI**
```bash
pip install flow-claude
```



**Verify Installation:**
```bash
flow --help
```

On Windows, if `flow` is not in your PATH, use:
```bash
python -m flow_claude.commands.flow_cli --help
```

---

## Quick Start and Tips

### 1. Initialize Your Project


Navigate to your git repository and initialize Flow-Claude:

#### Linux / macOS

```bash
cd /path/to/your/project
flow
```

#### Windows

On Windows, if `flow` is not in your PATH, use:
```bash
cd /path/to/your/project
python -m flow_claude.commands.flow_cli
```

---

**What happens during initialization:**
- Creates `flow` branch from your main branch
- Creates `.claude/` directory with skills, commands, agents
- Creates/updates `CLAUDE.md` with Flow-Claude instructions
- Commits all changes to `flow` branch


### 2. Launch Claude Code

```bash
claude
```

If you want to avoid frequent permission approval, use:
```bash
claude --dangerously-skip-permissions
```

### 3. Prompt Claude to use Flow-Claude

****Because the current Claude model does not reliably invoke Skills automatically, you need to append a reminder at the end of your prompt****.

For example:
```
Build a REST API for blog posts with CRUD operations. Remember to use your SKILLs.
```

![Launch](./assets/workflow1.png)

### 4. Resume 

When you return to a project after a break or session interruption, prompt Claude to understand the current state before continuing.

**Step 1:** Use the resume command to restore your previous conversation:
```
/resume
```
Select the past conversation from the list.

**Step 2:** ****Prompt Claude to check the current state and continue.**** For example:
```
Check the current plan and task branch status, then continue the unfinished task. Remember to use Skills.
```

![ResumeWork](./assets/resume_work.png)


---




### 5. Commit Manual Changes

If you make local changes on the `flow` branch and want workers to use them, commit your changes first:
```bash
git add . && git commit -m "Your commit message"
```
Workers pull from the `flow` branch, so uncommitted changes won't be visible to them.

### 6. Delete Unwanted Branches

After a plan is finished and all tasks passed, you may want to clean up the created branches. Use a prompt like:
```
Delete the plan/<plan-name> branch and all its related task branches.
```
For example: `Delete the plan/blog-api-crud branch and all its related task branches.`

![Delete](./assets/delete.png)

---


### 6. Commands

| Command | Description |
|---------|-------------|
| `\auto` | Toggle autonomous mode (ON = no approval needed) |
| `\parallel N` | Set max parallel workers (1-10, default: 3) |

---

## MCP Servers and Skills

The main agent can automatically determine which MCP tools and agent skills the worker agents require.

### MCP Servers Install

Flow-Claude uses MCP in the same way as Claude Code, except that **MCP servers must be installed inside your project directory**.

For detailed MCP setup instructions, see:
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)

**Example: Adding the Playwright MCP server**

```bash
claude mcp add playwright -- npx --scope project @playwright/mcp@latest # Run this command inside your project directory
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

### Skill Install

Flow-Claude uses Skill in the same way as Claude Code, except that **Skill must be added inside your project directory**.

For detailed Skill adding instructions, see:
- [Claude Code Skill](https://platform.claude.com/docs/en/agent-sdk/skills#how-skills-work-with-the-sdk)

**Example: Creating Skills**
- Created as `SKILL.md` files in specific directories (.claude/skills/)
```
.claude/skills/processing-pdfs/
└── SKILL.md
```

---

## Hooks Setup

Get notified when Claude needs attention or completes tasks - useful when running AI in background.

**1. Install notification script:**
```bash
npx claude-code-templates@latest --hook=automation/simple-notifications --yes
```
Then delete the `postToolUse` hook added by this command (we only need the notification script it installs).

**2. Add hooks via `/hooks` command:**

| Hook Type | Command |
|-----------|---------|
| **Stop** (task done) | `if command -v osascript >/dev/null 2>&1; then osascript -e 'display notification "Task completed successfully" with title "✅ Claude Code Done"'; elif command -v notify-send >/dev/null 2>&1; then notify-send '✅ Claude Code' 'Task completed successfully'; fi` |
| **Notification** (action needed) | `if command -v osascript >/dev/null 2>&1; then osascript -e 'display notification "Claude Code needs your input or approval!" with title "🛑 Action Required"'; elif command -v notify-send >/dev/null 2>&1; then notify-send '🛑 Claude Code' 'Action or permission required!'; fi` |

> Works on macOS (`osascript`) and Linux (`notify-send`).

---

## Contributing

Submit a [GitHub issue](https://github.com/a5507203/flow-claude/issues) or contact yu.yao@sydney.edu.au

---

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- [GitHub Issues](https://github.com/a5507203/flow-claude/issues)

---

**Ready to supercharge your development?**

```bash
pip install flow-claude && cd your-project && flow
```
