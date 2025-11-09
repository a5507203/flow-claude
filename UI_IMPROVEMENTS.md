# UI Improvements - Input Borders and Layout

## What Was Requested

> "we should have top border and bottom for the input to clearly separate other content"

## Bug Report

> "we can only see the border first time"

**Issue:** Borders were only showing on the very first prompt, not on subsequent requests after development sessions completed.

**Root Cause:** The border logic was inside the `while True` loop that handles slash command retries, not outside where it should execute once per `get_request()` call.

**Fix:**
1. Moved border display logic outside the while loop
2. Added `is_first_request` parameter to track first vs subsequent requests
3. Track `is_first_request` flag in the main `run()` loop

## What Was Implemented

### 1. Input Borders

Added clear visual borders around the input prompt to separate it from other content.

**First Request:**
```
==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  > create a new user authentication system
==============================================================================

[Development begins...]
```

**Subsequent Requests:**
```
------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > add password reset functionality
==============================================================================

[Development continues...]
```

### 2. Improved Welcome Banner

Updated to show all commands clearly with better formatting:

```
+------------------------------------------------------------------------------+
|                                                                              |
|  Flow-Claude v6.7                                                            |
|  Git-First Autonomous Development System                                     |
|                                                                              |
+------------------------------------------------------------------------------+

  Available Commands:
    \parallel  - Set max parallel workers
    \model     - Select Claude model
    \verbose   - Toggle verbose output
    \debug     - Toggle debug mode
    \auto      - Toggle autonomous mode
    \init      - Generate CLAUDE.md
    \help      - Show help
    \exit      - Exit Flow-Claude

  Tip: Type '\' to see autocomplete suggestions (in terminal)
  While agents work: Type follow-up requests or '\stop' to cancel
  Quit: Type '\exit' or '\q'

==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  >
```

## Visual Hierarchy

### Before (Old Layout)
```
Flow-Claude v6.7
Git-First Autonomous Development System

Enter your development request below:
----------------------------------------------------------------------------

Commands: \parallel, \model, \verbose, \debug, \init, \auto, \help
While agents work: Type follow-up requests anytime, or '\stop' to cancel
Quit: Type '\q', '\exit', 'q', or press Ctrl+C

  > [user input]

[Output immediately follows with no separation]
```

**Problems:**
- Input prompt blends with surrounding text
- Hard to see where to type
- No clear visual separation

### After (New Layout)
```
+------------------------------------------------------------------------------+
|                                                                              |
|  Flow-Claude v6.7                                                            |
|  Git-First Autonomous Development System                                     |
|                                                                              |
+------------------------------------------------------------------------------+

  Available Commands:
    \parallel  - Set max parallel workers
    \model     - Select Claude model
    [... etc ...]

  Tip: Type '\' to see autocomplete suggestions (in terminal)

==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  > create a new feature
==============================================================================

[Output starts here with clear separation]
```

**Benefits:**
- ✅ Clear visual separation with borders
- ✅ Input area stands out prominently
- ✅ Easy to locate where to type
- ✅ Commands listed clearly upfront
- ✅ Professional appearance

## Border Styles

### First Request
- **Top border**: `====` (double line, 78 chars)
- **Label**: "Enter your request below (or use \help for commands):"
- **Bottom border**: `====` (double line, 78 chars)

### Subsequent Requests
- **Top border**: `----` (single line, 78 chars)
- **Label**: "Next request:"
- **Bottom border**: `====` (double line, 78 chars)

### After Command Execution
Commands like `\help`, `\model` don't show bottom border - only actual requests do.

## Code Changes

### File: `cli_controller.py`

**Line 837**: Added `is_first_request` parameter
```python
async def get_request(self, show_banner: bool = True, is_first_request: bool = True) -> str:
```

**Lines 872-880**: Border logic (outside while loop)
```python
# Show input border (once per get_request call)
if is_first_request:
    print("\n" + "=" * 78)
    print("  Enter your request below (or use \\help for commands):")
    print("=" * 78)
else:
    print("\n" + "-" * 78)
    print("  Next request:")
    print("-" * 78)

while True:  # Then enter the input loop
```

**Lines 97-107**: Track first request in run() loop
```python
is_first_request = True
while not self.should_exit_cli:
    # Get development request from user
    request = await self.get_request(show_banner=False, is_first_request=is_first_request)
    is_first_request = False  # After first request, all subsequent are not first
```

**Lines 933-936**: Added bottom border after input
```python
# Regular request
if request:
    # Show bottom border after receiving request
    print("=" * 78 + "\n")
    return request
```

**Lines 70-82**: Improved welcome banner
```python
print("  Available Commands:")
print("    \\parallel  - Set max parallel workers")
print("    \\model     - Select Claude model")
# ... etc
print()
print("  Tip: Type '\\' to see autocomplete suggestions (in terminal)")
```

## Example Full Session

```
+------------------------------------------------------------------------------+
|                                                                              |
|  Flow-Claude v6.7                                                            |
|  Git-First Autonomous Development System                                     |
|                                                                              |
+------------------------------------------------------------------------------+

  Available Commands:
    \parallel  - Set max parallel workers
    \model     - Select Claude model
    \verbose   - Toggle verbose output
    \debug     - Toggle debug mode
    \auto      - Toggle autonomous mode
    \init      - Generate CLAUDE.md
    \help      - Show help
    \exit      - Exit Flow-Claude

  Tip: Type '\' to see autocomplete suggestions (in terminal)
  While agents work: Type follow-up requests or '\stop' to cancel
  Quit: Type '\exit' or '\q'

==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  > create a blog backend API
==============================================================================

[Planner creates plan and tasks...]
[Workers execute tasks...]
[Development completes...]

------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > add user authentication
==============================================================================

[Development continues...]

------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > \exit
==============================================================================

  Exiting Flow-Claude...
```

## Benefits

1. **Visual Clarity**: Input area clearly separated from output
2. **User Focus**: Easy to find where to type
3. **Professional**: Clean, organized appearance
4. **Consistency**: Same border style throughout session
5. **Readability**: Clear distinction between prompts and content

## Testing

The borders work in all environments:
- ✅ Windows cmd.exe
- ✅ PowerShell
- ✅ Claude Code terminal
- ✅ Git Bash
- ✅ SSH sessions

No special terminal features required - just basic ASCII characters.
