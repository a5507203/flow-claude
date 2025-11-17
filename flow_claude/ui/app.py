"""Main FlowCLI application for Flow-Claude."""

import asyncio
import sys
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual import on
from textual.widgets import Footer, RichLog, Label, Static
from textual.containers import Container
from textual.events import Key

from flow_claude.logging_config import get_logger, cleanup_old_logs

from .widgets import SubmittingTextArea, TextualStdout, TextualStderr
from .styles import APP_CSS, APP_BINDINGS
from .commands import CommandHandler
from .orchestrator import OrchestratorRunner


class FlowCLI(App):
    """Textual UI for Flow-Claude interactive sessions."""

    CSS = APP_CSS
    BINDINGS = APP_BINDINGS

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
        self._orchestrator_start_lock = asyncio.Lock()  # Prevent race condition on startup

        # Initialize command handler and orchestrator runner
        self.command_handler = CommandHandler(self)
        self.orchestrator_runner = OrchestratorRunner(self)

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
        with Container(id="input-container"):
            yield Label("Press Enter to submit  |  Use \\ for new line  |  Type / for commands", id="input-hint")
            yield Static("", id="suggestions")
            text_area = SubmittingTextArea(id="main-input")
            text_area.border_subtitle = "Multi-line input"
            yield text_area
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

        # Setup (flow branch + CLAUDE.md) is already handled by run_setup_ui()
        # in flow_cli.py before this app is launched
        # Just ensure prompt files exist
        self.ensure_prompt_files()

        # Focus input for user to start
        input_widget = self.query_one("#main-input", SubmittingTextArea)
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

    def _show_current_settings(self) -> None:
        """Display current settings summary."""
        settings = f"[dim]Settings: Model=[cyan]{self.model}[/cyan] | Parallel=[cyan]{self.max_parallel}[/cyan] | Verbose=[cyan]{'ON' if self.verbose_mode else 'OFF'}[/cyan] | Debug=[cyan]{'ON' if self.debug_mode else 'OFF'}[/cyan] | Auto=[cyan]{'ON' if self.auto_mode else 'OFF'}[/cyan][/dim]"
        self._log(settings)

    async def show_welcome(self) -> None:
        """Show welcome banner."""
        banner = f"""[bold cyan]Flow-Claude v6.7[/bold cyan]
[dim]Git-First Autonomous Development System[/dim]

[bold]Current Settings:[/bold]
  Model: [cyan]{self.model}[/cyan]  |  Parallel: [cyan]{self.max_parallel}[/cyan]  |  Verbose: [cyan]{'ON' if self.verbose_mode else 'OFF'}[/cyan]  |  Debug: [cyan]{'ON' if self.debug_mode else 'OFF'}[/cyan]  |  Auto: [cyan]{'ON' if self.auto_mode else 'OFF'}[/cyan]

[bold]Commands:[/bold]
  /parallel  - Set max parallel workers    /model     - Select Claude model
  /verbose   - Toggle verbose output       /debug     - Toggle debug mode
  /auto      - Toggle autonomous mode      /init      - Generate CLAUDE.md
  /help      - Show help                    /exit      - Exit Flow-Claude

[bold]Keys:[/bold] ctrl+c=quit, ESC=interrupt
"""
        for line in banner.split('\n'):
            self._log(line)
        self._log("")

    def action_submit_request(self) -> None:
        """Submit request from SubmittingTextArea."""
        # Get text from SubmittingTextArea
        text_area = self.query_one("#main-input", SubmittingTextArea)
        request = text_area.text.strip()
        text_area.text = ""  # Clear text area immediately
        text_area.styles.height = 3  # Reset to minimum height

        # Clear suggestions
        suggestions_widget = self.query_one("#suggestions", Static)
        suggestions_widget.update("")
        suggestions_widget.remove_class("visible")

        if not request:
            return

        # Run async handler in event loop
        asyncio.create_task(self._handle_request_async(request))

    @on(SubmittingTextArea.Changed, "#main-input")
    def update_slash_command_suggestions(self, event: SubmittingTextArea.Changed) -> None:
        """Update suggestions and auto-resize SubmittingTextArea based on content."""
        text = event.text_area.text
        suggestions_widget = self.query_one("#suggestions", Static)
        text_area = event.text_area

        # Auto-resize SubmittingTextArea based on line count
        lines = text.split('\n')
        line_count = len(lines)

        # Calculate height: min 3, max 20
        new_height = max(3, min(line_count, 20))
        text_area.styles.height = new_height

        # Get the last line (where user is currently typing)
        current_line = lines[-1].strip() if lines else ""

        # Only show suggestions if current line starts with forward slash
        if not current_line or not current_line.startswith('/'):
            suggestions_widget.update("")
            suggestions_widget.remove_class("visible")
            return

        # Find matching commands using command handler
        matches = self.command_handler.get_matching_commands(current_line)

        if matches:
            suggestions_text = " | ".join(matches[:3])  # Show max 3 suggestions
            suggestions_widget.update(suggestions_text)
            suggestions_widget.add_class("visible")
        else:
            suggestions_widget.update("")
            suggestions_widget.remove_class("visible")

    async def _handle_request_async(self, request: str) -> None:
        """Async handler for request submission."""
        log = self.query_one(RichLog)
        self._log(f"[bold cyan]> {request}[/bold cyan]")

        # Handle exit commands
        if request in ['/exit', '/q']:
            self.action_quit()
            return

        # Handle slash commands
        if request.startswith('/'):
            handled = await self.command_handler.handle_command(request)
            if handled:
                return
            # If not handled, fall through to send as request

        # First request - start orchestrator (with lock to prevent race condition)
        async with self._orchestrator_start_lock:
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
                self.orchestrator_task = asyncio.create_task(
                    self.orchestrator_runner.run_orchestrator(request)
                )

            else:
                # Follow-up request while orchestrator is running
                self._log("[yellow]Queuing follow-up request...[/yellow]")
                await self.control_queue.put({
                    "type": "intervention",
                    "data": {"requirement": request}
                })

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
        log = self.query_one(RichLog)
        self._log("\n[bold yellow][ESC] Interrupting current task...[/bold yellow]")

        # Clean all pending follow-up instructions, then send stop signal
        if self.control_queue:
            # Drain intervention messages from queue
            discarded = 0
            while not self.control_queue.empty():
                try:
                    msg = self.control_queue.get_nowait()
                    if msg.get("type") == "intervention":
                        discarded += 1  # Discard follow-up instructions
                    else:
                        # Keep stop/shutdown messages
                        asyncio.create_task(self.control_queue.put(msg))
                except Exception:
                    break

            if discarded > 0:
                self._log(f"[dim]Cleared {discarded} pending follow-up(s)[/dim]")

            # Send stop signal
            asyncio.create_task(self.control_queue.put({"type": "stop"}))

        self._log("[dim]Task will be interrupted. Type new request to continue.[/dim]\n")

    def ensure_prompt_files(self):
        """Ensure prompt files exist."""
        # This will be handled by orchestrator_runner._get_orchestrator_prompt()
        pass

    def write_message(self, message: str, agent: Optional[str] = None,
                     timestamp: Optional[str] = None) -> None:
        """Write a message to the log (thread-safe).

        This implements the message handler interface for cli.py.
        """
        try:
            # Try to call from thread (in case called from SDK thread)
            self.call_from_thread(self._write_message_internal, message, agent, timestamp)
        except Exception:
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
                if "worker" in agent_lower:
                    prefix_parts.append(f"[green]\\[{agent.upper()}][/green]")
                elif "user" in agent_lower:
                    prefix_parts.append(f"[cyan]\\[{agent.upper()}][/cyan]")
                elif "system" in agent_lower:
                    prefix_parts.append(f"[yellow]\\[{agent.upper()}][/yellow]")
                else:
                    # Orchestrator - use blue color
                    prefix_parts.append(f"[blue]\\[{agent.upper()}][/blue]")

            full_message = " ".join(prefix_parts) + f" {message}" if prefix_parts else message
            self._log(full_message)
        except Exception as e:
            # Fallback to print if something goes wrong
            print(f"{agent or ''} {message}")
