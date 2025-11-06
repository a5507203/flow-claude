# Interactive CLI Design - Final Architecture

## Overview

This document describes the final architecture for Flow-Claude's interactive CLI, enabling real-time communication between the user interface and the orchestrator agent, inspired by Claude Code's approach.

## Design Goals

1. **Real-time bidirectional communication** between CLI and orchestrator
2. **Graceful shutdown** - pressing 'q' stops all background tasks immediately
3. **Live status updates** - see what agents are doing in real-time
4. **ESC intervention** - pause execution and add requirements mid-stream
5. **Minimal latency** - updates appear instantly
6. **Clean resource cleanup** - no orphaned processes

## Architecture

### Component Overview

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │         │                  │         │                 │
│  Interactive    │◄────────┤  Event Queue     │◄────────┤  Orchestrator   │
│  CLI (UI)       │         │  (Async Queue)   │         │  Agent          │
│                 │────────►│                  │────────►│                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
       │                            │                            │
       │                            │                            │
       ├─ Key Listener              ├─ Message Queue            ├─ Planner Agent
       ├─ Display Renderer          ├─ Control Queue            ├─ Worker Agents
       └─ Shutdown Handler          └─ Status Updates           └─ Git Operations
```

### Communication Pattern: Async Event Queue (Best Practice)

**Why Async Queue (like Claude Code)?**
- Non-blocking: UI stays responsive while orchestrator runs
- Reliable: Messages never lost, delivered in order
- Decoupled: Components don't depend on each other directly
- Thread-safe: Built-in synchronization
- Graceful degradation: Queue can buffer during slowdowns

**Alternative approaches (not recommended):**
- ❌ IPC files: Too slow, race conditions, file system overhead
- ❌ Sockets: Overkill for single-machine, connection management complexity
- ❌ Shared memory: Complex synchronization, platform-specific
- ✅ **Python async queues: Fast, reliable, built-in to asyncio**

## Implementation Design

### 1. Message Protocol

```python
# Message types from Orchestrator → CLI
class MessageType(Enum):
    STATUS = "status"           # General status update
    AGENT_START = "agent_start" # Agent begins work
    AGENT_OUTPUT = "agent_output" # Agent produces output
    AGENT_COMPLETE = "agent_complete" # Agent finishes
    TASK_PROGRESS = "task_progress" # Task completion %
    ERROR = "error"             # Error occurred
    WARNING = "warning"         # Warning message
    COMPLETE = "complete"       # Session complete

# Message format
{
    "type": MessageType,
    "timestamp": "2025-01-06T14:30:00",
    "data": {
        # Type-specific data
    }
}

# Control messages from CLI → Orchestrator
class ControlType(Enum):
    INTERVENTION = "intervention"  # User adds requirement
    PAUSE = "pause"               # Pause execution
    RESUME = "resume"             # Resume execution
    SHUTDOWN = "shutdown"         # Stop all tasks

{
    "type": ControlType,
    "data": {
        # Type-specific data
    }
}
```

### 2. Orchestrator Integration

**Modify `flow_claude/cli.py` to support event queue:**

```python
import asyncio
from typing import Optional
from enum import Enum

