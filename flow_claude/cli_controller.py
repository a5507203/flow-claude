"""
Simple CLI Controller for Flow-Claude Interactive Mode

Provides a plain text interface using input() and print() for:
- Getting development requests from users
- Streaming execution output from IPC
- Handling ESC interruptions for adding requirements
- Showing session completion status
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from flow_claude.ipc import StateReader
from flow_claude.key_detector import start_esc_listener


class SimpleCLI:
    """Simple CLI controller for Flow-Claude interactive sessions"""

    def __init__(self, model: str = 'sonnet', max_parallel: int = 3, verbose: bool = False, debug: bool = False):
        self.model = model
        self.max_parallel = max_parallel
        self.verbose = verbose
        self.debug = debug

        # Threading controls
        self.interrupt_flag = threading.Event()
        self.stop_flag = threading.Event()
        self.output_paused = threading.Event()

        # Session state
        self.current_session_dir: Optional[Path] = None
        self.executor_process = None

    def run(self):
        """Main CLI loop - get request and start session"""
        try:
            # Start ESC key listener in background
            listener_thread = start_esc_listener(self.interrupt_flag, self.stop_flag)

            # Get development request from user
            request = self.get_request()
            if not request:
                print("\nNo request provided. Exiting.")
                return

            # Start executor process
            self.start_executor(request)

            # Stream execution output
            self.stream_execution()

            # Show completion status
            self.show_completion()

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C)")
            self.cleanup()
        except Exception as e:
            print(f"\n\nError: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            self.cleanup()
        finally:
            # Stop ESC listener
            self.stop_flag.set()
            if listener_thread:
                listener_thread.join(timeout=1.0)

    def get_request(self) -> str:
        """Get development request from user (plain input prompt)"""
        # Clear screen for cleaner look
        print("\n" * 2)

        # Header with box drawing
        print("┌" + "─" * 78 + "┐")
        print("│" + " " * 78 + "│")
        print("│" + "  Flow-Claude v6.7".ljust(78) + "│")
        print("│" + "  Git-First Autonomous Development System".ljust(78) + "│")
        print("│" + " " * 78 + "│")
        print("└" + "─" * 78 + "┘")
        print()

        # Instructions with better formatting
        print("  Enter your development request below:")
        print("  " + "·" * 76)
        print()
        print("  Commands: \\parallel, \\model, \\verbose, \\debug, \\init, \\help")
        print("  Tip: Press ESC anytime during execution to add requirements")
        print()

        while True:
            # Prompt with nice styling
            request = input("  > ").strip()

            # Handle slash commands
            if request.startswith('\\'):
                if self.handle_slash_command(request):
                    continue  # Command handled, prompt again
                else:
                    return ""  # Exit requested

            # Regular request
            if request:
                return request

            print("  Please enter a request or use \\help for available commands")

    def handle_slash_command(self, command: str) -> bool:
        """
        Handle slash commands interactively.
        Returns True to continue prompting, False to exit.
        """
        cmd = command[1:].lower()  # Remove leading backslash

        if cmd == 'parallel':
            print()
            current = self.max_parallel
            new_value = input(f"  Max parallel workers (current: {current}): ").strip()
            if new_value.isdigit():
                self.max_parallel = int(new_value)
                print(f"  → Set max parallel workers to {self.max_parallel}")
            else:
                print("  → Invalid number, keeping current value")
            print()
            return True

        elif cmd == 'model':
            print()
            current = self.model
            print(f"  Current model: {current}")
            print("  Available: sonnet, opus, haiku")
            new_value = input("  Select model: ").strip().lower()
            if new_value in ['sonnet', 'opus', 'haiku']:
                self.model = new_value
                print(f"  → Set model to {self.model}")
            else:
                print("  → Invalid model, keeping current value")
            print()
            return True

        elif cmd == 'verbose':
            self.verbose = not self.verbose
            status = "enabled" if self.verbose else "disabled"
            print(f"  → Verbose mode {status}")
            print()
            return True

        elif cmd == 'debug':
            self.debug = not self.debug
            status = "enabled" if self.debug else "disabled"
            print(f"  → Debug mode {status}")
            print()
            return True

        elif cmd == 'init':
            print()
            print("  Generating CLAUDE.md...")
            self.generate_claude_md()
            print("  → CLAUDE.md created successfully")
            print()
            return True

        elif cmd == 'help':
            print()
            print("  Available Commands:")
            print("  " + "─" * 76)
            print("  \\parallel    - Set maximum number of parallel workers")
            print("  \\model       - Select Claude model (sonnet/opus/haiku)")
            print("  \\verbose     - Toggle verbose output")
            print("  \\debug       - Toggle debug mode")
            print("  \\init        - Generate CLAUDE.md template")
            print("  \\help        - Show this help message")
            print("  \\exit        - Exit Flow-Claude")
            print("  " + "─" * 76)
            print()
            return True

        elif cmd == 'exit':
            print()
            print("  Exiting Flow-Claude...")
            return False

        else:
            print(f"  Unknown command: {command}")
            print("  Use \\help to see available commands")
            print()
            return True

    def generate_claude_md(self):
        """Generate CLAUDE.md template in current directory"""
        template = """# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

[Describe your project here]

## Architecture

[Describe the architecture and key components]

## Development Workflow

