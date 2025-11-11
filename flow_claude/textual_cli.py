"""Textual-based CLI controller for Flow-Claude."""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Input, RichLog
from textual import on

from flow_claude.logging_config import get_logger, cleanup_old_logs


class TextualStdout:
    """Stdout replacement for Textual - captures all print/click.echo output."""

    def __init__(self, app):
        self.app = app
        self.original_stdout = sys.stdout
        self._buffer = ""

    def write(self, text):
        """Write text to log widget."""
        if not text:
            return 0

        # Convert bytes to string if needed
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')

        # Convert to string if it's another type
        if not isinstance(text, str):
            text = str(text)

        # Buffer partial lines
        self._buffer += text

        # Process complete lines
        if '\n' in self._buffer:
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]  # Keep incomplete line

            for line in lines[:-1]:
                if line.strip():  # Skip empty lines
                    try:
                        self.app.call_from_thread(self._write_to_log, line)
                    except:
                        # Fallback if app not ready
                        try:
                            self.original_stdout.write(line + '\n')
                        except:
                            pass

        return len(text)

    def _write_to_log(self, text):
        """Internal method to write to log (runs in main thread)."""
        try:
            log = self.app.query_one(RichLog)
            log.write(text)
            log.scroll_end(animate=False)
        except:
            pass

    def flush(self):
        """Flush buffered content."""
        if self._buffer:
            try:
                # Write any remaining buffer content
                self.app.call_from_thread(self._write_to_log, self._buffer)
            except:
                try:
                    # Fallback to original stdout
                    self.original_stdout.write(self._buffer)
                    self.original_stdout.flush()
                except:
                    pass
            finally:
                self._buffer = ""

    def fileno(self):
        """Return invalid file descriptor to prevent real file operations."""
        raise OSError("Textual stdout has no file descriptor")

    def isatty(self):
        """Not a TTY."""
        return False


class TextualStderr(TextualStdout):
    """Stderr replacement for Textual - displays errors in red."""

    def __init__(self, app):
        super().__init__(app)
        self.original_stderr = sys.stderr

    def _write_to_log(self, text):
        """Write error text with error styling."""
        try:
            log = self.app.query_one(RichLog)
            log.write(f"[red]{text}[/red]")
            log.scroll_end(animate=False)
        except:
            pass


