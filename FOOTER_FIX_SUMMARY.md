# Fixed Footer - Final Implementation

## Problem
The footer was appearing on the same line as agent messages, causing visual clutter:
```
  > hi [ORCH] Orchestrator: Processing...
```

## Root Cause
1. User types input: `> hi` and presses Enter
2. The input line stays on screen
3. Footer was being enabled at wrong time
4. Agent messages were printing without proper separation

## Solution

### Flow Order
1. User types and presses Enter
2. Input is received by `_check_for_esc_or_input()`
3. Check if input is empty - if empty, don't enable footer (continue waiting)
4. If input is valid, **enable footer FIRST** (with newline)
5. Then process the input (queue request)
6. Agent messages print using `print_with_footer()` which keeps footer at bottom

### Key Code Changes

#### cli_controller.py - Input Loop
```python
# Got text input
user_input = esc_pressed.strip()

# Handle empty input first
if not user_input:
    continue

# Enable footer after receiving actual input (not empty)
if not footer_enabled:
    footer_enabled = True
    self.rich_ui.enable_fixed_footer(footer_text)

# Now process the input...
```

#### cli_rich_ui.py - Enable Footer
```python
def enable_fixed_footer(self, footer_text: str):
    self.fixed_footer_enabled = True
    self.footer_text = footer_text
    # Print newline first to separate from previous content
    self.console.print()
    self._print_footer()
```

#### cli.py - Print Request
```python
# Use Rich UI to print request processing
if _rich_ui:
    _rich_ui.console.print()
    _rich_ui.print_user_message(user_request, is_followup=False)
else:
    click.echo(f"\n[REQUEST] Processing: {user_request}\n")
```

## Result

### Before Fix
```
  > hi [ORCH] Orchestrator: Processing...
[PLAN] Planner: Creating plan...
Press ESC to interrupt | Type for follow-up | \q to quit
```

### After Fix
```
  > hi

[REQUEST] hi

Press ESC to interrupt | Type for follow-up | \q to quit
[ORCH] Orchestrator: Processing...
[PLAN] Planner: Creating plan...
Press ESC to interrupt | Type for follow-up | \q to quit  ← Stays here!
```

## How It Works

1. **Input Phase**: User types, no footer visible
2. **Footer Activation**: After Enter, footer appears with newline separation
3. **Execution Phase**: All messages use `print_with_footer()`:
   - Clear footer line (move up, clear)
   - Print message
   - Reprint footer

## Visual Flow

```
Terminal State 1 (Waiting for input):
  > _


Terminal State 2 (User types "hi"):
  > hi_


Terminal State 3 (User presses Enter, footer activates):
  > hi

Press ESC to interrupt | Type for follow-up | \q to quit


Terminal State 4 (Request processing starts):
  > hi

[REQUEST] hi

Press ESC to interrupt | Type for follow-up | \q to quit


Terminal State 5 (Agent messages scroll):
  > hi

[REQUEST] hi

[ORCH] Orchestrator: Processing...
[PLAN] Planner: Creating plan...
Press ESC to interrupt | Type for follow-up | \q to quit  ← Fixed position
```

## Key Points

1. ✅ Footer only appears after non-empty input
2. ✅ Footer appears below the input line (not above)
3. ✅ Footer stays at bottom while messages scroll
4. ✅ Clean visual separation with newlines
5. ✅ Works with both initial and follow-up requests

## Testing

Run the CLI and type "hi":
```bash
python -m flow_claude.commands.flow_cli
```

Expected:
- You type `> hi` and press Enter
- Footer appears on new line below
- Request message appears
- Agent messages scroll above footer
- Footer stays at bottom
