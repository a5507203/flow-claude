# Design Document: Optimize Agent Workflows with MCP Git Tools

**Version:** 1.0
**Date:** 2025-01-06
**Author:** Flow-Claude Optimization Initiative
**Status:** Proposed

---

## Executive Summary

### Problem Statement

Flow-Claude provides 4 custom MCP git tools (`mcp__git__parse_task`, `mcp__git__parse_plan`, `mcp__git__get_provides`, `mcp__git__read_plan_file`) to give agents structured access to git-based metadata. However, current agent workflows (planner, worker, orchestrator) make minimal use of these tools, instead relying on raw bash git commands with manual parsing.

**Consequences:**
- Agents manually parse git output in prompts (error-prone, verbose)
- Redundant git queries (every worker runs `git log main --merges`)
- The `parse_plan_commit()` parser function is never actually used
- More tool calls than necessary to gather task information
- Inconsistency between documented best practices and actual workflows

### Solution Overview

Update agent prompt workflows to use MCP tools for structured data retrieval instead of raw git commands. This will:
- **Reduce tool calls** by centralizing git queries in MCP tools
- **Eliminate manual parsing** by providing structured JSON responses
- **Activate parse_plan_commit()** through `mcp__git__parse_plan` usage
- **Improve consistency** between documentation and implementation

### Scope

**In Scope:**
- Updating worker.md workflow (Steps 1, 2, 3)
- Updating orchestrator.md workflow (Step 1)
- Updating planner.md workflow (Phase 4)
- Documentation alignment

**Out of Scope:**
- New MCP tools (future enhancement)
- Code changes to git_tools.py (current tools sufficient)
- Caching implementation (future optimization)

---

## Current State Analysis

### Available MCP Tools

Based on `flow_claude/git_tools.py`:

#### 1. `mcp__git__parse_task` (lines 36-126)
**Purpose:** Parse task metadata from first commit on task branch
**Input:** `{"branch": "task/001-user-model"}`
**Output:** Structured JSON
```json
{
  "id": "001",
  "description": "Create User model with email and password",
  "status": "pending",
  "preconditions": [],
  "provides": ["User model class", "User.email field"],
  "files": ["models/user.py"],
  "session_goal": "Add authentication",
  "session_id": "session-20250115-103000",
  "plan_branch": "plan/session-20250115-103000",
  "estimated_time": "8 minutes",
  "priority": "high"
}
```
**Parser Used:** `parse_task_metadata()` → `parse_commit_message()`
**Git Command:** `git log <branch> --reverse --format=%B -n 1`

#### 2. `mcp__git__parse_plan` (lines 128-214)
**Purpose:** Parse execution plan from latest plan branch commit
**Input:** `{"branch": "plan/session-20250115-103000"}`
**Output:** Structured JSON
```json
{
  "session_id": "session-20250115-103000",
  "user_request": "Add user authentication",
  "plan_version": "v1",
  "tasks": [
    {
      "id": "001",
      "description": "Create User model",
      "preconditions": [],
      "provides": ["User model class"],
      "estimated_time": "8 minutes"
    }
  ],
  "total_tasks": 5,
  "estimated_total_time": "40 minutes"
}
```
**Parser Used:** `parse_plan_commit()` ⚠️ **Currently unused!**
**Git Command:** `git log <branch> --format=%B -n 1`

#### 3. `mcp__git__get_provides` (lines 217-291)
**Purpose:** Get list of available preconditions from merged tasks
**Input:** `{}` (no parameters)
**Output:** List of strings
```json
["User model class", "User.email field", "User.password_hash field"]
```
**Parser Used:** `extract_provides_from_merge_commits()`
**Git Command:** `git log main --merges --format=%B`

#### 4. `mcp__git__read_plan_file` (lines 294-401)
**Purpose:** Read file from current plan branch without checkout
**Input:** `{"file_name": "plan.md"}`
**Output:** Raw file contents (string)
```
# Execution Plan v1
...
```
**Parser Used:** None (returns raw content)
**Git Commands:**
```bash
git config --local flow-claude.current-plan
git show <plan_branch>:<file_name>
```