class FlowCLI(App):
    """Textual UI for Flow-Claude interactive sessions."""

    CSS = """
    #main-log {
        height: 1fr;
        background: $surface;
        border: solid $panel;
    }
    #main-input {
        dock: bottom;
        background: $surface;
        border: solid $panel;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "interrupt", "Interrupt", show=True),
        Binding("h", "help", "Help", show=True),
    ]

    def __init__(self, model: str = 'sonnet', max_parallel: int = 3,
                 verbose: bool = False, debug: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.max_parallel = max_parallel
        self.verbose_mode = verbose
        self.debug_mode = debug

        # Session state
        self.control_queue: Optional[asyncio.Queue] = None
        self.shutdown_requested = False
        self.auto_mode = True
        self.orchestrator_session_id = None
        self.orchestrator_task = None

        # Logging
        self.logger = None
        self.session_id = None

        # Input handling
        self._interrupt_event = asyncio.Event()
        self._awaiting_initial_request = True

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield RichLog(
            id="main-log",
            auto_scroll=True,
            max_lines=10000,
            wrap=True,
            markup=True,
            highlight=True
        )
        yield Input(id="main-input", placeholder="Enter your request...")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize and start the CLI session."""
        log = self.query_one(RichLog)
        log.border_title = "Flow-Claude v6.7 - Git-First Autonomous Development"

        # Redirect stdout/stderr to capture all output (click.echo, print, etc.)
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = TextualStdout(self)
        sys.stderr = TextualStderr(self)

        # Register this app as the message handler for cli.py
        from flow_claude import cli
        cli._message_handler = self

        # Show welcome and initialize
        await self.show_welcome()
        cleanup_old_logs()

        # Initialize session
        self.session_id = datetime.now().strftime("session-%Y%m%d-%H%M%S")
        self.logger = get_logger(self.session_id)
        self.logger.info(f"Starting session (model={self.model}, max_parallel={self.max_parallel})")

        self.control_queue = asyncio.Queue()

        # Check initialization
        await self.check_and_prompt_init()
        self.ensure_prompt_files()

        # Focus input for user to start
        input_widget = self.query_one("#main-input", Input)
        input_widget.focus()

    async def on_unmount(self) -> None:
        """Clean up when app unmounts."""
        # Restore original stdout/stderr
        if hasattr(self, '_original_stdout'):
            sys.stdout = self._original_stdout
        if hasattr(self, '_original_stderr'):
            sys.stderr = self._original_stderr

        # Unregister message handler
        from flow_claude import cli
        if cli._message_handler is self:
            cli._message_handler = None

    def _log(self, text):
        """Helper to write to log and ensure visibility."""
        log = self.query_one(RichLog)
        log.write(text)
        log.scroll_end(animate=False)

    async def show_welcome(self) -> None:
        """Show welcome banner."""
        banner = """[bold cyan]Flow-Claude v6.7[/bold cyan]
[dim]Git-First Autonomous Development System[/dim]

[bold]Commands:[/bold]
  \\parallel  - Set max parallel workers    \\model     - Select Claude model
  \\verbose   - Toggle verbose output       \\debug     - Toggle debug mode
  \\auto      - Toggle autonomous mode      \\init      - Generate CLAUDE.md
  \\help      - Show help                    \\exit      - Exit Flow-Claude

[bold]Keys:[/bold] Q=quit, ESC=interrupt, H=help
"""
        for line in banner.split('\n'):
            self._log(line)
        self._log("")

    @on(Input.Submitted)
    async def handle_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission - works concurrently with orchestrator."""
        request = event.input.value.strip()
        event.input.value = ""  # Clear input immediately

        if not request:
            return

        log = self.query_one(RichLog)
        self._log(f"[bold cyan]> {request}[/bold cyan]")

        # Handle exit commands
        if request in ['\\exit', '\\q']:
            self.action_quit()
            return

        # Handle slash commands
        if request.startswith('\\'):
            handled = await self.handle_slash_command(request)
            if handled:
                return
            # If not handled, fall through to send as request

        # First request - start orchestrator
        if self._awaiting_initial_request:
            self._awaiting_initial_request = False
            self._log(f"[dim]Log file: {self.logger.log_file}[/dim]")
            self._log("")

            # Queue initial request
            await self.control_queue.put({
                "type": "intervention",
                "data": {"requirement": request}
            })

            # Start orchestrator in background (don't await!)
            self.orchestrator_task = asyncio.create_task(self.run_orchestrator(request))

        else:
            # Follow-up request while orchestrator is running
            self._log("[yellow]Queuing follow-up request...[/yellow]")
            await self.control_queue.put({
                "type": "intervention",
                "data": {"requirement": request}
            })
            if self.debug_mode:
                self._log(f"[dim]DEBUG: Intervention queued: {request[:50]}...[/dim]")

            # Ensure UI is responsive
            log = self.query_one(RichLog)
            log.scroll_end(animate=False)

    async def run_orchestrator(self, request: str):
        """Run the orchestrator session (runs in background)."""
        from flow_claude.cli import run_development_session

        # Load prompts
        working_dir = os.getcwd()
        prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

        def get_prompt_file(local_name, fallback_name):
            local_path = os.path.join(working_dir, local_name)
            default_path = os.path.join(prompts_dir, fallback_name)
            if not os.path.exists(local_path):
                import shutil
                shutil.copy2(default_path, local_path)
            return local_path

        # Get prompt files
        orch_file = get_prompt_file('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md')
        planner_file = get_prompt_file('PLANNER_INSTRUCTIONS.md', 'planner.md')
        worker_file = get_prompt_file('WORKER_INSTRUCTIONS.md', 'worker.md')
        user_file = get_prompt_file('USER_PROXY_INSTRUCTIONS.md', 'user.md')

        # Format prompts with @ syntax
        orchestrator_prompt = f"@{orch_file}"
        planner_prompt = f"@{planner_file}"
        worker_prompt = f"@{worker_file}"
        user_proxy_prompt = f"@{user_file}" if self.auto_mode else None

        # Determine execution mode
        enable_parallel = self.max_parallel > 1
        num_workers = self.max_parallel if enable_parallel else 1

        try:
            await run_development_session(
                initial_request=request,
                session_id=self.session_id,
                model=self.model,
                max_turns=100,
                permission_mode="bypassPermissions",
                enable_parallel=enable_parallel,
                max_parallel=self.max_parallel,
                verbose=self.verbose_mode,
                debug=self.debug_mode,
                orchestrator_prompt=orchestrator_prompt,
                planner_prompt=planner_prompt,
                worker_prompt=worker_prompt,
                user_proxy_prompt=user_proxy_prompt,
                num_workers=num_workers,
                control_queue=self.control_queue,
                logger=self.logger,
                auto_mode=self.auto_mode,
                resume_session_id=self.orchestrator_session_id
            )

            # Capture session ID after session completes
            from flow_claude import cli
            if hasattr(cli, '_current_session_id') and cli._current_session_id:
                self.orchestrator_session_id = cli._current_session_id

            # Session completed - ready for next request
            log = self.query_one(RichLog)
            self._log("\n[dim]Session ready for next request...[/dim]\n")

        except asyncio.CancelledError:
            log = self.query_one(RichLog)
            self._log("[yellow]Session cancelled[/yellow]")
        except Exception as e:
            self.logger.exception(f"Orchestrator error: {e}")
            log = self.query_one(RichLog)
            self._log(f"[.error]ERROR: {e}[/.error]")

    async def handle_slash_command(self, command: str) -> bool:
        """Handle slash commands. Returns True if handled."""
        cmd = command.strip().lower()
        log = self.query_one(RichLog)

        if cmd in ['\\exit', '\\q']:
            self.exit()
            return True
        elif cmd == '\\help':
            self.action_help()
            return True
        elif cmd == '\\verbose':
            self.verbose_mode = not self.verbose_mode
            self._log(f"[green]Verbose mode: {'ON' if self.verbose_mode else 'OFF'}[/green]")
            return True
        elif cmd == '\\debug':
            self.debug_mode = not self.debug_mode
            self._log(f"[green]Debug mode: {'ON' if self.debug_mode else 'OFF'}[/green]")
            return True
        elif cmd == '\\auto':
            self.auto_mode = not self.auto_mode
            self._log(f"[green]Autonomous mode: {'ON' if self.auto_mode else 'OFF'}[/green]")
            return True
        # TODO: Add other commands (\parallel, \model, \init)
        return False

    def action_quit(self) -> None:
        """Quit the application."""
        # Restore stdout/stderr before exiting
        if hasattr(self, '_original_stdout'):
            sys.stdout = self._original_stdout
        if hasattr(self, '_original_stderr'):
            sys.stderr = self._original_stderr
        self.exit()

    def action_interrupt(self) -> None:
        """Handle interrupt (ESC) - interrupts current task."""
        self._interrupt_event.set()
        log = self.query_one(RichLog)
        self._log("\n[bold yellow][ESC] Interrupting current task...[/bold yellow]")

        # Flush any buffered output before interrupt
        if hasattr(sys.stdout, 'flush'):
            try:
                sys.stdout.flush()
                if hasattr(sys.stderr, 'flush'):
                    sys.stderr.flush()
            except:
                pass

        # Send stop signal to control queue
        if self.control_queue:
            asyncio.create_task(self.control_queue.put({"type": "stop"}))
            if self.debug_mode:
                self._log("[dim]DEBUG: Stop signal queued[/dim]")

        self._log("[dim]Task will be interrupted. Type new request to continue.[/dim]\n")

    def action_help(self) -> None:
        """Show help."""
        help_text = """[bold]Flow-Claude Commands:[/bold]
