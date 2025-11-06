# Flow-Claude Simple CLI Design

**Version:** 1.0
**Date:** 2025-01-06
**Approach:** Plain CLI with `input()` and `print()` - No TUI libraries

---

## Vision: Simple, Interruptible CLI

One command. Simple prompts. Streaming output. Press ESC to add requirements.

```
$ flow
> Enter request: Create a blog
[Execution starts, logs stream...]
(Press ESC anytime to add requirements)
```

---

## User Experience

### Step 1: Launch Flow

```bash
$ cd my-project
$ flow
```

### Step 2: Input Screen (Plain CLI)

```
Flow-Claude v6.7
================================================================

Recent sessions:
  - session-20250106-120000: Create blog (2h ago)
  - session-20250105-163000: Add file upload (Complete)

> Enter development request: Create a NeurIPS 2028 conference website

Starting session...
```

### Step 3: Execution (Streaming Logs)

```
[14:30:15] Session: session-20250106-143000
[14:30:15] Request: Create a NeurIPS 2028 conference website
[14:30:16] Orchestrator: Starting session
[14:30:17] Spawning planner subagent
[14:30:19] Planner: Analyzing codebase structure
[14:30:22] Planner: Creating execution plan
[14:30:25] Planner: Created plan branch plan/session-20250106-143000
[14:30:26] Planner: Breaking request into tasks
[14:30:30] Planner: Created Wave 1 with 3 tasks
[14:30:30]   - task/001-base-structure
[14:30:30]   - task/002-home-page
[14:30:30]   - task/003-navigation
[14:30:32] Orchestrator: Spawning 3 workers for Wave 1
[14:30:33] Worker-1: Starting task/001-base-structure
[14:30:33] Worker-2: Starting task/002-home-page
[14:30:33] Worker-3: Starting task/003-navigation
[14:30:35] Worker-1: [task-001] Design: Project structure planning
[14:30:38] Worker-2: [task-002] Design: Home page layout
[14:30:40] Worker-3: [task-003] Design: Navigation component design
[14:30:45] Worker-1: [task-001] Implement: Create directory structure (1/5)
[14:30:47] Worker-2: [task-002] Implement: Add HTML boilerplate (1/6)
[14:30:48] Worker-3: [task-003] Implement: Create nav component (1/4)

(Press ESC to interrupt and add requirements)
```

### Step 4: User Presses ESC

```
[14:31:02] Worker-1: [task-001] Implement: Add package.json (3/5)
[14:31:04] Worker-2: [task-002] Implement: Add hero section (3/6)

================================================================
INTERVENTION MODE - Session Paused
================================================================

Current request: Create a NeurIPS 2028 conference website
Progress: Wave 1/3 (3 tasks in progress)
  - task/001-base-structure [worker-1]: 60% complete (3/5)
  - task/002-home-page [worker-2]: 50% complete (3/6)
  - task/003-navigation [worker-3]: 75% complete (3/4)

> Add requirement (or press Enter to cancel): Also add a registration page with form validation

Adding requirement: Also add a registration page with form validation
Sending to orchestrator...
Resuming execution...

================================================================
```

### Step 5: Execution Resumes

```
[14:31:45] Orchestrator: Received intervention
[14:31:45] Orchestrator: New requirement: Also add a registration page
[14:31:46] Spawning planner to update plan
[14:31:48] Planner: Analyzing new requirement
[14:31:50] Planner: Creating task/007-registration-page
[14:31:52] Planner: Updated plan with new task in Wave 2
[14:31:52] Orchestrator: Resuming Wave 1
[14:31:55] Worker-1: [task-001] Implement: Add README (4/5)
[14:32:00] Worker-2: [task-002] Implement: Style hero section (4/6)
[14:32:02] Worker-3: [task-003] Test: Navigation tests (4/4)
[14:32:05] Worker-3: [task-003] COMPLETE
[14:32:08] Worker-1: [task-001] Test: Verify structure (5/5)
[14:32:10] Worker-1: [task-001] COMPLETE
[14:32:15] Worker-2: [task-002] Implement: Add responsive styles (5/6)
[14:32:20] Worker-2: [task-002] Test: Responsive tests (6/6)
[14:32:22] Worker-2: [task-002] COMPLETE
[14:32:24] Orchestrator: Wave 1 complete
[14:32:24] Orchestrator: Starting Wave 2...
```

