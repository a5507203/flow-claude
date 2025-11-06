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

        # Control queue for interventions (ESC, shutdown)
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

            # Ensure prompt files exist in working directory
            self.ensure_prompt_files()

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

            # Create control queue for interventions
            self.control_queue = asyncio.Queue()

            # Start orchestrator in background
            self.logger.info("Starting orchestrator task")
            self.orchestrator_task = asyncio.create_task(
                self.run_orchestrator(request)
            )

            # Run input loop concurrently with orchestrator
            # (No render_loop needed - orchestrator prints directly)
            self.logger.info("Starting concurrent tasks (input, orchestrator)")
            await asyncio.gather(
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
        """Run orchestrator directly (no subprocess) with control_queue for interventions"""
        from flow_claude.cli import run_development_session
        import os

        # Load prompts (same logic as cli.py)
        working_dir = os.getcwd()
        prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

        def get_prompt_file(local_name, fallback_name):
            """Get prompt file from working dir, copying default if it doesn't exist."""
            local_path = os.path.join(working_dir, local_name)
            default_path = os.path.abspath(os.path.join(prompts_dir, fallback_name))

            # If local prompt doesn't exist, copy the default template
            if not os.path.exists(local_path):
                try:
                    import shutil
                    shutil.copy2(default_path, local_path)
                    if self.debug:
                        print(f"DEBUG: Copied default prompt {fallback_name} -> {local_name}")
                except Exception as e:
                    # If copy fails, fall back to using default directly
                    if self.debug:
                        print(f"DEBUG: Failed to copy prompt, using default: {e}")
                    return default_path

            return local_path

        orchestrator_prompt_file = get_prompt_file('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md')
        planner_prompt_file = get_prompt_file('PLANNER_INSTRUCTIONS.md', 'planner.md')
        worker_prompt_file = get_prompt_file('WORKER_INSTRUCTIONS.md', 'worker.md')
        user_proxy_prompt_file = get_prompt_file('USER_PROXY_INSTRUCTIONS.md', 'user.md')

        orchestrator_prompt = f"@{orchestrator_prompt_file}"
        planner_prompt = f"@{planner_prompt_file}"
        worker_prompt = f"@{worker_prompt_file}"
        user_proxy_prompt = f"@{user_proxy_prompt_file}"

        # Determine execution mode
        enable_parallel = self.max_parallel > 1
        num_workers = self.max_parallel if enable_parallel else 1

        try:
            # Call run_development_session directly with control_queue and logger
            await run_development_session(
                request=request,
                model=self.model,
                max_turns=100,
                permission_mode="bypassPermissions",  # Non-interactive mode
                enable_parallel=enable_parallel,
                max_parallel=self.max_parallel,
                verbose=self.verbose,
                debug=self.debug,
                orchestrator_prompt=orchestrator_prompt,
                planner_prompt=planner_prompt,
                worker_prompt=worker_prompt,
                user_proxy_prompt=user_proxy_prompt,
                num_workers=num_workers,
                control_queue=self.control_queue,  # Pass control_queue for interventions!
                logger=self.logger  # Pass logger for file logging
            )
        except asyncio.CancelledError:
            # Session was cancelled
            pass
        except Exception as e:
            print(f"\nERROR: Orchestrator error: {str(e)}")
            if self.debug:
                import traceback
                traceback.print_exc()

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
                    self.logger.info("User pressed ESC - requesting intervention")
                    # Queue intervention request (don't prompt yet - wait for clean output)
                    await self.control_queue.put({
                        "type": "intervention_pending",
                        "data": {}
                    })
                    print("\n\n  [ESC PRESSED] Waiting for current operation to complete...")

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

    async def cleanup(self):
        """Clean up resources"""
        if self.orchestrator_task and not self.orchestrator_task.done():
            self.orchestrator_task.cancel()
            try:
                await self.orchestrator_task
            except asyncio.CancelledError:
                pass

    def ensure_prompt_files(self):
        """Ensure prompt instruction files exist in working directory"""
        import os
        import shutil

        working_dir = os.getcwd()
        prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

        prompt_files = [
            ('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md'),
            ('PLANNER_INSTRUCTIONS.md', 'planner.md'),
            ('WORKER_INSTRUCTIONS.md', 'worker.md'),
            ('USER_PROXY_INSTRUCTIONS.md', 'user.md')
        ]

        for local_name, fallback_name in prompt_files:
            local_path = os.path.join(working_dir, local_name)
            default_path = os.path.abspath(os.path.join(prompts_dir, fallback_name))

            # If local prompt doesn't exist, copy the default template
            if not os.path.exists(local_path):
                try:
                    shutil.copy2(default_path, local_path)
                    self.logger.info(f"Created prompt file: {local_name}")
                    if self.debug:
                        print(f"  Created: {local_name}")
                except Exception as e:
                    # Log error but don't fail - will use default directly
                    self.logger.warning(f"Failed to copy prompt {local_name}: {e}")
                    if self.debug:
                        print(f"  Warning: Could not copy {local_name}: {e}")

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
                            timeout=180  # 3 minutes for Claude Code to analyze and generate CLAUDE.md
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