\\parallel N  - Set max parallel workers (1-10)
\\model NAME  - Select Claude model (sonnet/opus/haiku)
\\verbose     - Toggle verbose output
\\debug       - Toggle debug mode
\\auto        - Toggle autonomous mode
\\init        - Generate CLAUDE.md template
\\help        - Show this help
\\exit, \\q   - Exit Flow-Claude"""
        log = self.query_one(RichLog)
        self._log(help_text)

    async def check_and_prompt_init(self):
        """Check for CLAUDE.md and prompt to initialize."""
        # Simplified version - just check if file exists
        if not os.path.exists('CLAUDE.md'):
            log = self.query_one(RichLog)
            self._log("[yellow]CLAUDE.md not found. Use \\init to generate it.[/yellow]")

    def ensure_prompt_files(self):
        """Ensure prompt files exist."""
        # This will be handled by get_prompt_file in run_orchestrator
        pass

    def write_message(self, message: str, agent: Optional[str] = None,
                     timestamp: Optional[str] = None) -> None:
        """Write a message to the log (thread-safe).

        This implements the message handler interface for cli.py.
        """
        try:
            # Try to call from thread (in case called from SDK thread)
            self.call_from_thread(self._write_message_internal, message, agent, timestamp)
        except:
            # If not in async context or app not running, call directly
            self._write_message_internal(message, agent, timestamp)

    def _write_message_internal(self, message: str, agent: Optional[str] = None,
                                timestamp: Optional[str] = None) -> None:
        """Internal method to write message (must run in main thread)."""
        try:
            log = self.query_one(RichLog)

            prefix_parts = []
            if timestamp:
                prefix_parts.append(f"[dim]{timestamp}[/dim]")

            if agent:
                agent_lower = agent.lower()
                if "planner" in agent_lower:
                    prefix_parts.append(f"[blue]\\[{agent.upper()}][/blue]")
                elif "worker" in agent_lower:
                    prefix_parts.append(f"[green]\\[{agent.upper()}][/green]")
                elif "system" in agent_lower:
                    prefix_parts.append(f"[yellow]\\[{agent.upper()}][/yellow]")
                else:
                    # Orchestrator - use default/white color
                    prefix_parts.append(f"[white]\\[{agent.upper()}][/white]")

            full_message = " ".join(prefix_parts) + f" {message}" if prefix_parts else message
            self._log(full_message)
        except Exception as e:
            # Fallback to print if something goes wrong
            print(f"{agent or ''} {message}")