### Step 6: Completion

```
[14:45:30] Worker-2: [task-007] COMPLETE
[14:45:32] Orchestrator: All waves complete

================================================================
SESSION COMPLETE
================================================================

Request: Create a NeurIPS 2028 conference website
Duration: 15m 17s
Waves: 3
Tasks: 10 (including added registration page)

Summary:
  ✓ Wave 1: Foundation (3 tasks)
  ✓ Wave 2: Pages (4 tasks - includes registration page from intervention)
  ✓ Wave 3: Polish (3 tasks)

Files created: 18
Commits: 32
Tests: All passing

================================================================

[n] New request  [q] Quit: n

> Enter development request: _
```

---

## Technical Design

### Architecture Overview

```
Main Thread                    Background Thread
===========                    =================

1. Show input prompt
2. Get user request
3. Start executor process      → Monitor for ESC key
4. Stream output from IPC      → If ESC: set interrupt flag
5. Check interrupt flag
6. If set: show intervention
7. Resume streaming
8. Repeat until complete
```

### Core Components

#### 1. CLI Controller (No TUI)

```python
# flow_claude/cli_controller.py

import sys
import time
import threading
from pathlib import Path

class SimpleCLI:
    """Simple CLI controller using plain input() and print()"""

    def __init__(self, model='sonnet', max_parallel=3):
        self.model = model
        self.max_parallel = max_parallel
        self.interrupt_flag = threading.Event()
        self.output_paused = threading.Event()

    def run(self):
        """Main CLI loop"""
        while True:
            # Get request from user
            request = self.get_request()
            if not request:
                break

            # Start session
            session_id, session_dir = self.start_session(request)

            # Start ESC listener in background
            stop_listener = self.start_esc_listener()

            try:
                # Stream execution output
                self.stream_execution(session_dir)

                # Show completion
                action = self.show_completion(session_dir)
                if action == 'quit':
                    break
            finally:
                stop_listener.set()

    def get_request(self):
        """Get development request from user (plain input)"""
        print("\nFlow-Claude v6.7")
        print("=" * 64)

        # Show recent sessions
        recent = self.get_recent_sessions()
        if recent:
            print("\nRecent sessions:")
            for session in recent[:3]:
                status = "✓" if session['status'] == 'complete' else "..."
                print(f"  {status} {session['id']}: {session['request'][:45]}")

        print()
        request = input("> Enter development request: ").strip()

        if not request or request.lower() == 'q':
            print("Goodbye!")
            return None

        return request

    def stream_execution(self, session_dir):
        """Stream execution output from IPC (plain print statements)"""
        from flow_claude.ipc import IPCStateReader

        state_reader = IPCStateReader(session_dir)
        message_offset = 0

        print("\nStarting session...")
        print("(Press ESC to interrupt and add requirements)\n")

        while True:
            # Check if interrupted
            if self.interrupt_flag.is_set():
                self.handle_intervention(state_reader)
                self.interrupt_flag.clear()

            # Read new messages
            messages = state_reader.get_new_messages_from(message_offset)

            for msg in messages:
                # Print message (plain text with timestamp)
                timestamp = msg['time'].strftime('%H:%M:%S')
                print(f"[{timestamp}] {msg['message']}")
                message_offset += 1

            # Check if complete
            state = state_reader.get_state()
            if state.get('status') == 'complete':
                break

            time.sleep(0.5)  # Poll every 500ms

    def handle_intervention(self, state_reader):
        """Handle ESC interruption (plain CLI prompts)"""
        # Pause output
        self.output_paused.set()

        print("\n" + "=" * 64)
        print("INTERVENTION MODE - Session Paused")
        print("=" * 64)

        # Show current state
        state = state_reader.get_state()
        print(f"\nCurrent request: {state['request']}")
        print(f"Progress: Wave {state['current_wave']}/{state['total_waves']}")

        # Show active workers
        if state.get('workers'):
            print("\nActive tasks:")
            for worker_id, worker in state['workers'].items():
                progress = worker.get('progress', {})
                pct = progress.get('percentage', 0)
                print(f"  - {worker['task_branch']} [{worker_id}]: {pct}% complete")

        print()
        requirement = input("> Add requirement (or press Enter to cancel): ").strip()

        if requirement:
            print(f"\nAdding requirement: {requirement}")
            self.send_intervention(state_reader, requirement)
            print("Resuming execution...\n")
        else:
            print("Cancelled. Resuming...\n")

        print("=" * 64 + "\n")

        # Resume output
        self.output_paused.clear()

    def send_intervention(self, state_reader, requirement):
        """Send intervention to executor via IPC"""
        from flow_claude.ipc import IPCControlWriter

        control_writer = IPCControlWriter(state_reader.session_dir)
        control_writer.send_command('interrupt', {
            'new_requirements': requirement
        })

    def show_completion(self, session_dir):
        """Show completion summary (plain text)"""
        from flow_claude.ipc import IPCStateReader

        state = IPCStateReader(session_dir).get_state()

        print("\n" + "=" * 64)
        print("SESSION COMPLETE")
        print("=" * 64)
        print(f"\nRequest: {state['request']}")
        print(f"Duration: {self.format_duration(state.get('duration', 0))}")
        print(f"Waves: {state.get('total_waves', 0)}")
        print(f"Tasks: {state.get('total_tasks', 0)}")

        print("\nSummary:")
        for wave_num, wave in state.get('waves', {}).items():
            status = "✓" if wave['status'] == 'complete' else "..."
            print(f"  {status} Wave {wave_num}: {len(wave.get('tasks', []))} tasks")

        print(f"\nFiles created: {state.get('files_created', 0)}")
        print(f"Commits: {state.get('total_commits', 0)}")
        print(f"Tests: {state.get('test_status', 'Unknown')}")

        print("\n" + "=" * 64)

        action = input("\n[n] New request  [q] Quit: ").strip().lower()
        return 'quit' if action == 'q' else 'new'
```

