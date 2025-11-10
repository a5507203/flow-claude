# Fixed Footer Feature

## Overview

The Rich UI now supports a **fixed footer** that stays at the bottom of the terminal while content scrolls above it. This is perfect for displaying input prompts and status information that should always be visible.

## How It Works

The fixed footer uses ANSI escape sequences to:
1. Clear the footer line before printing new content
2. Print the new content
3. Reprint the footer at the bottom

This creates the visual effect of the footer staying in place while messages scroll above it.

## Usage

### Enable Fixed Footer

```python
ui = RichUI()
ui.enable_fixed_footer("Press ESC to interrupt | Type for follow-up | \\q to quit")
```

### Print Messages

All print methods automatically handle the footer:

```python
ui.print_agent_message("orchestrator", "Processing your request...")
ui.print_success("Task completed!")
ui.print_warning("Resource limit approaching")
```

The footer will stay at the bottom, and messages will scroll above it.

### Update Footer Text

```python
ui.update_footer("New prompt text here")
```

### Disable Fixed Footer

```python
ui.disable_fixed_footer()
```

## Integration with CLI

The CLI controller enables the fixed footer **after the first input** is received:

```python
async def input_loop(self):
    footer_enabled = False
    footer_text = "Press ESC to interrupt | Type for follow-up | \\q to quit"

    while not self.shutdown_requested:
        user_input = await get_input()

        # Enable footer after first input
        if not footer_enabled:
            footer_enabled = True
            self.rich_ui.enable_fixed_footer(footer_text)

        # ... process input ...

    # Disable when done
    self.rich_ui.disable_fixed_footer()
```

**Why after input?**
This ensures the footer appears BELOW the input line, not above it:

```
User types:
  > hi

Footer appears here:
Press ESC to interrupt | Type for follow-up | \q to quit

Then messages scroll above:
[ORCH] Processing...
[PLAN] Creating plan...
───────────────────────────────────────
Press ESC to interrupt | Type for follow-up | \q to quit  ← Stays here
```

## Visual Example

```
[ORCH] Orchestrator: Starting execution plan
[PLAN] Planner: Creating 5 tasks
[WORK] Worker: Implementing task 001
[OK] Task 001 completed
[WORK] Worker: Implementing task 002
─────────────────────────────────────────────
Press ESC to interrupt | Type for follow-up | \q to quit  ← Always at bottom
```

As new messages appear, they push older messages up, but the footer stays fixed at the bottom.

## Technical Details

### ANSI Escape Codes

The footer uses these ANSI codes:
- `\033[1A` - Move cursor up one line
- `\033[2K` - Clear entire line

### Footer Clearing Algorithm

```python
def _clear_footer(self):
    if self.footer_text:
        # Count lines in footer (support multi-line footers)
        lines = self.footer_text.count('\n') + 1
        for _ in range(lines):
            # Move up and clear each line
            self.console.file.write('\033[1A\033[2K')
        self.console.file.flush()
```

### Footer-Aware Printing

```python
def print_with_footer(self, *args, **kwargs):
    if self.fixed_footer_enabled:
        self._clear_footer()

    self.console.print(*args, **kwargs)

    if self.fixed_footer_enabled:
        self._print_footer()
```

## Methods Updated

All user-facing print methods now use `print_with_footer()`:

- `print_agent_message()`
- `print_tool_use()`
- `print_tool_result()`
- `print_error()`
- `print_warning()`
- `print_success()`
- `print_info()`
- `print_user_message()`
- `_print_highlighted_message()` (for key actions)

## Limitations

1. **Terminal Support**: Requires a terminal that supports ANSI escape codes (works on most modern terminals, Windows 10+, Unix/Linux)

2. **Line Wrapping**: If the footer text is wider than the terminal, it will wrap and may cause visual issues

3. **Multi-line Footers**: Supported, but increases the number of lines to clear/reprint

4. **Screen Clearing**: Calling `console.clear()` will remove the footer (need to call `enable_fixed_footer()` again)

## Benefits

1. **Always Visible Prompts**: Users always know what actions are available
2. **Better UX**: No need to scroll up to see what keys to press
3. **Clean Separation**: Clear visual separation between scrolling content and static controls
4. **Professional Look**: Similar to tools like `htop`, `vim`, and other TUI applications

## Testing

Run the test script to see the footer in action:

```bash
python test_fixed_footer.py
```

This will print multiple messages over time, demonstrating how the footer stays at the bottom while content scrolls above it.