---

## Current Agent Workflows

### Worker Workflow (`prompts/worker.md`)

**Current MCP Usage:** **0 tools**

#### Step 1: Read Task Metadata (lines 70-98)
**Current Implementation:**
```bash
git log --format=%B -1
# Returns raw commit message
# Worker must manually parse sections
```

**Problems:**
- Manual parsing of "## Task Metadata", "## Dependencies", etc.
- Verbose prompt instructions for parsing
- Error-prone (what if format slightly different?)

**Available Tool:** `mcp__git__parse_task` (returns structured JSON)

---

#### Step 2: Understand Session Context (lines 101-114)
**Current Implementation:**
```bash
git show plan/session-YYYYMMDD-HHMMSS:system-overview.md
git show plan/session-YYYYMMDD-HHMMSS:plan.md
# Returns raw markdown files
```

**Available Tool:** `mcp__git__read_plan_file` (same result, cleaner interface)

---

#### Step 3: Check Available Code (lines 116-125)
**Current Implementation:**
```bash
git log main --merges --format=%B | grep -A 10 "## Provides"
# Returns unstructured text with provides sections
```

**Problems:**
- Every worker in a wave runs the SAME expensive `git log main --merges`
- Manual grep parsing required
- Redundant computation (Wave 1 with 3 workers = 3x same query)

**Available Tool:** `mcp__git__get_provides` (returns clean list)

---

### Orchestrator Workflow (`prompts/orchestrator.md`)

**Current MCP Usage:** **0 tools**

#### Step 1: Read plan.md to identify task branches (lines 62-70)
**Current Implementation:**
```bash
git show plan/{plan_branch}:plan.md
# Returns raw markdown
# Must manually parse task list, dependencies, status
```

**Line 198 - Check if more waves remain:**
```bash
git show plan/{plan_branch}:plan.md | grep "status.*pending"
# Manual text parsing with grep
```

**Problems:**
- Manual parsing of markdown task list
- Fragile grep patterns for status checking
- No structured access to task dependencies

**Available Tool:** `mcp__git__parse_plan` ⚠️ **This would activate parse_plan_commit()!**

---

### Planner Workflow (`prompts/planner.md`)

**Current MCP Usage:** **1 tool** (`mcp__git__get_provides` in Phase 4)

#### Phase 4: Update Plan After Wave (lines 371-500)
**Current Implementation:**
```bash
# Line 381: Uses mcp__git__get_provides ✅ (good!)
mcp__git__get_provides({})

# Lines 388-411: Reads plan files
git checkout plan/session-{session_id}
# Edit files...
git add plan.md system-overview.md
git commit -m "Update..."
git checkout main
```

**Problems:**
- Despite Rule 6 (line 798) saying "Always use mcp__git__read_plan_file", workflow uses `git checkout`
- Inconsistency between documentation and implementation

**Available Tool:** `mcp__git__read_plan_file` for reads (checkout still needed for writes)

---

## parse_plan_commit() Status

### Definition Location
`flow_claude/parsers.py` lines 238-306

### Current Usage
- **git_tools.py line 173:** Used inside `mcp__git__parse_plan` tool
- **NOWHERE ELSE:** No agent currently calls `mcp__git__parse_plan`

### Why Unused?
Workflows were written BEFORE the MCP tool was fully integrated. Prompts contain OLD patterns using bash git commands.

### How to Activate
Update orchestrator.md Step 1 to call `mcp__git__parse_plan` instead of `git show plan.md`

---

## Optimization Opportunities

### 1. Worker Step 1: Use `mcp__git__parse_task`

**File:** `prompts/worker.md` lines 70-98

**Current:**
```markdown
**Step 1: Read task metadata from your branch**

Use git log to read the FIRST commit (initialization commit) on your task branch:

```bash
git log --format=%B -1
```

This commit contains ALL task metadata in structured format. Parse these sections:
- ## Task Metadata (ID, Description, Status)
- ## Dependencies (Preconditions, Provides)
- ## Files (Files to modify)
- ## Context (Session Goal, Session ID, Plan Branch, Related Tasks)
- ## Estimates (Estimated Time, Priority)
```