[Describe how to develop, test, and deploy]

## Key Files

[List important files and their purposes]

## Coding Standards

[Describe coding standards and conventions]

## Common Tasks

### Running the project
```bash
# Add commands here
```

### Running tests
```bash
# Add commands here
```

## Important Notes

[Any important notes or gotchas for Claude to be aware of]
"""

        with open('CLAUDE.md', 'w') as f:
            f.write(template)

    def start_executor(self, request: str):
        """Start the executor process with the development request"""
        import subprocess
        from flow_claude.ipc import get_session_dir

        # Create session directory
        session_id = datetime.now().strftime("session-%Y%m%d-%H%M%S")
        self.current_session_dir = get_session_dir(session_id)
        self.current_session_dir.mkdir(parents=True, exist_ok=True)

        # Build executor command
        cmd = [
            sys.executable, "-m", "flow_claude.cli", "develop",
            request,
            "--model", self.model,
            "--max-parallel", str(self.max_parallel),
            "--session-id", session_id,
        ]

        if self.verbose:
            cmd.append("--verbose")
        if self.debug:
            cmd.append("--debug")

        # Start executor in background
        print()
        print("  " + "─" * 76)
        print(f"  Starting session: {session_id}")
        print(f"  Model: {self.model} | Workers: {self.max_parallel}")
        print("  Press ESC anytime to interrupt and add requirements")
        print("  " + "─" * 76)
        print()

        self.executor_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )

    def stream_execution(self):
        """Stream execution output from IPC (plain print statements)"""
        if not self.current_session_dir:
            print("Error: No active session")
            return

        state_reader = StateReader(self.current_session_dir)
        last_position = 0

        while True:
            # Check if interrupted by ESC
            if self.interrupt_flag.is_set():
                self.output_paused.set()
                self.handle_intervention(state_reader)
                self.interrupt_flag.clear()
                self.output_paused.clear()

            # Read new messages from IPC
            messages = state_reader.get_new_messages(since_position=last_position)

            for msg in messages:
                timestamp = msg.get('time', datetime.now()).strftime('%H:%M:%S')
                message = msg.get('message', '')
                msg_type = msg.get('type', 'info')

                # Format message based on type
                if msg_type == 'error':
                    prefix = "[ERROR]"
                elif msg_type == 'warning':
                    prefix = "[WARN] "
                elif msg_type == 'agent':
                    prefix = "[AGENT]"
                elif msg_type == 'success':
                    prefix = "[DONE] "
                else:
                    prefix = "[INFO] "

                print(f"  [{timestamp}] {prefix} {message}")
                last_position = msg.get('position', last_position + 1)

            # Check if session complete
            state = state_reader.get_state()
            if state.get('status') in ['completed', 'failed', 'interrupted']:
                break

            # Check if executor process died
            if self.executor_process and self.executor_process.poll() is not None:
                break

            # Small sleep to avoid busy loop
            time.sleep(0.5)

    def handle_intervention(self, state_reader: StateReader):
        """Handle ESC interruption - prompt for additional requirement"""
        print()
        print("  " + "═" * 76)
        print("  INTERVENTION MODE")
        print("  " + "═" * 76)
        print()
        print("  Session paused. You can add additional requirements.")
        print("  (Press Enter with empty input to resume)")
        print()

        requirement = input("  > Additional requirement: ").strip()

        if requirement:
            # Send intervention command via IPC
            from flow_claude.ipc import StateWriter
            state_writer = StateWriter(self.current_session_dir)
            state_writer.write_control_command('intervention', {
                'requirement': requirement,
                'timestamp': datetime.now().isoformat()
            })

            print()
            print("  Requirement added. Resuming execution...")
        else:
            print()
            print("  No requirement added. Resuming execution...")

        print("  " + "═" * 76)
        print()

    def show_completion(self):
        """Show session completion status and summary"""
        if not self.current_session_dir:
            return

        state_reader = StateReader(self.current_session_dir)
        state = state_reader.get_state()

        status = state.get('status', 'unknown')

        print()
        print("  " + "═" * 76)
        print("  SESSION COMPLETE")
        print("  " + "═" * 76)
        print()

        if status == 'completed':
            print("  Status: COMPLETED")
        elif status == 'failed':
            print("  Status: FAILED")
        elif status == 'interrupted':
            print("  Status: INTERRUPTED")
        else:
            print(f"  Status: {status.upper()}")

        # Show summary stats
        total_tasks = state.get('total_tasks', 0)
        completed_tasks = state.get('completed_tasks', 0)
        failed_tasks = state.get('failed_tasks', 0)

        print()
        print(f"  Tasks completed: {completed_tasks}/{total_tasks}")
        if failed_tasks > 0:
            print(f"  Tasks failed: {failed_tasks}")

        # Show plan branch
        plan_branch = state.get('plan_branch', 'N/A')
        print()
        print(f"  Plan branch: {plan_branch}")

        # Show any error message
        error = state.get('error')
        if error:
            print()
            print(f"  Error: {error}")

        print()
        print("  " + "═" * 76)
        print()

    def cleanup(self):
        """Clean up resources and terminate executor process"""
        if self.executor_process:
            try:
                self.executor_process.terminate()
                self.executor_process.wait(timeout=5.0)
            except:
                try:
                    self.executor_process.kill()
                except:
                    pass
