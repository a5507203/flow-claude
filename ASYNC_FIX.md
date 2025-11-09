# Async/Await Fix for Command Autocomplete

## The Error

```
RuntimeWarning: coroutine 'Application.run_async' was never awaited
  continue
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

## Root Cause

The `get_request()` method was calling `questionary.autocomplete().ask()` which returns a coroutine, but:
1. The method itself was NOT async
2. The coroutine was NOT being awaited
3. This caused the coroutine to be created but never executed

## The Fix

### Step 1: Made `get_request()` Async
```python
# Before
def get_request(self, show_banner: bool = True) -> str:

# After
async def get_request(self, show_banner: bool = True) -> str:
```

### Step 2: Used `ask_async()` with `await`
```python
# Before (wrong - returns unawaited coroutine)
request = questionary.autocomplete(...).ask()

# After (correct - awaits the coroutine)
request = await questionary.autocomplete(...).ask_async()
```

### Step 3: Added `await` to Caller
```python
# In run() method

# Before
request = self.get_request(show_banner=False)

# After
request = await self.get_request(show_banner=False)
```

## Complete Async Chain

```
run() [async]                                          # Already async
  ├→ await check_and_prompt_init() [async]            # Already fixed
  │   └→ await setup_flow_branch() [async]            # Already fixed
  │       └→ await questionary.select().ask_async()   # Already fixed
  │
  └→ await get_request() [async]                      # NEWLY FIXED
      └→ await questionary.autocomplete().ask_async() # NEWLY FIXED
```

## Why This Matters

### The Problem with `.ask()`
```python
questionary.autocomplete(...).ask()
```
- Uses `asyncio.run()` internally
- Creates a NEW event loop
- Fails when already inside an event loop (like our `run()` method)
- Error: "asyncio.run() cannot be called from a running event loop"

### The Solution with `.ask_async()`
```python
await questionary.autocomplete(...).ask_async()
```
- Returns a coroutine to be awaited
- Uses the EXISTING event loop
- Works perfectly inside async functions
- No event loop conflicts

## Files Changed

1. **cli_controller.py line 831**: `async def get_request()`
2. **cli_controller.py line 869**: `await questionary.autocomplete(...).ask_async()`
3. **cli_controller.py line 99**: `request = await self.get_request()`

## Testing Status

The autocomplete feature still requires a real Windows terminal (cmd.exe or PowerShell) to work, but now:
- ✅ No more runtime warnings
- ✅ Proper async/await chain
- ✅ Graceful fallback to simple input
- ✅ Clear error messages in debug mode

## Environment Detection

The code now detects non-interactive environments:
```python
is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
```

And provides helpful feedback:
```
Note: Using simple input mode. Type \help for commands.
```

## Next Steps for User

To test the autocomplete feature:
1. Open **cmd.exe** or **PowerShell** (not Claude Code terminal)
2. Run: `python -m flow_claude.commands.flow_cli`
3. Type `\` at the prompt
4. See the autocomplete dropdown appear!

The feature will gracefully fall back to simple input in non-interactive environments like:
- Claude Code's Bash tool
- CI/CD pipelines
- SSH without PTY
- Git Bash / Cygwin