**Optimized:**
```markdown
**Step 1: Read task metadata from your branch**

Use the MCP tool to get structured task metadata:

```python
mcp__git__parse_task({"branch": "task/001-user-model"})
```

This returns a JSON object with all task metadata:
- `id`, `description`, `status`
- `preconditions`, `provides`
- `files`
- `session_goal`, `session_id`, `plan_branch`
- `estimated_time`, `priority`
```

**Benefits:**
- ✅ Eliminates 15+ lines of parsing instructions
- ✅ Agents get structured JSON instead of raw text
- ✅ Consistent parsing (all workers use same parser)
- ✅ Reduces prompt complexity

**Lines to Update:** 70-98 (entire Step 1 section)

---

### 2. Worker Step 3: Use `mcp__git__get_provides`

**File:** `prompts/worker.md` lines 116-125

**Current:**
```markdown
**Step 3: Check what code is already available**

Query main branch to see what's been merged:

```bash
git log main --merges --format=%B | grep -A 10 "## Provides"
```

This shows what capabilities are available from completed tasks.
```

**Optimized:**
```markdown
**Step 3: Check what code is already available**

Query merged tasks to see available capabilities:

```python
mcp__git__get_provides({})
```

This returns a list of all capabilities from completed tasks:
```json
["User model class", "User.email field", "Authentication service", ...]
```
```

**Benefits:**
- ✅ Eliminates redundant `git log main --merges` calls (every worker currently runs this!)
- ✅ MCP tool runs git command once, returns cached structured list
- ✅ Removes grep parsing complexity
- ✅ Wave with 3 workers: 3 git log calls → 1 git log call (67% reduction)

**Lines to Update:** 116-125 (entire Step 3 section)

---

### 3. Worker Step 2: Use `mcp__git__read_plan_file`

**File:** `prompts/worker.md` lines 101-114

**Current:**
```markdown
**Step 2: Understand the session context**

Read the session goal and current progress:

```bash
git show plan/session-YYYYMMDD-HHMMSS:system-overview.md
git show plan/session-YYYYMMDD-HHMMSS:plan.md
```
```

**Optimized:**
```markdown
**Step 2: Understand the session context**

Read the session goal and current progress:

```python
mcp__git__read_plan_file({"file_name": "system-overview.md"})
mcp__git__read_plan_file({"file_name": "plan.md"})
```
```

**Benefits:**
- ✅ Cleaner interface (MCP tool handles plan branch resolution)
- ✅ Consistent with other MCP tool usage
- ✅ Same functionality, better abstraction

**Lines to Update:** 101-114 (entire Step 2 section)

---

### 4. Orchestrator Step 1: Use `mcp__git__parse_plan` ⭐

**File:** `prompts/orchestrator.md` lines 62-70

**Current:**
```markdown
**Step 1: Read plan.md to identify task branches**

```bash
# Query what task branches the planner created
git branch --list "task/*"

# Or read plan.md on the plan branch to see task list
git show plan/{plan_branch}:plan.md
```
```

**Optimized:**
```markdown
**Step 1: Read plan.md to identify task branches**

Use the MCP tool to get structured plan data:

```python
mcp__git__parse_plan({"branch": "plan/session-20250115-143000"})
```

This returns structured task information:
```json
{
  "tasks": [
    {"id": "001", "description": "...", "preconditions": [], "provides": [...]},
    {"id": "002", "description": "...", "preconditions": ["001"], "provides": [...]}
  ],
  "total_tasks": 8,
  "session_id": "session-20250115-143000"
}
```

You can programmatically:
- Identify which tasks are in current wave (no unsatisfied preconditions)
- Determine task branch names from task IDs
- Check overall progress (completed vs total tasks)
```