#### 2. ESC Detection (Platform-Specific)

```python
# flow_claude/key_detector.py

import sys
import threading

def start_esc_listener(interrupt_flag, stop_flag):
    """Start background thread to detect ESC key (platform-specific)"""

    if sys.platform == 'win32':
        listener_thread = threading.Thread(
            target=_windows_esc_listener,
            args=(interrupt_flag, stop_flag),
            daemon=True
        )
    else:
        listener_thread = threading.Thread(
            target=_unix_esc_listener,
            args=(interrupt_flag, stop_flag),
            daemon=True
        )

    listener_thread.start()
    return listener_thread


def _windows_esc_listener(interrupt_flag, stop_flag):
    """Windows ESC detection using msvcrt"""
    import msvcrt

    while not stop_flag.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\x1b':  # ESC key
                interrupt_flag.set()

        stop_flag.wait(0.1)  # Check every 100ms


def _unix_esc_listener(interrupt_flag, stop_flag):
    """Unix/Linux/Mac ESC detection using select"""
    import sys
    import select
    import termios
    import tty

    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode
        tty.setraw(fd)

        while not stop_flag.is_set():
            # Check if input available (non-blocking)
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # ESC key
                    interrupt_flag.set()
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
```

#### 3. Stream Output Handler

```python
# flow_claude/output_stream.py

import time
from datetime import datetime

class OutputStreamer:
    """Stream output from IPC to console (plain print)"""

    def __init__(self, state_reader):
        self.state_reader = state_reader
        self.message_offset = 0
        self.paused = False

    def stream_until_complete(self, interrupt_callback=None):
        """Stream messages until session complete"""

        print(f"[{self.timestamp()}] Starting session...")
        print("(Press ESC to interrupt and add requirements)\n")

        while True:
            # Check for interrupts
            if interrupt_callback and interrupt_callback():
                self.paused = True
                yield 'interrupted'
                self.paused = False

            if not self.paused:
                # Get new messages
                messages = self.get_new_messages()

                for msg in messages:
                    self.print_message(msg)

                # Check if complete
                if self.is_complete():
                    break

            time.sleep(0.5)

    def get_new_messages(self):
        """Get new messages from IPC"""
        # Read messages from JSONL log
        messages = self.state_reader.get_new_messages()
        return messages

    def print_message(self, msg):
        """Print a message (plain text)"""
        timestamp = msg.get('time', datetime.now()).strftime('%H:%M:%S')
        text = msg.get('message', '')
        level = msg.get('level', 'info')

        # Simple prefix based on level
        prefix = {
            'error': '✗',
            'warning': '!',
            'info': ' ',
            'debug': '·'
        }.get(level, ' ')

        print(f"[{timestamp}] {prefix} {text}")

    def is_complete(self):
        """Check if session is complete"""
        state = self.state_reader.get_state()
        return state.get('status') == 'complete'

    def timestamp(self):
        """Get current timestamp string"""
        return datetime.now().strftime('%H:%M:%S')
```

