# Flow Branch Workflow - Implementation Summary

## Changes Completed

### 1. Added Questionary Dependency
- **File:** `pyproject.toml`
- **Change:** Added `questionary>=2.1.0` to dependencies
- **Purpose:** Interactive UI features:
  - Arrow-key menu selection for branch choices
  - Autocomplete dropdown for slash commands

### 2. Implemented Flow Branch Setup
- **File:** `flow_claude/cli_controller.py`
- **Changes:**
  - Made `check_and_prompt_init()` async (line 723)
  - Made `setup_flow_branch()` async (line 610)
  - Added await to method call on line 87
  - Added await to `setup_flow_branch()` call on line 732
  - Implemented interactive branch selection using questionary (lines 683-694)

### 3. Implemented Command Autocomplete
- **File:** `flow_claude/cli_controller.py`
- **Changes:**
  - Made `get_request()` async (line 831)
  - Replaced `input()` with `await questionary.autocomplete().ask_async()` (lines 869-879)
  - Added await to `get_request()` call in `run()` method (line 99)
  - Added slash command list with descriptions (lines 848-859)
  - Implemented TTY detection (line 846)
  - Implemented graceful fallback to regular input if questionary fails
  - Added debug output option to show why questionary failed
  - Added `\q` as alias for `\exit` command (line 992)

- **Flow Branch Workflow:**
  1. On startup, checks if "flow" branch exists
  2. If not, shows all local branches in interactive menu
  3. User selects base branch using arrow keys (or j/k)
  4. Creates "flow" branch from selected base
  5. Switches to flow branch for work

- **Command Autocomplete Workflow:**
  1. User types at the prompt `  > `
  2. When typing `\`, autocomplete dropdown appears showing all commands
  3. User can:
     - Continue typing to filter (e.g., `\pa` shows `\parallel`)
     - Use arrow keys to select from dropdown
     - Press Enter to complete
  4. System extracts command and executes it

### 4. Updated Git Tools
- **File:** `flow_claude/git_tools.py`
- **Changes:** Replaced all "master"/"main" references with "flow"
  - Line 247-248: Query flow branch for merge commits
  - Line 539, 543: Create plan branches from flow
  - Line 871, 875: Create task branches from flow

### 5. Updated Agent Prompts
- **Files:** `prompts/orchestrator.md`, `prompts/worker.md`, `prompts/planner.md`
- **Changes:** Updated all merge targets and branch references to use "flow" instead of "main"

### 6. Updated Documentation
- **File:** `CLAUDE.md`
- **Changes:** Added "Flow Branch Workflow" section explaining the new behavior

## How to Test

### IMPORTANT: Must Run in Real Terminal

The questionary library requires a **real Windows console** (cmd.exe or PowerShell) to work properly. It cannot run in Claude Code's Bash tool.

### Installation

```bash
# 1. Install dependencies first
pip install -e .
```

### Testing in cmd.exe

```bash
# 2. Open cmd.exe (Windows Command Prompt)

# 3. Navigate to your project directory
cd C:\path\to\your\project

# 4. Run the interactive CLI
python -m flow_claude.commands.flow_cli
```

### Expected Behavior

#### 1. Flow Branch Setup (First Run)
1. You'll see the welcome banner
2. Flow branch setup screen appears
3. Interactive menu shows all your local branches:
   ```
   Select base branch for flow branch:

     → main
       develop
       feature/xyz
   ```
4. Use arrow keys (↑/↓) or j/k to navigate
5. Press Enter to select
6. Flow branch is created from your selection

#### 2. Command Autocomplete
7. System proceeds to request input: `  > `
8. When you start typing `\`, autocomplete dropdown appears:
   ```
     > \

     \parallel - Set maximum number of parallel workers
     \model - Select Claude model (sonnet/opus/haiku)
     \verbose - Toggle verbose output
     \debug - Toggle debug mode
     \auto - Toggle user agent (autonomous decisions)
     \init - Generate CLAUDE.md template
     \help - Show help message
     \exit - Exit Flow-Claude
     \q - Exit Flow-Claude
   ```
9. You can:
   - Type to filter (e.g., `\mo` filters to `\model`)
   - Use arrow keys to select
   - Press Enter to execute command
   - Type any regular text for development requests

### Questionary Features Used

**Branch Selection (questionary.select):**
- Arrow key navigation (↑/↓)
- Vim-style navigation (j/k)
- Clear visual indicator (→)
- Instruction text at bottom
- Default selection (current branch or first branch)

**Command Autocomplete (questionary.autocomplete):**
- Real-time filtering as you type
- Arrow key navigation through matches
- Match highlighting
- Accepts any input (not restricted to list)
- Graceful fallback to regular input on errors

## Technical Details

### Async Chain

The complete async chain is:
```
run() [async]
  ├→ await check_and_prompt_init() [async]
  │   └→ await setup_flow_branch() [async]
  │       └→ await questionary.select().ask_async() [async]
  │
  └→ await get_request() [async]
      └→ await questionary.autocomplete().ask_async() [async]
```

### Why ask_async() Instead of ask()

- `ask()`: Blocking, uses `asyncio.run()` internally
- `ask_async()`: Non-blocking coroutine
- Since we're already in an async context (`run()` is async), we must use `ask_async()`

### Error Handling

The `setup_flow_branch()` method includes:
- Try/except for subprocess errors
- Git command validation
- Graceful error messages
- Automatic branch switching

## Known Limitations

1. **Non-Interactive Environments:** Will not work in:
   - Claude Code Bash tool
   - SSH sessions without PTY
   - CI/CD pipelines
   - Automated scripts

2. **Windows Console Required:** The questionary library specifically requires a Windows console on Windows systems.

## Next Steps

To add non-interactive fallback (if needed):
1. Detect if stdin is a TTY using `sys.stdin.isatty()`
2. Fall back to numbered input like before
3. Add environment variable check (e.g., `FLOW_CLAUDE_INTERACTIVE=0`)

## Files Modified

1. `pyproject.toml` - Added questionary dependency
2. `flow_claude/cli_controller.py` - Flow branch setup + async fixes
3. `flow_claude/git_tools.py` - Changed master→flow references
4. `flow_claude/prompts/orchestrator.md` - Updated branch references
5. `flow_claude/prompts/worker.md` - Updated merge targets
6. `flow_claude/prompts/planner.md` - Updated tool descriptions
7. `CLAUDE.md` - Added flow branch documentation

## Testing Checklist

- [ ] Install dependencies: `pip install -e .`
- [ ] Open cmd.exe or PowerShell
- [ ] Navigate to test git repository
- [ ] Run: `python -m flow_claude.commands.flow_cli`
- [ ] Verify interactive branch menu appears
- [ ] Use arrow keys to select branch
- [ ] Verify flow branch is created
- [ ] Verify system continues to request input
- [ ] Test full workflow with actual development request