**Benefits:**
- ✅ **Activates parse_plan_commit()!** (primary goal)
- ✅ Structured task list with dependencies parsed
- ✅ Orchestrator can programmatically determine wave membership
- ✅ Eliminates manual grep parsing at line 198 (`grep "status.*pending"`)
- ✅ Consistent with other MCP tool patterns

**Lines to Update:** 62-70 (Step 1), 194-203 (Step 6 status check)

---

### 5. Planner Phase 4: Use `mcp__git__read_plan_file`

**File:** `prompts/planner.md` lines 388-411

**Current:**
```markdown
**Update Plan Files:**

```bash
git checkout plan/session-{session_id}

# Update plan.md - mark Wave N tasks as complete

# Update system-overview.md - document learnings

git add plan.md system-overview.md
git commit -m "Update plan after Wave N completion"

git checkout main
```
```

**Optimized:**
```markdown
**Update Plan Files:**

Read current content:
```python
plan_content = mcp__git__read_plan_file({"file_name": "plan.md"})
overview_content = mcp__git__read_plan_file({"file_name": "system-overview.md"})
```

Update and write back:
```bash
git checkout plan/session-{session_id}

# Update files based on read content

git add plan.md system-overview.md
git commit -m "Update plan after Wave N completion"

git checkout main
```
```

**Benefits:**
- ✅ Follows Rule 6 (line 798): "Always use mcp__git__read_plan_file"
- ✅ Consistency between documentation and implementation
- ✅ Reads without branch switching (checkout still needed for writes)
- ✅ Cleaner separation of read vs write operations

**Limitation:** Still requires checkout for writes (until we add `mcp__git__update_plan_file`)

**Lines to Update:** 388-411 (Phase 4 update logic)

---

## Impact Analysis

### Quantitative Metrics

**Session Example:** 8 tasks across 3 waves

#### Current State
| Agent | MCP Calls | Git Queries |
|-------|-----------|-------------|
| Planner (3 waves) | 2 | ~10 |
| Workers (8 tasks) | 0 | 24 (3 per task: log, show x2, log main) |
| Orchestrator (3 waves) | 0 | 6 (2 per wave: show plan.md, grep) |
| **Total** | **2** | **40** |

**parse_plan_commit usage:** ❌ Never called

#### Optimized State
| Agent | MCP Calls | Git Queries |
|-------|-----------|-------------|
| Planner (3 waves) | 5 | ~6 |
| Workers (8 tasks) | 16 | 0 (all via MCP) |
| Orchestrator (3 waves) | 3 | 0 (all via MCP) |
| **Total** | **24** | **6** |

**parse_plan_commit usage:** ✅ Called 3 times (once per wave via orchestrator)

**Key Wins:**
- ✅ Git queries reduced: 40 → 6 (85% reduction)
- ✅ Structured JSON data instead of manual parsing
- ✅ parse_plan_commit finally used
- ✅ Deduplication via MCP tool caching

### Qualitative Benefits

1. **Reduced Prompt Complexity**
   - Workers no longer have parsing instructions
   - Cleaner, more maintainable prompts

2. **Improved Reliability**
   - Centralized parsing (one implementation, not N agents)
   - Less fragile (no grep patterns to break)

3. **Better Debugging**
   - MCP tools can log/instrument parsing
   - Easier to trace data flow

4. **Consistency**
   - All agents use same parser (parsers.py)
   - Documentation matches implementation

---

## Implementation Plan

### Phase 1: Worker Optimization (Highest Impact)

**Priority:** HIGH
**Rationale:** Workers are most numerous, biggest redundancy

**Files to Modify:**
1. `prompts/worker.md` lines 70-98 (Step 1)
2. `prompts/worker.md` lines 101-114 (Step 2)
3. `prompts/worker.md` lines 116-125 (Step 3)

**Changes:**
- Replace `git log` with `mcp__git__parse_task`
- Replace `git show plan:...` with `mcp__git__read_plan_file`
- Replace `git log main --merges | grep` with `mcp__git__get_provides`

