"""Textual-based UI for Flow-Claude interactive CLI."""

import asyncio
from typing import Optional
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Input, Log
from textual.containers import Container


class FlowClaudeApp(App):
    """Textual UI for Flow-Claude development sessions."""

    CSS = """
    Log {
        height: 1fr;
        border: solid $primary;
    }

    Input {
        dock: bottom;
        border: solid $accent;
    }

    .orchestrator { color: white; }
    .planner { color: $secondary; }
    .worker { color: $success; }
    .system { color: $warning; }
    .error { color: $error; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("escape", "interrupt", "Interrupt", show=True),
        Binding("h", "help", "Help", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._input_queue: asyncio.Queue = asyncio.Queue()
        self._interrupt_event: asyncio.Event = asyncio.Event()
        self._current_input: Optional[Input] = None
        self._expecting_input = False

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Log(id="main-log", auto_scroll=True, max_lines=10000)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        self.query_one(Log).border_title = "Flow-Claude v6.7 - Git-First Autonomous Development"

    async def write_message(
        self, message: str, agent: Optional[str] = None, timestamp: Optional[str] = None
    ) -> None:
        """Write a message to the log with optional agent prefix and timestamp.

        Args:
            message: The message text to display
            agent: Optional agent name (orchestrator, planner, worker-N, system)
            timestamp: Optional timestamp string (HH:MM:SS format)
        """
        log = self.query_one(Log)

        # Build prefix
        prefix_parts = []
        if timestamp:
            prefix_parts.append(f"[dim]{timestamp}[/dim]")

        if agent:
            agent_lower = agent.lower()
            if "planner" in agent_lower:
                prefix_parts.append(f"[.planner][{agent}][/.planner]")
            elif "worker" in agent_lower:
                prefix_parts.append(f"[.worker][{agent}][/.worker]")
            elif "system" in agent_lower:
                prefix_parts.append(f"[.system][{agent}][/.system]")
            else:  # orchestrator or unknown
                prefix_parts.append(f"[.orchestrator][{agent}][/.orchestrator]")

        # Combine prefix and message
        if prefix_parts:
            full_message = " ".join(prefix_parts) + f" {message}"
        else:
            full_message = message

        log.write_line(full_message)

    async def write_banner(self, banner: str) -> None:
        """Write a banner message (multiline text with borders)."""
        log = self.query_one(Log)
        for line in banner.split("\n"):
            log.write_line(line)

    async def write_separator(self, char: str = "=", length: int = 78) -> None:
        """Write a separator line."""
        log = self.query_one(Log)
        log.write_line(char * length)

    async def get_input(self, prompt: str = "", placeholder: str = "") -> str:
        """Get user input asynchronously.

        Args:
            prompt: Optional prompt to display before input
            placeholder: Placeholder text for input field

        Returns:
            User input string
        """
        log = self.query_one(Log)

        # Write prompt if provided
        if prompt:
            log.write_line(f"[bold]{prompt}[/bold]")

        # Create and mount input widget
        input_widget = Input(placeholder=placeholder or "Enter your request...")
        self._current_input = input_widget
        self._expecting_input = True

        await self.mount(input_widget)
        input_widget.focus()

        # Wait for input submission
        result = await self._input_queue.get()

        # Remove input widget and echo the input to log
        await input_widget.remove()
        log.write_line(f"[bold cyan]> {result}[/bold cyan]")

        self._current_input = None
        self._expecting_input = False

        return result

    @on(Input.Submitted)
    async def handle_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if self._expecting_input:
            await self._input_queue.put(event.value)
            event.input.value = ""

    def action_quit(self) -> None:
        """Handle quit action."""
        self.exit()

    def action_interrupt(self) -> None:
        """Handle interrupt action (ESC key)."""
        self._interrupt_event.set()
        self.write_message("[bold yellow]Interrupt signal sent[/bold yellow]")

    def action_help(self) -> None:
        """Display help message."""
        help_text = """
[bold]Flow-Claude Interactive CLI[/bold]

[bold cyan]Slash Commands:[/bold cyan]
  \\parallel N  - Set max parallel workers (1-10)
  \\model NAME  - Select Claude model (sonnet/opus/haiku)
  \\verbose     - Toggle verbose output
  \\debug       - Toggle debug mode
  \\auto        - Toggle autonomous mode
  \\init        - Generate CLAUDE.md template
  \\help        - Show this help message
  \\exit, \\q   - Exit Flow-Claude

[bold cyan]Key Bindings:[/bold cyan]
  Q      - Quit
  ESC    - Interrupt current task
  H      - Show help

[bold cyan]Usage:[/bold cyan]
  Enter development requests one after another.
  The system will decompose and execute them autonomously.
  All state is stored in git commits.
"""
        asyncio.create_task(self.write_message(help_text))

    async def check_interrupt(self) -> bool:
        """Check if interrupt was triggered and reset the flag.

        Returns:
            True if interrupt was triggered, False otherwise
        """
        if self._interrupt_event.is_set():
            self._interrupt_event.clear()
            return True
        return False

    async def write_error(self, message: str) -> None:
        """Write an error message."""
        log = self.query_one(Log)
        log.write_line(f"[.error]ERROR: {message}[/.error]")

    async def write_success(self, message: str) -> None:
        """Write a success message."""
        log = self.query_one(Log)
        log.write_line(f"[bold green]✓ {message}[/bold green]")

    async def clear_log(self) -> None:
        """Clear the log display."""
        log = self.query_one(Log)
        log.clear()


# Convenience functions for backward compatibility
_app_instance: Optional[FlowClaudeApp] = None


def set_app_instance(app: FlowClaudeApp) -> None:
    """Set the global app instance."""
    global _app_instance
    _app_instance = app


def get_app_instance() -> Optional[FlowClaudeApp]:
    """Get the global app instance."""
    return _app_instance