---

## Implementation Details

### Entry Point

```python
# flow_claude/commands/flow_cli.py

import click
from flow_claude.cli_controller import SimpleCLI

@click.command()
@click.option('--model', default='sonnet', help='Model to use')
@click.option('--max-parallel', default=3, help='Max parallel workers')
def main(model, max_parallel):
    """
    Flow-Claude - Simple Interactive CLI

    Launch autonomous development sessions with plain CLI interface.
    """
    cli = SimpleCLI(model=model, max_parallel=max_parallel)
    cli.run()

if __name__ == '__main__':
    main()
```

### Project Configuration

```toml
# pyproject.toml

[project.scripts]
flow-claude = "flow_claude.cli:main"  # Existing CLI (backwards compat)
flow = "flow_claude.commands.flow_cli:main"  # New simple CLI
```

---

## Threading Model

```
┌─────────────────────────────────────────────────────┐
│ Main Thread                                         │
│                                                     │
│  1. Get user input (blocking input())               │
│  2. Start executor subprocess                       │
│  3. Stream output loop:                            │
│     - Read new messages from IPC                   │
│     - Print to stdout                              │
│     - Check interrupt_flag                         │
│     - If interrupted: show prompt, get input       │
│     - Sleep 500ms                                  │
│  4. Show completion summary                        │
│  5. Repeat or exit                                 │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Background Thread (Key Listener)                    │
│                                                     │
│  while not stop_flag:                              │
│      if ESC key pressed:                           │
│          interrupt_flag.set()                      │
│      sleep 100ms                                   │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Executor Process (Separate)                        │
│                                                     │
│  - Runs ClaudeSDKClient                            │
│  - Writes state to IPC files                       │
│  - Checks for interrupt commands                   │
│  - Independent of UI                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Output Buffering Strategy

### Problem
When showing intervention prompt, ongoing worker output could interleave with prompt.

### Solution: Pause Detection

```python
class OutputStreamer:
    def stream_until_complete(self, check_interrupt):
        while True:
            if check_interrupt():
                # Interrupt detected
                self.flush_pending()  # Print any buffered messages
                return 'interrupted'

            messages = self.get_new_messages()
            for msg in messages:
                self.print_message(msg)

            time.sleep(0.5)

    def flush_pending(self):
        """Ensure all messages printed before intervention"""
        messages = self.get_new_messages()
        for msg in messages:
            self.print_message(msg)
        time.sleep(0.1)  # Allow final output to flush
```

---

## Error Handling

### Worker Errors

```python
def print_message(self, msg):
    """Print message with error highlighting"""
    timestamp = msg['time'].strftime('%H:%M:%S')
    level = msg.get('level', 'info')
    text = msg['message']

    if level == 'error':
        # Simple error formatting (no color codes for portability)
        print(f"[{timestamp}] ✗ ERROR: {text}")
        if 'traceback' in msg:
            print(f"         {msg['traceback']}")
    else:
        print(f"[{timestamp}]   {text}")
```

### Intervention Errors

```python
def handle_intervention(self, state_reader):
    """Handle intervention with error recovery"""
    try:
        requirement = input("> Add requirement: ").strip()

        if requirement:
            self.send_intervention(state_reader, requirement)
            print("✓ Requirement added successfully")
        else:
            print("Cancelled")
    except Exception as e:
        print(f"✗ Error during intervention: {e}")
        print("Resuming execution...")