**Testing:**
- Run single-task test: `flow-claude develop "add hello world function"`
- Verify worker uses MCP tools
- Check structured data is correctly consumed

---

### Phase 2: Orchestrator Optimization (parse_plan_commit Activation!)

**Priority:** HIGH
**Rationale:** Activates the unused parse_plan_commit() function

**Files to Modify:**
1. `prompts/orchestrator.md` lines 62-70 (Step 1)
2. `prompts/orchestrator.md` lines 194-203 (Step 6)

**Changes:**
- Replace `git show plan.md` with `mcp__git__parse_plan`
- Update wave detection logic to use structured task data
- Remove manual grep parsing

**Testing:**
- Run multi-wave test: `flow-claude develop "create 3-page website"`
- Verify orchestrator uses `mcp__git__parse_plan`
- Confirm parse_plan_commit() is called (add logging if needed)

---

### Phase 3: Planner Alignment

**Priority:** MEDIUM
**Rationale:** Consistency with documentation (Rule 6)

**Files to Modify:**
1. `prompts/planner.md` lines 388-411 (Phase 4)

**Changes:**
- Use `mcp__git__read_plan_file` to read before updating
- Keep checkout for writes (no change needed there)

**Testing:**
- Run multi-wave test
- Verify planner reads with MCP tool
- Confirm writes still work correctly

---

### Phase 4: Documentation Update

**Priority:** LOW
**Rationale:** Keep docs in sync

**Files to Modify:**
1. `CLAUDE.md` - Update "Current State Analysis" section
2. `README.md` - Update workflow descriptions if present

---

## Risks and Mitigation

### Risk 1: MCP Tool Bugs

**Risk:** MCP tools may have undiscovered bugs when used heavily
**Likelihood:** Low (tools already tested)
**Impact:** Medium (could block development sessions)
**Mitigation:**
- Test thoroughly in Phase 1 with simple tasks
- Keep bash fallback instructions in comments
- Add error handling to MCP tools

### Risk 2: Performance Regression

**Risk:** More MCP calls might be slower than bash
**Likelihood:** Very Low (MCP tools are optimized)
**Impact:** Low (small latency difference)
**Mitigation:**
- Benchmark before/after
- If needed, add caching layer

### Risk 3: Breaking Changes

**Risk:** Changing prompts might break existing behavior
**Likelihood:** Medium (prompts are complex)
**Impact:** High (broken sessions)
**Mitigation:**
- **Phase-by-phase rollout**
- Test each phase independently
- Keep git history for easy rollback
- Run integration tests after each phase

---

## Future Enhancements (Out of Scope)

### 1. Add `mcp__git__update_plan_file` Tool

**Purpose:** Update plan.md without git checkout
**Benefit:** Eliminate ALL branch switching in planner

**Implementation Sketch:**
```python
@tool("update_plan_file", "Update file on plan branch")
async def update_plan_file(args: dict):
    file_name = args["file_name"]
    content = args["content"]

    # Use git plumbing:
    # 1. hash-object to create blob
    # 2. update-index to stage
    # 3. commit-tree to commit
    # 4. update-ref to move branch

    # No checkout needed!
```

### 2. Add Caching Layer

**Purpose:** Cache `get_provides` results within session
**Benefit:** Further reduce redundant git queries

**Implementation Sketch:**
```python
# Session-scoped cache
_provides_cache = {}

def get_provides():
    session_id = get_current_session()
    if session_id in _provides_cache:
        return _provides_cache[session_id]

    result = query_git()
    _provides_cache[session_id] = result
    return result
```

### 3. Add `mcp__git__get_task_status` Tool

**Purpose:** Get current status of all tasks (ready, in_progress, blocked, complete)
**Benefit:** Orchestrator can determine wave membership without parsing plan.md

---

## Success Criteria

### Must Have (Phase 1-3)
- ✅ Workers use `mcp__git__parse_task`, `mcp__git__get_provides`, `mcp__git__read_plan_file`
- ✅ Orchestrator uses `mcp__git__parse_plan`
- ✅ parse_plan_commit() is called in real sessions
- ✅ All existing tests pass
- ✅ No performance regression

