"""
Simple CLI Controller for Flow-Claude Interactive Mode

Provides a plain text interface using async event loops for:
- Getting development requests from users
- Real-time streaming of execution output via async queues
- Handling 'q' for graceful shutdown
- Handling ESC interruptions for adding requirements
- Showing session completion status
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

from flow_claude.logging_config import get_logger, cleanup_old_logs


class SimpleCLI:
    """Simple CLI controller for Flow-Claude interactive sessions with async queues"""

    def __init__(self, model: str = 'sonnet', max_parallel: int = 3, verbose: bool = False, debug: bool = False):
        self.model = model
        self.max_parallel = max_parallel
        self.verbose = verbose
        self.debug = debug

        # Async queues for communication
        self.message_queue = None
        self.control_queue = None

        # Session state
        self.orchestrator_task = None
        self.shutdown_requested = False

        # Logger (will be initialized in run())
        self.logger = None

    async def run(self):
        """Main async CLI loop - get request and start session"""
        # Initialize logger
        session_id = datetime.now().strftime("session-%Y%m%d-%H%M%S")
        self.logger = get_logger(session_id)

        # Cleanup old logs
        cleanup_old_logs()

        try:
            self.logger.info(f"Starting Flow-Claude CLI (model={self.model}, max_parallel={self.max_parallel})")

            # Check if we should prompt for CLAUDE.md initialization
            self.check_and_prompt_init()

            # Get development request from user (synchronous)
            request = self.get_request()
            if not request:
                print("\nNo request provided. Exiting.")
                self.logger.info("No request provided, exiting")
                return

            self.logger.info(f"User request: {request}")

            # Print log file location
            print(f"  Log file: {self.logger.log_file}")
            print()

            # Create async queues
            self.message_queue = asyncio.Queue()
            self.control_queue = asyncio.Queue()

            # Start orchestrator in background
            self.logger.info("Starting orchestrator task")
            self.orchestrator_task = asyncio.create_task(
                self.run_orchestrator(request)
            )

            # Run UI tasks concurrently
            self.logger.info("Starting concurrent tasks (render, input, orchestrator)")
            await asyncio.gather(
                self.render_loop(),      # Display messages from orchestrator
                self.input_loop(),       # Handle keyboard input (q/ESC)
                self.orchestrator_task,  # Orchestrator execution
                return_exceptions=True
            )

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C)")
            self.logger.warning("Session interrupted by Ctrl+C")
            await self.cleanup()
        except Exception as e:
            print(f"\n\nError: {e}")
            self.logger.exception(f"Fatal error: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            await self.cleanup()
        finally:
            if self.logger:
                self.logger.close()

    async def run_orchestrator(self, request: str):
        """Run orchestrator in background with async queue communication"""
        from flow_claude.orchestrator import OrchestratorSession

        session = OrchestratorSession(
            request=request,
            message_queue=self.message_queue,
            control_queue=self.control_queue,
            model=self.model,
            max_parallel=self.max_parallel,
            verbose=self.verbose,
            debug=self.debug
        )

        try:
            await session.run()
        except asyncio.CancelledError:
            # Orchestrator was cancelled, cleanup already handled
            pass
        except Exception as e:
            await self.message_queue.put({
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "data": {"message": f"Orchestrator error: {str(e)}"}
            })

    async def render_loop(self):
        """Display messages from orchestrator"""
        while not self.shutdown_requested:
            try:
                # Wait for message from orchestrator
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=0.5
                )

                # Render message
                self.render_message(message)

                # Check if session complete
                if message.get("type") == "complete":
                    break

            except asyncio.TimeoutError:
                # No message, continue
                continue
            except asyncio.CancelledError:
                break

    async def input_loop(self):
        """Handle keyboard input - q for quit, ESC for intervention"""
        loop = asyncio.get_event_loop()
        self.logger.debug("Input loop started")

        while not self.shutdown_requested:
            try:
                # Read key in non-blocking way
                key = await loop.run_in_executor(None, self.read_key_with_timeout)

                if key == 'q':
                    self.logger.info("User pressed 'q' - initiating shutdown")
                    # Send shutdown signal
                    await self.control_queue.put({
                        "type": "shutdown",
                        "data": {}
                    })

                    print("\n\n  Shutting down... Please wait.")
                    self.shutdown_requested = True

                    # Cancel orchestrator
                    if self.orchestrator_task:
                        self.orchestrator_task.cancel()

                    break

                elif key == '\x1b':  # ESC
                    self.logger.info("User pressed ESC - entering intervention mode")
                    # Handle intervention
                    await self.handle_intervention()

            except asyncio.CancelledError:
                self.logger.debug("Input loop cancelled")
                break

    def read_key_with_timeout(self) -> Optional[str]:
        """Read single key with timeout (blocking with short timeout)"""
        import sys

        if sys.platform == 'win32':
            import msvcrt
            import time

            # Poll for 0.5 seconds
            start = time.time()
            while time.time() - start < 0.5:
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8', errors='ignore')
                time.sleep(0.05)
            return None
        else:
            import select
            import tty
            import termios

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)

                # Wait for input with 0.5 second timeout
                rlist, _, _ = select.select([sys.stdin], [], [], 0.5)
                if rlist:
                    return sys.stdin.read(1)
                return None

            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    async def handle_intervention(self):
        """Handle ESC interruption - prompt for additional requirement"""
        self.logger.info("Intervention: Sending pause signal")
        # First, pause the backend process
        await self.control_queue.put({
            "type": "pause",
            "data": {}
        })

        # Wait a moment for the pause to take effect
        await asyncio.sleep(0.5)

        print()
        print("  " + "=" * 76)
        print("  INTERVENTION MODE")
        print("  " + "=" * 76)
        print()
        print("  Session paused. You can add additional requirements.")
        print("  (Press Enter with empty input to resume)")
        print()

        # Get requirement synchronously (blocking is OK here)
        loop = asyncio.get_event_loop()
        requirement = await loop.run_in_executor(
            None,
            lambda: input("  > Additional requirement: ").strip()
        )

        if requirement:
            self.logger.info(f"Intervention: User added requirement: {requirement}")
            # Send intervention to orchestrator
            await self.control_queue.put({
                "type": "intervention",
                "data": {
                    "requirement": requirement,
                    "timestamp": datetime.now().isoformat()
                }
            })

            print()
            print("  Requirement added. Resuming execution...")
        else:
            self.logger.info("Intervention: No requirement added")
            print()
            print("  No requirement added. Resuming execution...")

        print("  " + "=" * 76)
        print()

        self.logger.info("Intervention: Sending resume signal")
        # Resume the backend process
        await self.control_queue.put({
            "type": "resume",
            "data": {}
        })

    def render_message(self, message: dict):
        """Render message to console"""
        msg_type = message.get("type")
        data = message.get("data", {})
        timestamp = message.get("timestamp", datetime.now().isoformat())[:19]

        # Log all orchestrator messages
        self.logger.log_orchestrator_message(msg_type, data)

        if msg_type == "status":
            print(f"  [{timestamp}] [INFO]  {data.get('message', '')}")

        elif msg_type == "agent_start":
            agent = data.get('agent', 'unknown')
            msg = data.get('message', '')
            print(f"  [{timestamp}] [AGENT] {agent}: {msg}")

        elif msg_type == "agent_output":
            print(f"  [{timestamp}] [OUT]   {data.get('message', '')}")

        elif msg_type == "task_progress":
            print(f"  [{timestamp}] [PROG] {data.get('message', '')}")

        elif msg_type == "warning":
            print(f"  [{timestamp}] [WARN]  {data.get('message', '')}")

        elif msg_type == "error":
            print(f"  [{timestamp}] [ERROR] {data.get('message', '')}")

        elif msg_type == "complete":
            self.show_completion(data)

    def show_completion(self, data: dict):
        """Show session completion status"""
        status = data.get('status', 'unknown')

        print()
        print("  " + "=" * 76)
        print("  SESSION COMPLETE")
        print("  " + "=" * 76)
        print()

        if status == 'success':
            print("  Status: COMPLETED")
        elif status == 'failed':
            print("  Status: FAILED")
        elif status == 'interrupted':
            print("  Status: INTERRUPTED")
        else:
            print(f"  Status: {status.upper()}")

        print()
        print("  " + "=" * 76)
        print()

    async def cleanup(self):
        """Clean up resources"""
        if self.orchestrator_task and not self.orchestrator_task.done():
            self.orchestrator_task.cancel()
            try:
                await self.orchestrator_task
            except asyncio.CancelledError:
                pass

    def check_and_prompt_init(self):
        """Check if directory needs CLAUDE.md initialization and prompt user"""
        from pathlib import Path
        import subprocess

        cwd = Path.cwd()
        claude_md = cwd / "CLAUDE.md"

        # Check if CLAUDE.md already exists
        if claude_md.exists():
            return

        # Check if directory is empty (only check for non-hidden files)
        files = [f for f in cwd.iterdir() if not f.name.startswith('.')]
        if not files:
            # Empty directory, no need to prompt
            return

        # Directory is not empty and no CLAUDE.md - prompt user
        print()
        print("  " + "-" * 76)
        print("  This directory doesn't have a CLAUDE.md file.")
        print("  CLAUDE.md helps Claude Code understand your project better.")
        print("  " + "-" * 76)
        print()

        while True:
            response = input("  Would you like to initialize CLAUDE.md now? (y/n): ").strip().lower()

            if response in ['y', 'yes']:
                self.logger.info("User chose to initialize CLAUDE.md with Claude Code")
                print()
                print("  Initializing CLAUDE.md with Claude Code...")
                print()

                # Try to run claude code to create CLAUDE.md
                try:
                    # Check if claude command exists
                    # On Windows, need shell=True to find .cmd files
                    result = subprocess.run(
                        'claude --version',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        # Claude Code is available, create CLAUDE.md automatically
                        print("  Creating CLAUDE.md with Claude Code...")
                        print()

                        # Use echo to pipe prompt to claude code --print with --dangerously-skip-permissions
                        # This allows non-interactive file creation
                        prompt = "Please create a CLAUDE.md file for this project with proper documentation structure. Write the file now."
                        init_result = subprocess.run(
                            f'echo {prompt} | claude code --print --dangerously-skip-permissions',
                            shell=True,
                            cwd=str(cwd),
                            capture_output=True,
                            text=True,
                            timeout=60
                        )

                        # Check if CLAUDE.md was created
                        if claude_md.exists():
                            print("  ✓ CLAUDE.md created successfully!")
                            print()
                            self.logger.info("CLAUDE.md initialized successfully with Claude Code")
                        else:
                            print("  ✗ CLAUDE.md creation failed.")
                            print("  You can run 'claude code' and use \\init manually.")
                            print()
                            self.logger.warning("CLAUDE.md file not found after initialization")
                    else:
                        raise FileNotFoundError()

                except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
                    # Claude Code not available
                    print("  ✗ Claude Code CLI not found.")
                    print()
                    print("  To install Claude Code, visit:")
                    print("  https://docs.claude.com/en/docs/claude-code")
                    print()
                    print("  Or run 'claude code' and use \\init slash command manually.")
                    print()
                    self.logger.warning(f"Claude Code CLI not available: {e}")

                break

            elif response in ['n', 'no']:
                self.logger.info("User declined to create CLAUDE.md")
                print()
                print("  Skipping CLAUDE.md initialization.")
                print("  Note: CLAUDE.md helps Claude Code understand your project better.")
                print()
                break
            else:
                print("  Please enter 'y' or 'n'")

    def get_request(self) -> str:
        """Get development request from user (plain input prompt)"""
        import sys

        # Clear screen for cleaner look
        print("\n" * 2)

        # Header with box drawing - use ASCII for Windows compatibility
        if sys.platform == 'win32':
            print("+" + "-" * 78 + "+")
            print("|" + " " * 78 + "|")
            print("|" + "  Flow-Claude v6.7".ljust(78) + "|")
            print("|" + "  Git-First Autonomous Development System".ljust(78) + "|")
            print("|" + " " * 78 + "|")
            print("+" + "-" * 78 + "+")
        else:
            print("┌" + "─" * 78 + "┐")
            print("│" + " " * 78 + "│")
            print("│" + "  Flow-Claude v6.7".ljust(78) + "│")
            print("│" + "  Git-First Autonomous Development System".ljust(78) + "│")
            print("│" + " " * 78 + "│")
            print("└" + "─" * 78 + "┘")
        print()

        # Instructions with better formatting
        print("  Enter your development request below:")
        print("  " + "-" * 76)
        print()
        print("  Commands: \\parallel, \\model, \\verbose, \\debug, \\init, \\help")
        print("  Tip: Press 'q' during execution to stop, ESC to add requirements")
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
            print("  " + "-" * 76)
            print("  \\parallel    - Set maximum number of parallel workers")
            print("  \\model       - Select Claude model (sonnet/opus/haiku)")
            print("  \\verbose     - Toggle verbose output")
            print("  \\debug       - Toggle debug mode")
            print("  \\init        - Generate CLAUDE.md template")
            print("  \\help        - Show this help message")
            print("  \\exit        - Exit Flow-Claude")
            print("  " + "-" * 76)
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
