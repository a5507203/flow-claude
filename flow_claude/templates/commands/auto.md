---
description: Toggle autonomous mode (ON/OFF)
---

# Auto Command

Toggle the autonomous mode for Flow-Claude orchestrator.

**Current behavior**: Check if `.claude/agents/user-proxy.md` exists
- If **file exists** → Autonomous mode is **OFF** (orchestrator asks for confirmation)
- If **file missing** → Autonomous mode is **ON** (orchestrator executes automatically)

**Action**:
1. Check if `.claude/agents/user-proxy.md` exists
2. If exists: Delete it (turn autonomous mode **ON**)
3. If missing: Create it from template (turn autonomous mode **OFF**)
4. Inform user of the new state

**Template location**: `flow_claude/templates/agents/user-proxy.md`

When creating the file, copy the user-proxy template content which defines how the orchestrator should get user confirmation before executing plans.

Respond with:
- "✓ Autonomous mode: ON" (if file was deleted)
- "✓ Autonomous mode: OFF" (if file was created)
