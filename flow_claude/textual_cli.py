"""Textual-based CLI controller for Flow-Claude."""

import asyncio
import os
import sys
from datetime import datetime
from time import sleep
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, RichLog, Label, Static, Button
from textual.containers import Container, Horizontal
from textual import on
from textual.events import Key

from flow_claude.logging_config import get_logger, cleanup_old_logs

from textual.widgets import TextArea
from textual import events






class SubmittingTextArea(TextArea):
    """Custom SubmittingTextArea that submits on Enter (unless Ctrl is pressed)."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pre_key = "" 


    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses which correspond to document inserts."""

        self._restart_blink()

        if self.read_only:
            return

        key = event.key
        insert_values = {
            "backslash":"\n",
        }

        if self.pre_key!="backslash" and event.key=="enter":
            event.prevent_default()
            event.stop()
            # Call app’s submit logic
            self.app.action_submit_request()
            self.pre_key=key
            return

        if self.tab_behavior == "indent":
            if key == "escape":
                event.stop()
                event.prevent_default()
                self.screen.focus_next()
                self.pre_key = key
                return
            if self.indent_type == "tabs":
                insert_values["tab"] = "\t"
            else:
                insert_values["tab"] = " " * self._find_columns_to_next_tab_stop()

        if event.is_printable or key in insert_values:
            event.stop()
            event.prevent_default()
            insert = insert_values.get(key, event.character)
            # `insert` is not None because event.character cannot be
            # None because we've checked that it's printable.
            assert insert is not None
            start, end = self.selection
            self._replace_via_keyboard(insert, start, end)
        

        self.pre_key = key



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
                    except Exception:
                        # Fallback if app not ready
                        try:
                            self.original_stdout.write(line + '\n')
                        except Exception:
                            # Silently fail if both methods don't work
                            pass

        return len(text)

    def _write_to_log(self, text):
        """Internal method to write to log (runs in main thread)."""
        try:
            log = self.app.query_one(RichLog)
            log.write(text)
            log.scroll_end(animate=False)
        except Exception:
            # Silently fail if log widget not available
            pass

    def flush(self):
        """Flush buffered content."""
        if self._buffer.strip():
            try:
                self.app.call_from_thread(self._write_to_log, self._buffer)
                self._buffer = ""
            except Exception:
                # Silently fail if app not available
                pass

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
        except Exception:
            # Silently fail if log widget not available
            pass