```

---

## Cross-Platform Considerations

### Windows vs Unix Key Detection

| Feature | Windows (msvcrt) | Unix (termios) |
|---------|------------------|----------------|
| Import | `import msvcrt` | `import termios, tty, select` |
| Check key | `msvcrt.kbhit()` | `select.select([stdin], ...)` |
| Read key | `msvcrt.getch()` | `stdin.read(1)` |
| ESC value | `b'\x1b'` | `'\x1b'` |
| Terminal mode | Not needed | Must set raw mode |
| Cleanup | Not needed | Must restore settings |

### Input History

```python
# Enable readline for input history (works on all platforms)
import readline

# Configure history
history_file = Path.home() / '.flow_history'
try:
    readline.read_history_file(history_file)
except FileNotFoundError:
    pass

# Save history on exit
import atexit
atexit.register(readline.write_history_file, history_file)
```

---

## Benefits of Simple CLI Approach

### 1. Simplicity
- ✅ Plain `input()` and `print()` - everyone understands
- ✅ No TUI library dependencies (Rich, Textual, curses)
- ✅ Works in any terminal
- ✅ Easy to debug (just read stdout)

### 2. Portability
- ✅ Works over SSH
- ✅ Works in CI/CD (redirect to file)
- ✅ Works in basic terminals
- ✅ Clipboard works normally

### 3. Reliability
- ✅ No terminal rendering issues
- ✅ No escape sequence conflicts
- ✅ Works with screen readers
- ✅ Simple error recovery

### 4. Performance
- ✅ No rendering overhead
- ✅ Low memory footprint
- ✅ Fast startup
- ✅ Minimal CPU usage

---

## Comparison: TUI vs Simple CLI

| Feature | Rich TUI | Simple CLI |
|---------|----------|------------|
| Input method | Rich Prompt dialogs | Plain `input()` |
| Output | Live-updating layouts | Streaming print statements |
| Progress | Progress bars `████` | Text updates "50% complete" |
| ESC detection | TUI keyboard handler | Platform-specific thread |
| Dependencies | Rich library (~500KB) | Standard library only |
| Terminal req | ANSI color support | Any terminal |
| SSH friendly | Sometimes breaks | Always works |
| CI/CD friendly | No (needs PTY) | Yes (stdout redirect) |
| Complexity | High | Low |

---

## Testing Strategy

### Manual Testing

```bash
# Basic flow
$ flow
> Enter request: Create homepage
[Watch output stream...]
[Press ESC]
> Add requirement: Also add footer
[Watch continued output...]
[Session completes]
[n] New request: [Enter another request]

# Test ESC detection
$ flow
> Enter request: Test ESC
[Press ESC immediately]
> Add requirement: Test requirement
[Verify pauses and resumes correctly]

# Test on different platforms
$ # On Windows
$ flow
$ # On Linux
$ flow
$ # On Mac
$ flow
```

### Automated Testing

```python
# tests/test_cli_controller.py

def test_simple_flow():
    """Test basic CLI flow with mocked input"""
    inputs = iter(["Create test", ""])  # Request, then quit

    def mock_input(prompt):
        return next(inputs)

    with patch('builtins.input', mock_input):
        cli = SimpleCLI()
        # Test runs without errors

def test_intervention():
    """Test ESC intervention flow"""
    # Mock interrupt flag being set
    # Verify intervention prompt shows
    # Verify execution resumes

def test_cross_platform_keys():
    """Test ESC detection on both platforms"""
    # Test Windows path
    # Test Unix path
```

---

## Summary

This simple CLI design provides:

✅ **No TUI complexity** - Just `input()` and `print()`
✅ **Platform-specific ESC** detection - Works on Windows/Linux/Mac
✅ **Streaming output** - Like `tail -f`, not dashboard
✅ **Simple intervention** - Pause, prompt, resume
✅ **Session continuity** - Chain multiple requests
✅ **Works everywhere** - SSH, CI/CD, basic terminals

**Implementation**: ~300 lines of simple Python code vs ~1000+ lines for Rich TUI.

**User Experience**: Familiar CLI interaction, like Git or npm, with added ESC interrupt capability.
