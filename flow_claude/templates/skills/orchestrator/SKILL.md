---
max_parallel: 3
description: Main orchestration logic
---

# Orchestrator Skill

Coordinates autonomous development using git-tools and sdk-workers.

## Workflow

1. Analyze request
2. Check `.claude/agents/user-proxy.md` (exists = need confirmation)
3. Create plan: `python -m flow_claude.scripts.create_plan_branch ...`
4. Create tasks: `python -m flow_claude.scripts.create_task_branch ...`
5. Launch workers: `python -m flow_claude.scripts.launch_worker ...`
6. Monitor: `python -m flow_claude.scripts.get_worker_status`
7. Report results

Read max_parallel from YAML frontmatter above.
