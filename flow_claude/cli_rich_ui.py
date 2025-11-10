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
import sys


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
        self.console = Console(
            force_terminal=True,
            legacy_windows=True if sys.platform == 'win32' else False
        )
        self.verbose = verbose
        self.debug = debug
        self.current_status = "Initializing..."
        self.session_info = {}
        self.fixed_footer_enabled = False
        self.footer_text = ""

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

        # Check for structured information patterns
        if self._should_highlight_message(message):
            self._print_highlighted_message(agent_type, message, color)
            return

        # Format agent name
        agent_name = Text()
        agent_name.append(f"{icon} ", style=color)
        agent_name.append(f"{agent_type.title()}", style=f"bold {color}")
        agent_name.append(": ", style="dim")

        # Add message
        message_text = Text(message, style=color)

        # Combine
        full_text = agent_name + message_text

        self.print_with_footer(full_text)

        # Show details if verbose
        if self.verbose and details:
            self._print_details(details)

    def _should_highlight_message(self, message: str) -> bool:
        """Check if message contains key information that should be highlighted"""
        keywords = [
            "Creating plan",
            "Created plan",
            "Creating task branch",
            "Created branch",
            "Starting wave",
            "Wave complete",
            "Task complete",
            "Merging",
            "All tasks complete",
            "Plan created",
            "branches created",
        ]
        return any(keyword.lower() in message.lower() for keyword in keywords)

    def _print_highlighted_message(self, agent_type: str, message: str, color: str):
        """Print important messages in a highlighted panel"""
        icon = self.AGENT_ICONS.get(agent_type.lower(), "🤖")

        # Create styled text
        title_text = Text()
        title_text.append(f"{icon} {agent_type.title()}", style=f"bold {color}")

        # Create panel with message
        panel = Panel(
            message,
            title=title_text,
            border_style=color,
            box=box.ROUNDED,
            padding=(0, 2)
        )

        self.print_with_footer(panel)

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
        # Always show git MCP tools (key operations)
        is_git_tool = tool_name.startswith("mcp__git__")

        if not self.verbose and not is_git_tool:
            return

        import sys
        icon = "[TOOL]" if sys.platform == 'win32' else "🔧"
        color = self.COLORS.get(agent_type.lower(), "magenta")

        # For git tools, extract key information
        if is_git_tool and tool_input:
            self._print_git_tool(tool_name, tool_input, agent_type)
            return

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append("Tool: ", style="dim")
        text.append(tool_name, style=f"bold {color}")

        self.print_with_footer(text)

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

        self.print_with_footer(text)

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

        self.print_with_footer(text)

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

        self.print_with_footer(text)

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

        self.print_with_footer(text)

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

        self.print_with_footer(text)

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

        self.print_with_footer(text)
        if not self.fixed_footer_enabled:
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
        if is_initial:
            # Simple, clean prompt without box
            self.console.print("Enter your development request (or \\q to quit):", style="bold cyan")
        else:
            # During session - show inline prompt
            prompt_text = Text()
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

    def enable_fixed_footer(self, footer_text: str):
        """
        Enable fixed footer mode with given text

        Args:
            footer_text: Text to display in the fixed footer
        """
        self.fixed_footer_enabled = True
        self.footer_text = footer_text
        # Print newline first to separate from previous content
        self.console.print()
        self._print_footer()

    def disable_fixed_footer(self):
        """Disable fixed footer mode"""
        if self.fixed_footer_enabled:
            self._clear_footer()
        self.fixed_footer_enabled = False
        self.footer_text = ""

    def update_footer(self, footer_text: str):
        """
        Update the footer text

        Args:
            footer_text: New footer text
        """
        if self.fixed_footer_enabled:
            self._clear_footer()
            self.footer_text = footer_text
            self._print_footer()

    def _clear_footer(self):
        """Clear the current footer line using ANSI escape codes"""
        # Move cursor up one line and clear it
        if self.footer_text:
            # Count number of lines the footer takes
            lines = self.footer_text.count('\n') + 1
            for _ in range(lines):
                # Move cursor up and clear line
                self.console.file.write('\033[1A\033[2K')
            self.console.file.flush()

    def _print_footer(self):
        """Print the footer at the bottom"""
        if self.footer_text:
            self.console.print(self.footer_text, style="dim")

    def print_with_footer(self, *args, **kwargs):
        """
        Print content while maintaining fixed footer

        This clears the footer, prints the content, then reprints the footer
        """
        if self.fixed_footer_enabled:
            self._clear_footer()

        self.console.print(*args, **kwargs)

        if self.fixed_footer_enabled:
            self._print_footer()

    def _print_details(self, details: Dict[str, Any]):
        """
        Print additional details in a formatted way

        Args:
            details: Details dictionary
        """
        for key, value in details.items():
            self.console.print(f"  {key}: {value}", style="dim")

    def print_task_info(self, task_id: str, description: str, status: str = "pending"):
        """
        Print task information in a formatted way

        Args:
            task_id: Task ID
            description: Task description
            status: Task status (pending, in_progress, completed)
        """
        status_colors = {
            "pending": "yellow",
            "in_progress": "cyan",
            "completed": "green",
            "failed": "red"
        }

        import sys
        status_icons = {
            "pending": "[ ]" if sys.platform == 'win32' else "○",
            "in_progress": "[~]" if sys.platform == 'win32' else "◐",
            "completed": "[X]" if sys.platform == 'win32' else "●",
            "failed": "[!]" if sys.platform == 'win32' else "✗"
        }

        color = status_colors.get(status, "white")
        icon = status_icons.get(status, "?")

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(f"Task {task_id}", style=f"bold {color}")
        text.append(f": {description}", style="white")

        self.console.print(text)

    def print_wave_info(self, wave_num: int, task_ids: list):
        """
        Print wave execution information

        Args:
            wave_num: Wave number
            task_ids: List of task IDs in this wave
        """
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Info", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Wave", f"{wave_num}")
        table.add_row("Tasks", ", ".join(task_ids))
        table.add_row("Execution", "Parallel" if len(task_ids) > 1 else "Sequential")

        panel = Panel(
            table,
            title=f"[bold cyan]Wave {wave_num} Execution",
            border_style="cyan",
            box=box.ROUNDED
        )

        self.console.print(panel)

    def print_git_operation(self, operation: str, branch_name: str, details: str = ""):
        """
        Print git operation information

        Args:
            operation: Git operation (create, merge, checkout, etc.)
            branch_name: Branch name
            details: Additional details
        """
        import sys
        icon = "[GIT]" if sys.platform == 'win32' else "⎇"

        text = Text()
        text.append(f"{icon} ", style="magenta")
        text.append(f"{operation.title()}: ", style="bold magenta")
        text.append(branch_name, style="bold white")

        if details:
            text.append(f" - {details}", style="dim")

        self.console.print(text)

    def print_progress_summary(self, completed: int, total: int, current_task: str = ""):
        """
        Print overall progress summary

        Args:
            completed: Number of completed tasks
            total: Total number of tasks
            current_task: Current task description
        """
        progress_pct = (completed / total * 100) if total > 0 else 0

        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Progress", f"{completed}/{total} ({progress_pct:.0f}%)")
        if current_task:
            table.add_row("Current", current_task)

        self.console.print(table)
        self.console.print()

    def _print_git_tool(self, tool_name: str, tool_input: Dict[str, Any], agent_type: str):
        """
        Print git MCP tool usage with formatted key information

        Args:
            tool_name: Git tool name (e.g., mcp__git__create_task_branch)
            tool_input: Tool input parameters
            agent_type: Agent using the tool
        """
        import sys
        icon = "[GIT]" if sys.platform == 'win32' else "⎇"
        color = self.COLORS.get(agent_type.lower(), "magenta")

        # Extract operation type from tool name
        operation = tool_name.replace("mcp__git__", "").replace("_", " ").title()

        text = Text()
        text.append(f"{icon} ", style="magenta")
        text.append(f"{operation}", style="bold magenta")

        # Add key details based on tool type
        if "create_plan_branch" in tool_name:
            session_id = tool_input.get("session_id", "")
            text.append(f" - {session_id}", style="white")

        elif "create_task_branch" in tool_name:
            task_id = tool_input.get("task_id", "")
            description = tool_input.get("description", "")
            text.append(f" - Task {task_id}: {description[:50]}", style="white")

        elif "update_plan_branch" in tool_name:
            wave_num = tool_input.get("wave_num", "")
            text.append(f" - Wave {wave_num}", style="white")

        elif "parse" in tool_name.lower():
            # Don't show parse operations (too noisy)
            if not self.debug:
                return
            text.append(" (reading metadata)", style="dim")

        self.console.print(text)
