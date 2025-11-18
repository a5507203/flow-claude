---
description: Set maximum parallel workers (1-10)
---

# Parallel Command

Set the maximum number of parallel worker agents that the orchestrator can spawn simultaneously.

**Usage**: `\parallel <number>`

**Valid range**: 1-10
- 1 = Sequential execution (one task at a time)
- 3 = Default (moderate parallelization)
- 10 = Maximum parallelization

**Action**:
1. Parse the number from user input
2. Validate it's between 1 and 10
3. Update `.claude/skills/orchestrator/skill.md` YAML frontmatter
4. Find the line: `max_parallel: X`
5. Replace with: `max_parallel: <new_number>`

**Example**:
```yaml
---
max_parallel: 3
---
```

Change to:
```yaml
---
max_parallel: 5
---
```

**Response**:
- If successful: "✓ Max parallel workers: {number}"
- If invalid: "❌ Error: Value must be between 1 and 10"
- If file not found: "❌ Error: Orchestrator skill not found"

The change takes effect immediately for the next development request.
