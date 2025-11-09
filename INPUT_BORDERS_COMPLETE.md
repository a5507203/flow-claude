# Input Borders - Complete Implementation

## User Requirement

> "the implementation should like this. there always have two line even for input area"

**Visual Design:**
```
[top border line]
  > [input area]
[bottom border line]
```

This should apply to **ALL** input prompts throughout the application, not just the main request prompt.

## All Input Areas Now Have Borders

### 1. Main Development Request (get_request)
**Lines 873-880:**
```
==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  > create a new feature
==============================================================================
```

Or for subsequent requests:
```
------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > add authentication
==============================================================================
```

### 2. User Proxy - Additional Requirements (During Execution)
**Lines 432-437:**
```
------------------------------------------------------------------------------
  > Additional requirement: make it responsive
------------------------------------------------------------------------------
```

### 3. CLAUDE.md Initialization Prompt
**Lines 764-766:**
```
------------------------------------------------------------------------------
  Would you like to initialize CLAUDE.md now? (y/n): y
------------------------------------------------------------------------------
```

### 4. Slash Command: \parallel
**Lines 961-963:**
```
------------------------------------------------------------------------------
  Max parallel workers (current: 3): 5
------------------------------------------------------------------------------
```

### 5. Slash Command: \model
**Lines 977-979:**
```
------------------------------------------------------------------------------
  Select model: opus
------------------------------------------------------------------------------
```

### 6. Simple Input Mode Fallback (get_request)
**Line 928:**
Already inside the bordered area from lines 873-880, so it automatically has borders.

### 7. Input Loop - Initial Prompt (During Session)
**Lines 266-267:**
```
------------------------------------------------------------------------------
  > [user input during session]
------------------------------------------------------------------------------
```

### 8. Input Loop - Empty Input Re-prompt
**Lines 281-282:**
```
------------------------------------------------------------------------------
  > [re-prompt after empty input]
------------------------------------------------------------------------------
```

### 9. Input Loop - After Stop Command
**Lines 321-322:**
```
------------------------------------------------------------------------------
  > [prompt after \stop command]
------------------------------------------------------------------------------
```

### 10. Input Loop - After Follow-up Request
**Lines 348-349:**
```
------------------------------------------------------------------------------
  > [prompt after processing follow-up]
------------------------------------------------------------------------------
```

## Visual Consistency

All input areas now follow the same pattern:
1. **Top border**: `----` (78 characters)
2. **Input prompt**: Prefixed with `  > ` or custom text
3. **Bottom border**: `----` (78 characters)

**Exception:** Main request prompts use `====` for the first request and `----` for subsequent ones.

## Code Changes Summary

| Location | Lines | Input Type | Border Added |
|----------|-------|------------|--------------|
| get_request() | 873-880 | Main development request | ✅ Top (before while loop) |
| get_request() | 935 | Main request (return) | ✅ Bottom |
| User proxy | 432, 437 | Additional requirement | ✅ Top & Bottom |
| CLAUDE.md init | 764, 766 | y/n prompt | ✅ Top & Bottom |
| \parallel cmd | 961, 963 | Number input | ✅ Top & Bottom |
| \model cmd | 977, 979 | Model selection | ✅ Top & Bottom |
| Input loop initial | 266-267, 276 | Session start prompt | ✅ Top & Bottom |
| Input loop empty | 281-282 | Re-prompt | ✅ Top & Bottom |
| Input loop stop | 321-322 | After \stop | ✅ Top & Bottom |
| Input loop follow-up | 348-349 | After request | ✅ Top & Bottom |

## Benefits

✅ **Visual Consistency**: Every input area looks the same
✅ **Clear Separation**: Easy to distinguish input from output
✅ **Professional Appearance**: Clean, organized interface
✅ **User Focus**: Borders draw attention to where user should type
✅ **Works Everywhere**: Uses simple ASCII characters - no special terminal features needed

## Example Session Flow

```
+------------------------------------------------------------------------------+
|  Flow-Claude v6.7                                                            |
+------------------------------------------------------------------------------+

  Available Commands:
    \parallel  - Set max parallel workers
    ...

==============================================================================
  Enter your request below (or use \help for commands):
==============================================================================
  > create a blog backend
==============================================================================

  Log file: .flow-claude\logs\session-...

============================================================
Flow-Claude V6.6 Development Session Starting...
============================================================

[Agents working...]

------------------------------------------------------------------------------
  > Additional requirement: add caching
------------------------------------------------------------------------------

[Agents continue...]

Session complete.

------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > \parallel
==============================================================================

------------------------------------------------------------------------------
  Max parallel workers (current: 3): 5
------------------------------------------------------------------------------

  → Set max parallel workers to 5

------------------------------------------------------------------------------
  Next request:
------------------------------------------------------------------------------
  > add frontend
==============================================================================

[Development continues...]
```

## Implementation Complete

All input areas throughout the Flow-Claude CLI now have consistent top and bottom borders, making it crystal clear where users should provide input.