class OrchestratorSession:
    """Main orchestrator with event queue communication"""

    def __init__(self,
                 request: str,
                 message_queue: asyncio.Queue,
                 control_queue: asyncio.Queue):
        self.request = request
        self.message_queue = message_queue  # Send messages to CLI
        self.control_queue = control_queue  # Receive from CLI
        self.shutdown_event = asyncio.Event()

    async def run(self):
        """Main orchestrator loop"""
        try:
            # Send initial status
            await self.send_message("status", {"message": "Initializing..."})

            # Start planner
            await self.send_message("agent_start", {
                "agent": "planner",
                "message": "Analyzing request and creating plan..."
            })

            # Run planning phase
            plan = await self.run_planner()

            # Execute waves
            for wave_num, tasks in enumerate(plan.waves):
                # Check for control messages
                if self.shutdown_event.is_set():
                    await self.send_message("status", {"message": "Shutdown requested"})
                    break

                # Check for interventions
                await self.check_control_queue()

                # Execute wave
                await self.execute_wave(wave_num, tasks)

            # Complete
            await self.send_message("complete", {"status": "success"})

        except Exception as e:
            await self.send_message("error", {"message": str(e)})

    async def send_message(self, msg_type: str, data: dict):
        """Send message to CLI"""
        message = {
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        await self.message_queue.put(message)

    async def check_control_queue(self):
        """Check for control messages from CLI"""
        try:
            # Non-blocking check
            control = self.control_queue.get_nowait()

            if control["type"] == "shutdown":
                self.shutdown_event.set()
                await self.cleanup()

            elif control["type"] == "intervention":
                requirement = control["data"]["requirement"]
                await self.handle_intervention(requirement)

        except asyncio.QueueEmpty:
            pass  # No messages

    async def cleanup(self):
        """Clean up all resources"""
        # Kill all worker processes
        for worker in self.workers:
            worker.terminate()
            await worker.wait()

        # Clean up git worktrees
        await self.cleanup_worktrees()

        # Send final status
        await self.send_message("status", {"message": "Cleanup complete"})
```

### 3. Interactive CLI Implementation

**Modify `flow_claude/cli_controller.py`:**

```python
import asyncio
from asyncio import Queue

class SimpleCLI:
    """Interactive CLI with async event queue"""

    def __init__(self, model='sonnet', max_parallel=3):
        self.model = model
        self.max_parallel = max_parallel

        # Async queues
        self.message_queue = Queue()  # Orchestrator → CLI
        self.control_queue = Queue()  # CLI → Orchestrator

        # State
        self.running = False
        self.orchestrator_task = None

    async def run(self):
        """Main CLI loop"""
        # Get request
        request = self.get_request()
        if not request:
            return

        # Start orchestrator in background
        self.orchestrator_task = asyncio.create_task(
            self.run_orchestrator(request)
        )

        # Start UI tasks
        await asyncio.gather(
            self.render_loop(),      # Display messages
            self.input_loop(),       # Handle keyboard input
            self.orchestrator_task,  # Orchestrator execution
            return_exceptions=True
        )

    async def run_orchestrator(self, request: str):
        """Run orchestrator in background"""
        from flow_claude.orchestrator import OrchestratorSession

        session = OrchestratorSession(
            request=request,
            message_queue=self.message_queue,
            control_queue=self.control_queue
        )

        await session.run()

    async def render_loop(self):
        """Display messages from orchestrator"""
        while True:
            try:
                # Wait for message (blocks until available)
                message = await self.message_queue.get()

                # Render based on type
                self.render_message(message)

                # Check if complete
                if message["type"] == "complete":
                    break

            except asyncio.CancelledError:
                break

    async def input_loop(self):
        """Handle keyboard input"""
        loop = asyncio.get_event_loop()

        while True:
            # Read key in non-blocking way
            key = await loop.run_in_executor(None, self.read_key)

            if key == 'q':
                # Send shutdown signal
                await self.control_queue.put({
                    "type": "shutdown",
                    "data": {}
                })

                # Cancel orchestrator
                if self.orchestrator_task:
                    self.orchestrator_task.cancel()

                print("\n\n  Shutting down... Please wait.")
                break

            elif key == '\x1b':  # ESC
                # Pause and get requirement
                requirement = input("\n  > Additional requirement: ").strip()

                if requirement:
                    await self.control_queue.put({
                        "type": "intervention",
                        "data": {"requirement": requirement}
                    })

    def read_key(self) -> str:
        """Read single key (blocking)"""
        import sys
        if sys.platform == 'win32':
            import msvcrt
            return msvcrt.getch().decode('utf-8', errors='ignore')
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def render_message(self, message: dict):
        """Render message to console"""
        msg_type = message["type"]
        data = message["data"]
        timestamp = message["timestamp"][:19]  # Strip milliseconds

        if msg_type == "status":
            print(f"  [{timestamp}] [INFO]  {data['message']}")

        elif msg_type == "agent_start":
            print(f"  [{timestamp}] [AGENT] {data['agent']}: {data['message']}")

        elif msg_type == "agent_output":
            print(f"  [{timestamp}] [OUT]   {data['message']}")

        elif msg_type == "error":
            print(f"  [{timestamp}] [ERROR] {data['message']}")

        elif msg_type == "complete":
            self.show_completion(data)
```

## Key Features

### 1. Graceful Shutdown (Press 'q')

```python
# When user presses 'q':
1. Send shutdown signal to orchestrator via control_queue
2. Orchestrator checks shutdown_event in main loop
3. Orchestrator:
   - Terminates all worker processes
   - Cleans up git worktrees
   - Closes any open files/connections
   - Sends final status message
4. CLI waits for orchestrator to finish cleanup
5. Exit cleanly
```

### 2. Real-time Status Updates

```python
# Orchestrator sends messages at key points:
- "Analyzing codebase..."
- "Creating execution plan..."
- "Starting worker 1 on task/001-user-model..."
- "Worker 1: Creating User model..."
- "Worker 1: Running tests..."
- "Worker 1: Task complete"
- "Merging completed tasks..."
- "Wave 1 complete (3/8 tasks done)"
```

### 3. ESC Intervention

```python
# User presses ESC:
1. CLI pauses message display
2. Shows intervention prompt
3. User enters requirement
4. CLI sends intervention message to orchestrator
5. Orchestrator:
   - Updates plan with new requirement
   - Notifies planner to replan
   - Continues execution
6. CLI resumes message display
```

## File Structure

```
flow_claude/
├── cli_controller.py          # Interactive CLI (modified)
├── orchestrator.py            # Orchestrator with queue support (new)
├── cli.py                     # Entry point (modified to use orchestrator)
├── agents.py                  # Agent definitions
├── git_tools.py               # Git operations
└── commands/
    └── flow_cli.py            # Flow command entry
```

## Benefits of This Approach

1. **No IPC files**: Faster, no file system overhead
2. **Thread-safe**: Async queues handle synchronization
3. **Responsive UI**: Never blocks on I/O
4. **Clean shutdown**: All resources properly cleaned up
5. **Extensible**: Easy to add new message types
6. **Testable**: Can inject mock queues for testing

## Migration Path

### Phase 1: Add Queue Support to Orchestrator
- Modify `cli.py` to create `OrchestratorSession` class
- Add `message_queue` and `control_queue` parameters
- Add `send_message()` calls at key points
- Add `check_control_queue()` in main loop

### Phase 2: Update CLI Controller
- Replace subprocess execution with `asyncio.create_task()`
- Add `render_loop()` and `input_loop()`
- Remove IPC file reading code
- Add keyboard handling

### Phase 3: Add Shutdown Handling
- Add `shutdown_event` to orchestrator
- Check event in main loop
- Add `cleanup()` method
- Test graceful shutdown

### Phase 4: Add Intervention Support
- Handle intervention messages in orchestrator
- Update planner to incorporate new requirements
- Test mid-execution replanning

## Testing Strategy

```python
# Test with mock queues
async def test_shutdown():
    message_queue = asyncio.Queue()
    control_queue = asyncio.Queue()

    # Start orchestrator
    session = OrchestratorSession("test request", message_queue, control_queue)
    task = asyncio.create_task(session.run())

    # Wait a bit
    await asyncio.sleep(1)

    # Send shutdown
    await control_queue.put({"type": "shutdown"})

    # Wait for cleanup
    await task

    # Verify resources cleaned up
    assert len(session.workers) == 0
    assert session.shutdown_event.is_set()
```

## Comparison with Claude Code

| Feature | Claude Code | Flow-Claude (This Design) |
|---------|-------------|---------------------------|
| Communication | Async event queue | Async event queue ✅ |
| Shutdown | Graceful with cleanup | Graceful with cleanup ✅ |
| Real-time updates | Yes | Yes ✅ |
| Intervention | Yes (via UI) | Yes (ESC key) ✅ |
| Process management | Robust | Robust ✅ |

## Next Steps

1. Implement `OrchestratorSession` class in new `orchestrator.py`
2. Modify existing `cli.py` to use `OrchestratorSession`
3. Update `cli_controller.py` to use async queues
4. Add shutdown handling and testing
5. Add intervention support
6. Test thoroughly with real development tasks

## Conclusion

This design provides a robust, responsive, and maintainable interactive CLI for Flow-Claude, following industry best practices and inspired by Claude Code's architecture. The async queue approach provides the best balance of simplicity, performance, and reliability.