### Nice to Have
- ✅ Reduced git query count (measured)
- ✅ Improved prompt readability (subjective)
- ✅ Documentation updated

### Success Metrics
- **Git queries per session:** 40 → <10 (75% reduction target)
- **parse_plan_commit calls:** 0 → >0 (any usage is success)
- **Test pass rate:** 100% maintained
- **Session completion rate:** No decrease

---

## Approval and Next Steps

**Decision Needed:** Approve Phase 1-3 implementation?

**If Approved:**
1. Implement Phase 1 (worker.md)
2. Test with simple task
3. Implement Phase 2 (orchestrator.md)
4. Test with multi-wave task
5. Implement Phase 3 (planner.md)
6. Run full integration tests
7. Update documentation

**Estimated Effort:** 2-3 hours for Phases 1-3

---

## Appendix: File Locations Reference

```
flow-claude/
├── flow_claude/
│   ├── git_tools.py          # MCP tools (no changes needed)
│   └── parsers.py             # Parsers (parse_plan_commit @ 238-306)
│
├── prompts/
│   ├── worker.md              # MODIFY: Steps 1, 2, 3
│   ├── orchestrator.md        # MODIFY: Steps 1, 6
│   └── planner.md             # MODIFY: Phase 4
│
└── DESIGN_MCP_OPTIMIZATION.md # This document
```

---

---

## ARCHITECTURAL DECISION: Commit-Only Plan Storage (v2.0)

**Date:** 2025-01-06
**Decision:** Remove `plan.md` and `system-overview.md` files, store all plan data in commit messages

### Rationale

The current architecture has a **fundamental design conflict**:

1. **Parser Expects Commits:** `parse_plan_commit()` (parsers.py:238-306) parses commit messages
2. **Workflow Uses Files:** Agents read/write `plan.md` and `system-overview.md` files
3. **Result:** `parse_plan_commit()` is never used (tool exists but agents never call it)

**Root cause:** Agents use `git show plan.md` to read files instead of `git log` to read commits.

### Proposed Architecture: Commit-Only Plan Storage

**Core Principle:** All plan data lives in commit messages on the plan branch (no files).

**Benefits:**
- ✅ **Git-native:** Commits are immutable, versioned, auditable
- ✅ **Activates parse_plan_commit():** Tool becomes useful
- ✅ **Simpler workflow:** No file editing, just append commits
- ✅ **Consistent with tasks:** Task branches already use commit-only metadata
- ✅ **Better history:** Each wave update is a new commit with full context

**How Mutable State Works with Immutable Commits:**

Instead of editing `plan.md` to update task status, the planner writes **append-only commits**:

```bash
# Commit 1: Initialize plan v1
git commit -m "Initialize execution plan v1

## Session Information
Session ID: session-20250115-143000
User Request: Add user authentication
Created: 2025-01-15 14:30:00
Plan Version: v1

## Architecture
[system architecture description]

## Design Patterns
[design patterns in use]

## Technology Stack
[technologies used]

## Tasks
### Task 001
ID: 001
Description: Create User model
Status: pending
Preconditions: []
Provides: [User model class]
Estimated Time: 8 minutes

### Task 002
ID: 002
Description: Add authentication service
Status: pending
Preconditions: [User model class]
Provides: [Auth service]
Estimated Time: 10 minutes

## Estimates
Estimated Total Time: 40 minutes
Total Tasks: 5"

# Commit 2: Update after Wave 1
git commit -m "Update plan: Wave 1 complete

## Session Information
Session ID: session-20250115-143000
User Request: Add user authentication
Plan Version: v1

## Architecture
[updated architecture with learnings from Wave 1]

## Tasks
### Task 001
ID: 001
Description: Create User model
Status: complete  ← UPDATED
...

### Task 002
ID: 002
Description: Add authentication service
Status: ready  ← NOW READY (deps satisfied)
...

## Estimates
Completed: 1/5 tasks
Estimated Remaining: 32 minutes"
```