class FlowCLI(App):
    """Textual UI for Flow-Claude interactive sessions."""

    CSS = """
    #main-log {
        height: 1fr;
        background: $surface;
        border: solid $panel;
    }

    #input-container {
        dock: bottom;
        height: auto;
        background: $surface;
        padding: 0;
    }

    #input-hint {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: $panel;
        padding: 0 1;
        text-style: italic;
    }

    #main-input {
        min-height: 3;
        max-height: 20;
        height: auto;
        background: $surface;
        border: solid $panel;
        margin-top: 0;
    }

    #suggestions {
        width: 100%;
        height: auto;
        max-height: 3;
        color: $accent;
        background: $panel;
        padding: 0 1;
        display: none;
    }

    #suggestions.visible {
        display: block;
    }

    #button-row {
        height: auto;
        width: 100%;
        padding: 0 1;
        background: $surface;
    }

    #submit-button {
        width: 20;
        margin-right: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("escape", "interrupt", "Interrupt", show=True),

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
        self._orchestrator_start_lock = asyncio.Lock()  # Prevent race condition on startup

        # Slash command autocomplete
        self.slash_commands = {
            "/parallel": "Set max parallel workers (1-10)",
            "/model": "Select Claude model (sonnet/opus/haiku)",
            "/verbose": "Toggle verbose output",
            "/debug": "Toggle debug mode",
            "/auto": "Toggle autonomous mode",
            "/init": "Generate CLAUDE.md",
            "/help": "Show help",
            "/exit": "Exit Flow-Claude",
            "/q": "Exit Flow-Claude"
        }

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

    # async def on_key(self, event: Key) -> None:
    #     """Handle key presses - intercept Enter to submit."""
    #     # Only handle Enter key when SubmittingTextArea is focused
    #     if event.key == "enter":
    #         text_area = self.query_one("#main-input", SubmittingTextArea)
    #         if text_area.has_focus:
    #             # Check if Ctrl is pressed - allow Ctrl+Enter for new line
    #             if not event.ctrl:
    #                 # Plain Enter - submit the request
    #                 event.prevent_default()
    #                 event.stop()
    #                 self.action_submit_request()

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

        # Find matching commands
        matches = []
        for cmd, desc in self.slash_commands.items():
            if cmd.startswith(current_line.lower()) or cmd.startswith(current_line):
                matches.append(f"[cyan]{cmd}[/cyan] - {desc}")

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
            handled = await self.handle_slash_command(request)
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
                self.orchestrator_task = asyncio.create_task(self.run_orchestrator(request))

            else:
                # Follow-up request while orchestrator is running
                self._log("[yellow]Queuing follow-up request...[/yellow]")
                await self.control_queue.put({
                    "type": "intervention",
                    "data": {"requirement": request}
                })

    async def run_orchestrator(self, request: str):
        """Run the orchestrator session (runs in background)."""
        from flow_claude.cli import run_development_session
        from flow_claude.sdk_workers import get_sdk_worker_manager

        # Initialize WorkerManager with control_queue for async worker management
        # Create a logging function that writes to the UI log
        def worker_log(msg: str):
            log = self.query_one(RichLog)
            # Always show worker output (it's important for tracking progress)
            # Use different styling for different message types
            if "[Worker-" in msg and "ERROR]" in msg:
                # Error messages from workers
                self._log(f"[red]{msg}[/red]")
            elif "[Worker-" in msg and "]" in msg:
                # Normal output from workers
                self._log(f"[cyan]{msg}[/cyan]")
            elif "[WorkerManager]" in msg and self.debug_mode:
                # Manager debug messages only in debug mode
                self._log(f"[dim]{msg}[/dim]")
            elif "[SDKWorkerManager]" in msg and self.debug_mode:
                # SDK Manager debug messages only in debug mode
                self._log(f"[dim]{msg}[/dim]")
            elif "[Worker" in msg:
                # Other worker-related messages
                self._log(f"[blue]{msg}[/blue]")

        # Initialize SDK-based worker manager
        sdk_worker_manager = get_sdk_worker_manager(
            control_queue=self.control_queue,
            debug=self.debug_mode,
            log_func=worker_log
        )

        # Load prompts
        working_dir = os.getcwd()
        prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

        def get_prompt_file(local_name, fallback_name):
            # Store prompt files in .flow-claude/ directory
            flow_claude_dir = os.path.join(working_dir, '.flow-claude')
            os.makedirs(flow_claude_dir, exist_ok=True)

            local_path = os.path.join(flow_claude_dir, local_name)
            default_path = os.path.join(prompts_dir, fallback_name)
            if not os.path.exists(local_path):
                import shutil
                shutil.copy2(default_path, local_path)
            return local_path

        # Get prompt files
        orch_file = get_prompt_file('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md')
        worker_file = get_prompt_file('WORKER_INSTRUCTIONS.md', 'worker.md')
        user_file = get_prompt_file('USER_PROXY_INSTRUCTIONS.md', 'user.md')

        # Format prompts with @ syntax
        orchestrator_prompt = f"@{orch_file}"
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
        cmd_parts = command.strip().split()
        cmd = cmd_parts[0].lower()
        log = self.query_one(RichLog)

        if cmd in ['/exit', '/q']:
            self.exit()
            return True
        elif cmd == '/help':
            self.action_help()
            return True
        elif cmd == '/verbose':
            self.verbose_mode = not self.verbose_mode
            self._log(f"[green]✓ Verbose mode: {'ON' if self.verbose_mode else 'OFF'}[/green]")
            self._show_current_settings()
            return True
        elif cmd == '/debug':
            self.debug_mode = not self.debug_mode
            self._log(f"[green]✓ Debug mode: {'ON' if self.debug_mode else 'OFF'}[/green]")
            self._show_current_settings()
            return True
        elif cmd == '/auto':
            self.auto_mode = not self.auto_mode
            self._log(f"[green]✓ Autonomous mode: {'ON' if self.auto_mode else 'OFF'}[/green]")
            self._show_current_settings()
            return True
        elif cmd == '/parallel':
            # Set max parallel workers
            if len(cmd_parts) > 1 and cmd_parts[1].isdigit():
                new_value = int(cmd_parts[1])
                if 1 <= new_value <= 10:
                    self.max_parallel = new_value
                    self._log(f"[green]✓ Max parallel workers set to {self.max_parallel}[/green]")
                    self._show_current_settings()
                else:
                    self._log(f"[yellow]Invalid value. Must be between 1 and 10.[/yellow]")
            else:
                self._log(f"[yellow]Usage: /parallel <number> (current: {self.max_parallel})[/yellow]")
            return True
        elif cmd == '/model':
            # Select Claude model
            if len(cmd_parts) > 1:
                new_model = cmd_parts[1].lower()
                if new_model in ['sonnet', 'opus', 'haiku']:
                    self.model = new_model
                    self._log(f"[green]✓ Model set to {self.model}[/green]")
                    self._log(f"[yellow]Note: Model change will apply to next session[/yellow]")
                    self._show_current_settings()
                else:
                    self._log(f"[yellow]Invalid model. Choose: sonnet, opus, haiku[/yellow]")
            else:
                self._log(f"[yellow]Usage: /model <name> (current: {self.model})[/yellow]")
                self._log(f"[dim]Available: sonnet, opus, haiku[/dim]")
            return True
        elif cmd == '/init':
            # Generate CLAUDE.md with Claude Code (or template fallback)
            # Run in background to keep UI responsive
            self._log("[dim]Generating CLAUDE.md...[/dim]")
            self.run_worker(self._generate_claude_md_worker, thread=True)
            return True
        return False

    def _generate_claude_md_worker(self) -> None:
        """Worker function to generate CLAUDE.md in background thread."""
        from pathlib import Path
        from flow_claude.setup_ui import claude_generator

        try:
            # Check if Claude Code is available
            if claude_generator.check_claude_code_available():
                self.app.call_from_thread(
                    self._log, "[yellow]Analyzing project with Claude Code...[/yellow]"
                )
                self.app.call_from_thread(
                    self._log, "[dim]This may take up to 3 minutes...[/dim]"
                )
            else:
                self.app.call_from_thread(
                    self._log, "[yellow]Claude Code not found, using template...[/yellow]"
                )

            # Generate (tries Claude Code first, falls back to template)
            success, method, error = claude_generator.generate_claude_md(Path.cwd())

            if success:
                if method == "claude_code":
                    self.app.call_from_thread(
                        self._log, "[green]✓ CLAUDE.md generated with AI[/green]"
                    )
                else:
                    self.app.call_from_thread(
                        self._log, "[green]✓ CLAUDE.md created from template[/green]"
                    )
            else:
                self.app.call_from_thread(
                    self._log, f"[red]Error: {error}[/red]"
                )

        except Exception as e:
            self.app.call_from_thread(
                self._log, f"[red]Error generating CLAUDE.md: {e}[/red]"
            )

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

    def action_help(self) -> None:
        """Show help."""
        help_text = """[bold]Flow-Claude Commands:[/bold]
/parallel N  - Set max parallel workers (1-10)
/model NAME  - Select Claude model (sonnet/opus/haiku)
/verbose     - Toggle verbose output
/debug       - Toggle debug mode
/auto        - Toggle autonomous mode
/init        - Generate CLAUDE.md with Claude Code
/help        - Show this help
/exit, /q    - Exit Flow-Claude

[dim]Note: Settings changes apply immediately for new requests.[/dim]"""
        log = self.query_one(RichLog)
        self._log(help_text)

    async def check_and_prompt_init(self):
        """Check for CLAUDE.md and prompt to initialize."""
        # Setup (flow branch + CLAUDE.md) is handled by run_setup_ui() in flow_cli.py
        # This method is kept for backwards compatibility but does nothing
        pass

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
