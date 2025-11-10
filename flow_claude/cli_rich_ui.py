"""
Rich UI components for Flow-Claude CLI

Provides beautiful, informative terminal UI using the Rich library.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich import box


class RichUI:
    """Manages all Rich-based terminal UI for Flow-Claude"""

    # Agent type to emoji mapping (disable emojis on Windows due to encoding issues)
    @staticmethod
    def _get_agent_icons():
        import sys
        if sys.platform == 'win32':
            # Use ASCII prefixes on Windows
            return {
                "orchestrator": "[ORCH]",
                "planner": "[PLAN]",
                "worker": "[WORK]",
                "user_proxy": "[USER]",
                "system": "[SYS]",
            }
        else:
            # Use emojis on Unix/Linux
            return {
                "orchestrator": "🎯",
                "planner": "📋",
                "worker": "⚙️",
                "user_proxy": "👤",
                "system": "💻",
            }

    AGENT_ICONS = _get_agent_icons.__func__()

    # Message type colors
    COLORS = {
        "orchestrator": "cyan",
        "planner": "blue",
        "worker": "green",
        "user_proxy": "yellow",
        "system": "magenta",
        "error": "red",
        "warning": "yellow",
        "success": "green",
        "info": "cyan",
        "user": "white",
    }

    def __init__(self, verbose: bool = False, debug: bool = False):
        """
        Initialize Rich UI

        Args:
            verbose: Show detailed output
            debug: Show debug information
        """
        # Use safe_width and force_terminal for better Windows compatibility
        import sys
        self.console = Console(
            force_terminal=True,
            legacy_windows=True if sys.platform == 'win32' else False
        )
        self.verbose = verbose
        self.debug = debug
        self.current_status = "Initializing..."
        self.session_info = {}

    def safe_print(self, *args, **kwargs):
        """Safely print with emoji handling for Windows"""
        try:
            self.console.print(*args, **kwargs)
        except UnicodeEncodeError:
            # Fall back to ASCII if emojis can't be displayed
            import re
            # Remove emojis and unicode characters
            for arg in args:
                if isinstance(arg, str):
                    # Replace common emojis with text equivalents
                    cleaned = arg
                    cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned)  # Remove non-ASCII
                    self.console.print(cleaned, **kwargs)
                else:
                    self.console.print(arg, **kwargs)

    def show_banner(self):
        """Display Flow-Claude startup banner"""
        banner_text = Text()
        banner_text.append("Flow-Claude", style="bold cyan")
        banner_text.append(" | Git-Driven Autonomous Development\n", style="dim")
        banner_text.append("Powered by Claude Agent SDK", style="italic dim")

        panel = Panel(
            banner_text,
            border_style="cyan",
            box=box.DOUBLE,
            padding=(1, 2)
        )
        self.console.print(panel)
        self.console.print()

    def show_session_header(
        self,
        session_id: str,
        model: str,
        num_workers: int,
        base_branch: str = "flow"
    ):
        """
        Display session information panel at top

        Args:
            session_id: Current session ID
            model: Claude model being used
            num_workers: Number of worker agents
            base_branch: Git base branch
        """
        self.session_info = {
            "session_id": session_id,
            "model": model,
            "num_workers": num_workers,
            "base_branch": base_branch
        }

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")

        table.add_row("Session:", session_id)
        table.add_row("Model:", model)
        table.add_row("Workers:", str(num_workers))
        table.add_row("Branch:", base_branch)
        table.add_row("Started:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        panel = Panel(
            table,
            title="[bold cyan]Flow-Claude Session",
            border_style="cyan",
            box=box.ROUNDED
        )

        self.console.print(panel)
        self.console.print()

    def print_agent_message(
        self,
        agent_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Print formatted agent message with icon and color

        Args:
            agent_type: Type of agent (orchestrator, planner, worker, etc.)
            message: Message to display
            details: Optional additional details (shown in verbose mode)
        """
        icon = self.AGENT_ICONS.get(agent_type.lower(), "🤖")
        color = self.COLORS.get(agent_type.lower(), "white")

        # Format agent name
        agent_name = Text()
        agent_name.append(f"{icon} ", style=color)
        agent_name.append(f"{agent_type.title()}", style=f"bold {color}")
        agent_name.append(": ", style="dim")

        # Add message
        message_text = Text(message, style=color)

        # Combine
        full_text = agent_name + message_text

        self.console.print(full_text)

        # Show details if verbose
        if self.verbose and details:
            self._print_details(details)

    def print_tool_use(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
        agent_type: str = "system"
    ):
        """
        Print tool usage information

        Args:
            tool_name: Name of tool being used
            tool_input: Tool input parameters (shown in debug mode)
            agent_type: Agent using the tool
        """
        if not self.verbose:
            return

        import sys
        icon = "[TOOL]" if sys.platform == 'win32' else "🔧"
        color = self.COLORS.get(agent_type.lower(), "magenta")

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append("Tool: ", style="dim")
        text.append(tool_name, style=f"bold {color}")

        self.console.print(text)

        # Show input in debug mode
        if self.debug and tool_input:
            self.console.print(
                Panel(
                    Syntax(str(tool_input), "json", theme="monokai", word_wrap=True),
                    title="[dim]Tool Input",
                    border_style="dim",
                    box=box.MINIMAL
                )
            )

    def print_tool_result(
        self,
        tool_name: str,
        success: bool = True,
        message: Optional[str] = None,
        result: Optional[Any] = None
    ):
        """
        Print tool execution result

        Args:
            tool_name: Name of tool that executed
            success: Whether tool succeeded
            message: Optional status message
            result: Tool result (shown in debug mode)
        """
        if not self.verbose:
            return

        import sys
        if sys.platform == 'win32':
            icon = "[OK]" if success else "[ERR]"
        else:
            icon = "✓" if success else "✗"
        color = "green" if success else "red"

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(f"{tool_name}", style=f"dim {color}")

        if message:
            text.append(f" - {message}", style="dim")

        self.console.print(text)

        # Show result in debug mode
        if self.debug and result:
            self.console.print(
                Panel(
                    str(result)[:500] + ("..." if len(str(result)) > 500 else ""),
                    title="[dim]Tool Result",
                    border_style="dim",
                    box=box.MINIMAL
                )
            )

    def print_error(self, message: str, details: Optional[str] = None):
        """
        Print error message

        Args:
            message: Error message
            details: Optional error details
        """
        import sys
        prefix = "[ERROR] " if sys.platform == 'win32' else "❌ Error: "

        text = Text()
        text.append(prefix, style="bold red")
        text.append(message, style="red")

        self.console.print(text)

        if details:
            self.console.print(
                Panel(
                    details,
                    title="[red]Error Details",
                    border_style="red",
                    box=box.ROUNDED
                )
            )

    def print_warning(self, message: str):
        """
        Print warning message

        Args:
            message: Warning message
        """
        import sys
        prefix = "[WARNING] " if sys.platform == 'win32' else "⚠️  Warning: "

        text = Text()
        text.append(prefix, style="bold yellow")
        text.append(message, style="yellow")

        self.console.print(text)

    def print_success(self, message: str):
        """
        Print success message

        Args:
            message: Success message
        """
        import sys
        prefix = "[OK] " if sys.platform == 'win32' else "✓ "

        text = Text()
        text.append(prefix, style="bold green")
        text.append(message, style="green")

        self.console.print(text)

    def print_info(self, message: str):
        """
        Print informational message

        Args:
            message: Info message
        """
        import sys
        prefix = "[INFO] " if sys.platform == 'win32' else "ℹ️  "

        text = Text()
        text.append(prefix, style="cyan")
        text.append(message, style="cyan")

        self.console.print(text)

    def print_user_message(self, message: str, is_followup: bool = False):
        """
        Print user input message

        Args:
            message: User's message
            is_followup: Whether this is a follow-up request
        """
        import sys
        if sys.platform == 'win32':
            prefix = "[FOLLOWUP] " if is_followup else "[REQUEST] "
        else:
            prefix = "📝 Follow-up: " if is_followup else "💬 Request: "

        text = Text()
        text.append(prefix, style="bold white")
        text.append(message, style="white")

        self.console.print(text)
        self.console.print()

    def update_status(self, status: str):
        """
        Update current status message

        Args:
            status: New status message
        """
        self.current_status = status

        # Print status bar
        self.console.print(
            Panel(
                Text(status, style="bold cyan"),
                border_style="cyan",
                box=box.SIMPLE,
                padding=(0, 2)
            )
        )

    def show_input_prompt(self, is_initial: bool = True):
        """
        Display input prompt with instructions

        Args:
            is_initial: Whether this is the initial request prompt
        """
        import sys
        if is_initial:
            prompt_text = Text()
            if sys.platform == 'win32':
                prompt_text.append("Enter your development request", style="bold cyan")
            else:
                prompt_text.append("💭 Enter your development request", style="bold cyan")
            prompt_text.append("\n   (or ", style="dim")
            prompt_text.append("\\q", style="bold")
            prompt_text.append(" to quit)", style="dim")

            self.console.print()
            self.console.print(
                Panel(
                    prompt_text,
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2)
                )
            )
        else:
            # During session - show inline prompt
            prompt_text = Text()
            if sys.platform != 'win32':
                prompt_text.append("💡 ", style="cyan")
            prompt_text.append("Press ", style="dim")
            prompt_text.append("ESC", style="bold yellow")
            prompt_text.append(" to interrupt | Type for follow-up | ", style="dim")
            prompt_text.append("\\q", style="bold")
            prompt_text.append(" to quit", style="dim")

            self.console.print(prompt_text)

    def show_separator(self, char: str = "─", style: str = "dim"):
        """
        Show a separator line

        Args:
            char: Character to use for separator
            style: Rich style for the separator
        """
        import sys
        # Use safe ASCII character on Windows
        if sys.platform == 'win32':
            char = "-"

        width = self.console.width
        self.console.print(char * width, style=style)

    def clear(self):
        """Clear the console"""
        self.console.clear()

    def _print_details(self, details: Dict[str, Any]):
        """
        Print additional details in a formatted way

        Args:
            details: Details dictionary
        """
        for key, value in details.items():
            self.console.print(f"  {key}: {value}", style="dim")