**Key insight:** Reading always gets the **latest commit** (`git log -n 1`), which contains the current state.

### Extended Commit Message Format

The planner will write commit messages with these sections:

```markdown
## Session Information
Session ID: session-YYYYMMDD-HHMMSS
User Request: [original request]
Created: [timestamp]
Plan Version: v1

## Architecture
[System architecture overview - what system-overview.md used to contain]
[Component relationships, data flow, interfaces]

## Design Patterns
[Design patterns in use]
[Why each pattern was chosen]

## Technology Stack
[Technologies, frameworks, libraries]
[Rationale for each choice]

## Tasks
### Task 001
ID: 001
Description: [task description]
Status: pending | ready | in_progress | complete | blocked
Preconditions: []
Provides: [List of capabilities]
Files: [List of files]
Estimated Time: [X minutes]
Priority: high | medium | low

### Task 002
[...]

## Estimates
Estimated Total Time: [X minutes]
Total Tasks: [N]
Completed: [M/N] tasks
```

### Implementation Plan

#### Phase 1: Extend Parser (~30 lines in parsers.py)

Update `parse_plan_commit()` to extract new sections:

```python
def parse_plan_commit(message: str) -> Dict[str, Any]:
    """Parse execution plan from plan branch commit."""
    sections = parse_commit_message(message)

    # Existing fields
    session_text = sections.get('session_information', '')

    # NEW: Extract architecture sections
    architecture_text = sections.get('architecture', '')
    design_patterns_text = sections.get('design_patterns', '')
    tech_stack_text = sections.get('technology_stack', '')

    # Parse tasks...

    return {
        'session_id': extract_field(session_text, 'Session ID'),
        'user_request': extract_field(session_text, 'User Request'),
        'plan_version': plan_version,
        'architecture': architecture_text,  # NEW
        'design_patterns': design_patterns_text,  # NEW
        'technology_stack': tech_stack_text,  # NEW
        'tasks': tasks,
        'total_tasks': len(tasks),
        'estimated_total_time': extract_field(estimates_text, 'Estimated Total Time'),
    }
```

#### Phase 2: Update planner.md (~80 lines)

**Phase 1 (Initial Plan Creation):**

Change from:
```bash
git checkout -b plan/session-{session_id}
# Create plan.md file
# Create system-overview.md file
git add plan.md system-overview.md
git commit -m "Initialize plan v1"
```

To:
```bash
git checkout -b plan/session-{session_id}
git commit --allow-empty -m "[structured commit message with all sections]"
```

**Phase 4 (Update After Wave):**

Change from:
```bash
git checkout plan/session-{session_id}
# Edit plan.md - update task status
# Edit system-overview.md - add learnings
git add plan.md system-overview.md
git commit -m "Update plan"
```

To:
```bash
git checkout plan/session-{session_id}
# Read latest commit to get current state
git log -n 1 --format=%B > /tmp/current-plan.txt
# Update task statuses, add learnings
git commit --allow-empty -m "[full updated plan with new status]"
```

**Phase 5 (Final Report):**

Same pattern - append final commit with complete summary.

#### Phase 3: Update orchestrator.md (~10 lines)

**Step 1: Read plan to identify task branches**

Change from:
```bash
git show plan/{plan_branch}:plan.md
```

To:
```python
plan = mcp__git__parse_plan({"branch": "plan/session-20250115-143000"})
# Access: plan["tasks"], plan["architecture"], plan["session_id"]
```

**Step 6: Check if more waves remain**

Change from:
```bash
git show plan/{plan_branch}:plan.md | grep "status.*pending"
```

To:
```python
plan = mcp__git__parse_plan({"branch": "plan/session-20250115-143000"})
pending_tasks = [t for t in plan["tasks"] if t["status"] == "pending"]
if pending_tasks:
    # More waves remain
```

#### Phase 4: Update worker.md (~10 lines)

**Step 2: Understand Session Context**

