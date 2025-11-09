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

import questionary

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
        self.should_exit_cli = False  # Flag for 'q' to quit entire CLI
        self.auto_mode = True  # Default: user agent enabled for autonomous decisions
        self.orchestrator_session_id = None  # SDK session ID for resume

        # Logger (will be initialized in run())
        self.logger = None

    def show_welcome_banner(self):
        """Show welcome banner once at CLI startup"""
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
        print("  Available Commands:")
        print("    \\parallel  - Set max parallel workers")
        print("    \\model     - Select Claude model")
        print("    \\verbose   - Toggle verbose output")
        print("    \\debug     - Toggle debug mode")
        print("    \\auto      - Toggle autonomous mode")
        print("    \\init      - Generate CLAUDE.md")
        print("    \\help      - Show help")
        print("    \\exit      - Exit Flow-Claude")
        print()
        print("  Tip: Type '\\' to see autocomplete suggestions (in terminal)")
        print("  While agents work: Type follow-up requests or '\\stop' to cancel")
        print("  Quit: Type '\\exit' or '\\q'")

    async def run(self):
        """Main async CLI loop - supports continuous sessions"""
        # Show welcome banner once at startup
        self.show_welcome_banner()

        # Cleanup old logs once at startup
        cleanup_old_logs()

        # One-time initialization checks (CLAUDE.md, prompts)
        await self.check_and_prompt_init()
        self.ensure_prompt_files()

        # Main session loop - continue until user explicitly exits
        is_first_request = True
        while not self.should_exit_cli:
            # Initialize NEW session
            session_id = datetime.now().strftime("session-%Y%m%d-%H%M%S")
            self.logger = get_logger(session_id)
            self.logger.info(f"Starting new session (model={self.model}, max_parallel={self.max_parallel})")

            try:
                # Get development request from user
                request = await self.get_request(show_banner=False, is_first_request=is_first_request)
                is_first_request = False  # After first request, all subsequent are not first
                if not request:
                    # User requested exit via \exit or empty input handling
                    break

                self.logger.info(f"User request: {request}")

                # Print log file location
                print(f"  Log file: {self.logger.log_file}")
                print()

                # Run the session
                await self.run_session(request)

                # Check if user pressed 'q' to exit entirely
                if self.should_exit_cli:
                    break

                # Session completed successfully
                print("\n  " + "=" * 76)
                print("  Session complete. Enter another request or type \\exit to quit.")
                print("  " + "=" * 76 + "\n")

            except KeyboardInterrupt:
                print("\n\nInterrupted by user (Ctrl+C)")
                self.logger.warning("Session interrupted by Ctrl+C")
                await self.cleanup()
                break  # Exit CLI on Ctrl+C

            except Exception as e:
                print(f"\n\nError: {e}")
                self.logger.exception(f"Fatal error: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                await self.cleanup()
                # Don't break - allow user to try another session

            finally:
                # Clean up current session
                if self.logger:
                    self.logger.close()
                    self.logger = None

        # Final exit message
        print("\n  Exiting Flow-Claude...\n")

    async def run_session(self, request: str):
        """Run a single development session"""
        # Reset session state
        self.shutdown_requested = False
        self.control_queue = asyncio.Queue()

        # Start orchestrator in background
        self.logger.info("Starting orchestrator task")
        self.orchestrator_task = asyncio.create_task(
            self.run_orchestrator(request)
        )

        # Run input loop concurrently with orchestrator
        self.logger.info("Starting concurrent tasks (input, orchestrator)")
        await asyncio.gather(
            self.input_loop(),       # Handle keyboard input (q/ESC/p)
            self.orchestrator_task,  # Orchestrator execution
            return_exceptions=True
        )

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
                logger=self.logger,  # Pass logger for file logging
                auto_mode=self.auto_mode,  # Pass auto_mode for user agent control
                resume_session_id=self.orchestrator_session_id  # Resume from previous session if available
            )

            # Capture session ID after session completes (for future resume)
            from flow_claude import cli
            if hasattr(cli, '_current_session_id') and cli._current_session_id:
                self.orchestrator_session_id = cli._current_session_id
                if self.debug:
                    print(f"DEBUG: Captured session ID: {self.orchestrator_session_id}")

        except asyncio.CancelledError:
            # Session was cancelled - preserve session ID for resume
            from flow_claude import cli
            if hasattr(cli, '_current_session_id') and cli._current_session_id:
                self.orchestrator_session_id = cli._current_session_id
                if self.debug:
                    print(f"DEBUG: Session cancelled, preserved ID: {self.orchestrator_session_id}")
            pass
        except Exception as e:
            print(f"\nERROR: Orchestrator error: {str(e)}")
            if self.debug:
                import traceback
                traceback.print_exc()

    async def input_loop(self):
        """Handle user input - always-available text input for follow-up requests"""
        loop = asyncio.get_event_loop()
        self.logger.debug("Input loop started")

        # Show initial prompt with top border
        print("\n" + "-" * 78)

        while not self.shutdown_requested:
            try:
                # Show prompt
                print("  > ", end="", flush=True)

                # Read full line of input asynchronously
                user_input = await loop.run_in_executor(
                    None,
                    lambda: input().strip()
                )

                # Print bottom border immediately on next line, then blank line
                print("-" * 78, flush=True)  # Force immediate flush to prevent race condition
                print(flush=True)  # Blank line, also flushed
                await asyncio.sleep(0.01)  # Give border time to render (10ms)

                # Handle different input types
                if not user_input:
                    # Empty input - show top border and prompt again
                    print("-" * 78)
                    continue

                elif user_input in ['\\q', '\\exit', 'q']:
                    # Quit entire CLI
                    self.logger.info("User requested quit")
                    print("\n  Shutting down... Please wait.")
                    self.shutdown_requested = True
                    self.should_exit_cli = True

                    # Cancel orchestrator
                    if self.orchestrator_task:
                        self.orchestrator_task.cancel()

                    break

                elif user_input in ['\\stop', 'stop']:
                    # Hard cancel - stops ALL agents immediately
                    # Session ID preserved for resume
                    self.logger.info("User requested stop (will resume session)")
                    print("\n  [STOP] Stopping all agents...")

                    # Cancel orchestrator task (kills all agents including subagents)
                    if self.orchestrator_task and not self.orchestrator_task.done():
                        self.orchestrator_task.cancel()

                        # Wait for task to actually stop (with timeout)
                        try:
                            await asyncio.wait_for(self.orchestrator_task, timeout=2.0)
                        except asyncio.CancelledError:
                            pass
                        except asyncio.TimeoutError:
                            self.logger.warning("Orchestrator task did not stop within timeout")
                        except Exception as e:
                            self.logger.warning(f"Error waiting for orchestrator to stop: {e}")

                    # Session ID already captured in CancelledError handler
                    print("  Stopped. Session will resume when you continue.")
                    print("  Type new request to continue, or \\q to quit.")
                    print()
                    print("-" * 78)
                    # Loop will show prompt again
                    # Don't break - stay in input loop for follow-up

                else:
                    # User typed a follow-up request
                    self.logger.info(f"User follow-up request: {user_input}")

                    # Check if orchestrator is still running
                    if self.orchestrator_task and not self.orchestrator_task.done():
                        # Orchestrator is running - queue intervention
                        await self.control_queue.put({
                            "type": "intervention",
                            "data": {
                                "requirement": user_input,
                                "timestamp": datetime.now().isoformat()
                            }
                        })
                        print("  ✓ Request queued, agents will adjust")
                    else:
                        # Orchestrator was stopped - restart with resume
                        print("  ✓ Resuming session...")
                        self.orchestrator_task = asyncio.create_task(
                            self.run_orchestrator(user_input)
                        )
                        # Note: run_orchestrator will use self.orchestrator_session_id for resume

                    print()
                    print("-" * 78)
                    # Loop will show prompt again

            except asyncio.CancelledError:
                self.logger.debug("Input loop cancelled")
                break
            except KeyboardInterrupt:
                # Ctrl+C - quit CLI
                self.logger.info("Keyboard interrupt - quitting")
                print("\n\n  Interrupted. Quitting...")
                self.shutdown_requested = True
                self.should_exit_cli = True

                if self.orchestrator_task:
                    self.orchestrator_task.cancel()

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

    def wait_for_any_key(self) -> str:
        """Wait for any keypress (blocking, no timeout)"""
        import sys

        if sys.platform == 'win32':
            import msvcrt
            # Wait indefinitely for a keypress
            return msvcrt.getch().decode('utf-8', errors='ignore')
        else:
            import tty
            import termios

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                # Wait indefinitely for input
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    async def handle_intervention_immediate(self):
        """Handle ESC - stop agents immediately and get intervention"""
        print()
        print("  " + "=" * 76)
        print("  INTERVENTION MODE")
        print("  " + "=" * 76)
        print()
        print("  All agents have been stopped.")
        print("  Enter additional requirements:")
        print("  (Press Enter with empty input to cancel)")
        print()

        # Get requirement from user (async)
        loop = asyncio.get_event_loop()
        try:
            # Show input border
            print("\n" + "-" * 78)
            requirement = await loop.run_in_executor(
                None,
                lambda: input("  > Additional requirement: ").strip()
            )
            print("-" * 78)

            if requirement:
                self.logger.info(f"Intervention: User added requirement: {requirement}")
                # Send stop and intervention signal
                await self.control_queue.put({
                    "type": "stop_and_intervene",
                    "data": {
                        "requirement": requirement,
                        "timestamp": datetime.now().isoformat()
                    }
                })

                print()
                print("  ✓ Requirement will be sent to orchestrator")
            else:
                self.logger.info("Intervention: No requirement added, resuming")
                print()
                print("  No requirement added. Resuming...")

            print("  " + "=" * 76)
            print()

        except (EOFError, KeyboardInterrupt):
            print()
            print("  Intervention cancelled. Resuming...")
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

        created_files = []  # Track newly created files for auto-commit

        for local_name, fallback_name in prompt_files:
            local_path = os.path.join(working_dir, local_name)
            default_path = os.path.abspath(os.path.join(prompts_dir, fallback_name))

            # If local prompt doesn't exist, copy the default template
            if not os.path.exists(local_path):
                try:
                    shutil.copy2(default_path, local_path)
                    created_files.append(local_name)  # Track this file was created
                    if self.logger:
                        self.logger.info(f"Created prompt file: {local_name}")
                    if self.debug:
                        print(f"  Created: {local_name}")
                except Exception as e:
                    # Log error but don't fail - will use default directly
                    if self.logger:
                        self.logger.warning(f"Failed to copy prompt {local_name}: {e}")
                    if self.debug:
                        print(f"  Warning: Could not copy {local_name}: {e}")

        # Auto-commit newly created files to main branch
        if created_files:
            self.commit_prompt_files_to_main(created_files)

    def commit_prompt_files_to_main(self, created_files: list):
        """
        Commit newly created instruction files to main branch.

        This ensures task branches created later will have these files.

        Args:
            created_files: List of instruction file names that were just created
        """
        import subprocess
        from pathlib import Path

        try:
            # Check if git repo exists
            if not Path('.git').exists():
                if self.debug:
                    print("  No git repository - skipping auto-commit")
                return

            # Check current branch (empty output means no commits yet, which is fine)
            try:
                result = subprocess.run(
                    'git branch --show-current',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                current_branch = result.stdout.strip()

                # If there's a current branch and it's not main/master, skip
                if current_branch and current_branch not in ['main', 'master']:
                    if self.debug:
                        print(f"  Not on main/master branch ({current_branch}) - skipping auto-commit")
                    return
            except Exception:
                # If we can't determine branch, assume it's safe (probably fresh repo)
                pass

            # Check if files are untracked
            untracked_files = []
            for filename in created_files:
                result = subprocess.run(
                    f'git status --porcelain "{filename}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                status = result.stdout.strip()
                # ?? means untracked, which is what we want
                if status.startswith('??'):
                    untracked_files.append(filename)

            if not untracked_files:
                if self.debug:
                    print("  Instruction files already tracked - skipping auto-commit")
                return

            # Stage the untracked files
            files_str = ' '.join(f'"{f}"' for f in untracked_files)
            subprocess.run(
                f'git add {files_str}',
                shell=True,
                check=True,
                timeout=10
            )

            # Commit with descriptive message
            commit_message = """Initialize Flow-Claude instruction files

Added agent instruction files for Flow-Claude v6.7

🤖 Auto-committed by Flow-Claude"""

            subprocess.run(
                f'git commit -m "{commit_message}"',
                shell=True,
                check=True,
                capture_output=True,
                timeout=10
            )

            if self.logger:
                self.logger.info(f"Auto-committed instruction files to main: {', '.join(untracked_files)}")
            if self.debug:
                print(f"  ✓ Committed instruction files to main branch")

        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.warning("Git command timed out during auto-commit")
            if self.debug:
                print("  Warning: Git command timed out - instruction files not committed")
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.warning(f"Git command failed during auto-commit: {e}")
            if self.debug:
                print(f"  Warning: Could not auto-commit instruction files")
                print(f"  You can manually commit them with: git add *_INSTRUCTIONS.md && git commit -m 'Add Flow-Claude instructions'")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Unexpected error during auto-commit: {e}")
            if self.debug:
                print(f"  Warning: Could not auto-commit instruction files: {e}")

    async def setup_flow_branch(self):
        """Setup flow branch if it doesn't exist"""
        import subprocess

        try:
            # Check if flow branch exists
            flow_check = subprocess.run(
                ['git', 'rev-parse', '--verify', 'flow'],
                capture_output=True,
                timeout=5
            )

            if flow_check.returncode == 0:
                # Flow branch exists - use it
                print("\n  ✓ Flow branch found. Using existing flow branch for this session.\n")
                return

            # Flow branch doesn't exist - need to create it
            print("\n  " + "=" * 76)
            print("  FLOW BRANCH SETUP")
            print("  " + "=" * 76)
            print("\n  Flow-Claude uses a dedicated 'flow' branch for development work.")
            print("  This keeps your work isolated until you're ready to merge.\n")

            # Get list of branches
            branches_result = subprocess.run(
                ['git', 'branch', '--format=%(refname:short)'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True,
                timeout=5
            )
            branches = [b.strip() for b in branches_result.stdout.strip().split('\n') if b.strip()]

            if not branches:
                # No branches yet - create main and use it
                print("  No branches found. Creating 'main' branch...")
                subprocess.run(
                    ['git', 'checkout', '-b', 'main'],
                    capture_output=True,
                    check=True,
                    timeout=5
                )
                branches = ['main']
                selected_base = 'main'
            else:
                # Get current branch as default
                current_result = subprocess.run(
                    ['git', 'branch', '--show-current'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=5
                )
                current_branch = current_result.stdout.strip()

                # Prepare choices with current branch indicator
                choices = []
                default_choice = None

                for branch in branches:
                    if branch == current_branch:
                        label = f"{branch} (current)"
                        default_choice = label
                    else:
                        label = branch
                    choices.append(label)

                # If no current branch match, default to first branch
                if default_choice is None and choices:
                    default_choice = choices[0]

                # Interactive selection with arrow keys
                print("  Select base branch for flow branch:")
                selected_label = await questionary.select(
                    "",  # Empty message since we print above
                    choices=choices,
                    default=default_choice,
                    pointer="  →",
                    qmark="",
                    use_arrow_keys=True,
                    use_jk_keys=True,
                    instruction="  (Use arrow keys, j/k, or Enter to select)"
                ).ask_async()

                # Extract branch name (remove " (current)" suffix if present)
                if selected_label:
                    selected_base = selected_label.replace(" (current)", "")
                else:
                    # Handle Ctrl+C or ESC - use current branch as fallback
                    print("\n  Selection cancelled, using current branch.")
                    selected_base = current_branch if current_branch else branches[0]

            # Create flow branch from selected base
            print(f"\n  Creating 'flow' branch from '{selected_base}'...")
            subprocess.run(
                ['git', 'branch', 'flow', selected_base],
                capture_output=True,
                check=True,
                timeout=5
            )
            print(f"  ✓ Created 'flow' branch from '{selected_base}'\n")

        except subprocess.CalledProcessError as e:
            print(f"\n  ERROR: Failed to setup flow branch: {e}")
            if self.logger:
                self.logger.error(f"Flow branch setup failed: {e}")
        except Exception as e:
            print(f"\n  ERROR: Unexpected error during flow branch setup: {e}")
            if self.logger:
                self.logger.error(f"Unexpected error in flow branch setup: {e}")

    async def check_and_prompt_init(self):
        """Check if directory needs CLAUDE.md initialization and flow branch setup"""
        from pathlib import Path
        import subprocess

        cwd = Path.cwd()
        claude_md = cwd / "CLAUDE.md"

        # First: Setup flow branch if needed
        await self.setup_flow_branch()

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
            print("-" * 78)
            response = input("  Would you like to initialize CLAUDE.md now? (y/n): ").strip().lower()
            print("-" * 78)

            if response in ['y', 'yes']:
                if self.logger:
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
                            if self.logger:
                                self.logger.info("CLAUDE.md initialized successfully with Claude Code")
                        else:
                            print("  ✗ CLAUDE.md creation failed.")
                            print("  You can run 'claude code' and use \\init manually.")
                            print()
                            if self.logger:
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
                    if self.logger:
                        self.logger.warning(f"Claude Code CLI not available: {e}")

                break

            elif response in ['n', 'no']:
                if self.logger:
                    self.logger.info("User declined to create CLAUDE.md")
                print()
                print("  Skipping CLAUDE.md initialization.")
                print("  Note: CLAUDE.md helps Claude Code understand your project better.")
                print()
                break
            else:
                print("  Please enter 'y' or 'n'")

    async def get_request(self, show_banner: bool = True, is_first_request: bool = True) -> str:
        """Get development request from user (plain input prompt)

        Args:
            show_banner: If True, show welcome banner. False for subsequent sessions.
            is_first_request: If True, this is the first request of the session.

        Returns:
            str: User's request, or empty string to signal exit
        """
        # Show banner only if requested (first time)
        if show_banner:
            self.show_welcome_banner()

        # Check if we're in an interactive terminal
        import sys
        is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

        # Available slash commands for autocomplete
        slash_commands = [
            '\\parallel - Set maximum number of parallel workers',
            '\\model - Select Claude model (sonnet/opus/haiku)',
            '\\verbose - Toggle verbose output',
            '\\debug - Toggle debug mode',
            '\\auto - Toggle user agent (autonomous decisions)',
            '\\init - Generate CLAUDE.md template',
            '\\help - Show help message',
            '\\exit - Exit Flow-Claude',
            '\\q - Exit Flow-Claude',
        ]

        # Try questionary once, fall back permanently if it fails
        use_questionary = is_interactive
        questionary_failed = False

        # Show input border (once per get_request call)
        if is_first_request:
            print("\n" + "=" * 78)
            print("  Enter your request below (or use \\help for commands):")
            print("=" * 78)
        else:
            print("\n" + "-" * 78)
            print("  Next request:")
            print("-" * 78)

        while True:

            if use_questionary and not questionary_failed:
                try:
                    # Use questionary autocomplete for better UX (async)
                    request = await questionary.autocomplete(
                        "",
                        choices=slash_commands,
                        qmark="  >",
                        match_middle=True,
                        validate=lambda text: True,  # Allow any input
                        style=questionary.Style([
                            ('qmark', 'fg:default'),
                            ('answer', 'fg:default'),
                        ])
                    ).ask_async()

                    if request is None:  # User pressed Ctrl+C
                        return ""

                    # Extract just the command part (before ' - ')
                    if ' - ' in request:
                        request = request.split(' - ')[0]

                    request = request.strip()

                except KeyboardInterrupt:
                    return ""
                except Exception as e:
                    # Questionary failed - fall back permanently
                    questionary_failed = True
                    if self.debug:
                        print(f"\n  Note: Interactive features unavailable in this environment.")
                        print(f"  Reason: {type(e).__name__}: {e}")
                        print(f"  Using simple input mode. Type \\help for commands.\n")
                    else:
                        print(f"  Note: Using simple input mode. Type \\help for commands.\n")
                    continue
            else:
                # Simple input mode
                try:
                    request = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    return ""

            # Handle slash commands
            if request.startswith('\\'):
                if self.handle_slash_command(request):
                    continue  # Command handled, prompt again
                else:
                    # Show bottom border before exit
                    print("=" * 78 + "\n")
                    return ""  # Exit requested

            # Regular request
            if request:
                # Show bottom border after receiving request
                print("=" * 78 + "\n")
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
            print("-" * 78)
            new_value = input(f"  Max parallel workers (current: {current}): ").strip()
            print("-" * 78)
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
            print("-" * 78)
            new_value = input("  Select model: ").strip().lower()
            print("-" * 78)
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

        elif cmd == 'auto':
            self.auto_mode = not self.auto_mode
            status = "ENABLED" if self.auto_mode else "DISABLED"
            print()
            print(f"  Auto mode {status}")
            print(f"  User agent (for autonomous decisions): {'Available' if self.auto_mode else 'Not available'}")
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
            print(f"  \\auto        - Toggle user agent (autonomous decisions) [Current: {'ON' if self.auto_mode else 'OFF'}]")
            print("  \\init        - Generate CLAUDE.md template")
            print("  \\help        - Show this help message")
            print("  \\exit        - Exit Flow-Claude")
            print("  " + "-" * 76)
            print()
            return True

        elif cmd == 'exit' or cmd == 'q':
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