Change from:
```bash
git show plan/session-YYYYMMDD-HHMMSS:system-overview.md
git show plan/session-YYYYMMDD-HHMMSS:plan.md
```

To:
```python
plan = mcp__git__parse_plan({"branch": "plan/session-YYYYMMDD-HHMMSS"})
# Access:
# - plan["architecture"] (was system-overview.md)
# - plan["design_patterns"] (was system-overview.md)
# - plan["technology_stack"] (was system-overview.md)
# - plan["tasks"] (was plan.md)
```

#### Phase 5: Remove mcp__git__read_plan_file (~110 lines)

Remove function from `flow_claude/git_tools.py` lines 294-401.

**Rationale:** No longer needed since agents don't read plan files anymore.

#### Phase 6: Update DESIGN_MCP_OPTIMIZATION.md

Add this architectural decision section (this document!).

### Impact on Previous Optimization Plan

**Previous plan metrics (from v1.0):**

| Agent | MCP Calls | Git Queries |
|-------|-----------|-------------|
| Planner (3 waves) | 5 | ~6 |
| Workers (8 tasks) | 16 | 0 |
| Orchestrator (3 waves) | 3 | 0 |
| **Total** | **24** | **6** |

**NEW metrics (commit-only architecture):**

| Agent | MCP Calls | Git Queries |
|-------|-----------|-------------|
| Planner (3 waves) | 3 (get_provides only) | ~6 (writes only) |
| Workers (8 tasks) | 16 (parse_task, get_provides, parse_plan) | 0 |
| Orchestrator (3 waves) | 3 (parse_plan) | 0 |
| **Total** | **22** | **6** |

**Key differences:**
- ✅ Planner no longer needs `read_plan_file` calls (2 fewer MCP calls)
- ✅ Workers use `parse_plan` instead of `read_plan_file` (same count, better structure)
- ✅ Orchestrator uses `parse_plan` for structured task data
- ✅ `parse_plan_commit()` finally activated!
- ✅ `mcp__git__read_plan_file` tool removed entirely

### Risks and Mitigation

**Risk 1: Large commit messages**
- **Concern:** Commit messages might get large (8 tasks × 100 lines each)
- **Mitigation:** Git handles large commits fine; this is standard practice
- **Precedent:** Linux kernel commits can be 10,000+ lines

**Risk 2: Loss of file-based diffing**
- **Concern:** Can't use `git diff plan.md` to see what changed
- **Mitigation:** Use `git log -p` to see commit-to-commit diffs
- **Better:** Each wave update is explicit, not incremental file edits

**Risk 3: Breaking existing behavior**
- **Concern:** Major architectural change might break workflows
- **Mitigation:**
  - Thorough testing with small tasks first
  - Phase-by-phase rollout
  - Keep git history for easy rollback

### Testing Plan

1. **Unit tests:** Update `tests/test_parsers.py` to test new architecture fields
2. **Integration test:** Run simple 2-task session, verify plan commits parse correctly
3. **Multi-wave test:** Run 6-task session with 2 waves, verify wave updates work
4. **Large test:** Run 10-task session with 3 waves, verify scalability

### Decision Rationale Summary

**Why commit-only?**

1. **Consistency:** Tasks already use commit-only metadata (why should plans be different?)
2. **Git-first philosophy:** Flow-Claude's core principle is "git as single source of truth"
3. **Activate unused code:** `parse_plan_commit()` exists but is never used
4. **Immutability:** Commits are immutable, auditable, versioned
5. **Simplicity:** No file editing, just append commits
6. **Better history:** Each wave is a commit, easy to see progression

**Why NOT file-based?**

1. **Mutation complexity:** Editing files requires checkout, edit, add, commit cycle
2. **Parser mismatch:** Parser expects commits, workflow uses files
3. **Tool waste:** We built `parse_plan_commit()` but never use it
4. **Inconsistency:** Tasks use commits, plans use files (confusing!)

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-06 | Initial design document with MCP optimization plan |
| 2.0 | 2025-01-06 | Added commit-only architecture decision, removed plan.md/system-overview.md files |
