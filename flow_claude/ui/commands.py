"""Slash command handlers for Flow-Claude UI."""

import asyncio
from pathlib import Path
from typing import Optional


class CommandHandler:
    """Handles slash commands for Flow-Claude."""

    # Slash commands and their descriptions
    SLASH_COMMANDS = {
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

    def __init__(self, app):
        """Initialize command handler.

        Args:
            app: The FlowCLI app instance
        """
        self.app = app

    async def handle_command(self, command: str) -> bool:
        """Handle slash commands. Returns True if handled."""
        cmd_parts = command.strip().split()
        cmd = cmd_parts[0].lower()

        if cmd in ['/exit', '/q']:
            self.app.exit()
            return True
        elif cmd == '/help':
            self._show_help()
            return True
        elif cmd == '/verbose':
            self._toggle_verbose()
            return True
        elif cmd == '/debug':
            self._toggle_debug()
            return True
        elif cmd == '/auto':
            self._toggle_auto()
            return True
        elif cmd == '/parallel':
            await self._set_parallel(cmd_parts)
            return True
        elif cmd == '/model':
            self._set_model(cmd_parts)
            return True
        elif cmd == '/init':
            self._generate_claude_md()
            return True
        return False

    def _toggle_verbose(self) -> None:
        """Toggle verbose mode."""
        self.app.verbose_mode = not self.app.verbose_mode
        self.app._log(f"[green]✓ Verbose mode: {'ON' if self.app.verbose_mode else 'OFF'}[/green]")
        self.app._show_current_settings()

    def _toggle_debug(self) -> None:
        """Toggle debug mode."""
        self.app.debug_mode = not self.app.debug_mode
        self.app._log(f"[green]✓ Debug mode: {'ON' if self.app.debug_mode else 'OFF'}[/green]")
        self.app._show_current_settings()

    def _toggle_auto(self) -> None:
        """Toggle autonomous mode."""
        self.app.auto_mode = not self.app.auto_mode
        self.app._log(f"[green]✓ Autonomous mode: {'ON' if self.app.auto_mode else 'OFF'}[/green]")
        self.app._show_current_settings()

    async def _set_parallel(self, cmd_parts: list) -> None:
        """Set max parallel workers."""
        if len(cmd_parts) > 1 and cmd_parts[1].isdigit():
            new_value = int(cmd_parts[1])
            if 1 <= new_value <= 10:
                old_value = self.app.max_parallel
                self.app.max_parallel = new_value

                # Update SDK worker manager
                from flow_claude.sdk_workers import get_sdk_worker_manager
                manager = get_sdk_worker_manager()
                if hasattr(manager, 'update_max_parallel'):
                    manager.update_max_parallel(new_value)

                self.app._log(f"[green]✓ Max parallel workers set to {self.app.max_parallel}[/green]")

                # Notify orchestrator if session is active
                if self.app.control_queue and self.app.orchestrator_task and not self.app._awaiting_initial_request:
                    await self.app.control_queue.put({
                        "type": "intervention",
                        "data": {
                            "requirement": f"[CONFIG UPDATE] User changed max_parallel from {old_value} to {new_value}. You now have {new_value} worker slots available (worker-1 through worker-{new_value}). Check current worker status with mcp__git__get_worker_status() and adjust your task scheduling accordingly."
                        }
                    })
                    self.app._log(f"[dim]→ Notified orchestrator about max_parallel change[/dim]")

                self.app._show_current_settings()
            else:
                self.app._log(f"[yellow]Invalid value. Must be between 1 and 10.[/yellow]")
        else:
            self.app._log(f"[yellow]Usage: /parallel <number> (current: {self.app.max_parallel})[/yellow]")

    def _set_model(self, cmd_parts: list) -> None:
        """Select Claude model."""
        if len(cmd_parts) > 1:
            new_model = cmd_parts[1].lower()
            if new_model in ['sonnet', 'opus', 'haiku']:
                self.app.model = new_model
                self.app._log(f"[green]✓ Model set to {self.app.model}[/green]")
                self.app._log(f"[yellow]Note: Model change will apply to next session[/yellow]")
                self.app._show_current_settings()
            else:
                self.app._log(f"[yellow]Invalid model. Choose: sonnet, opus, haiku[/yellow]")
        else:
            self.app._log(f"[yellow]Usage: /model <name> (current: {self.app.model})[/yellow]")
            self.app._log(f"[dim]Available: sonnet, opus, haiku[/dim]")

    def _generate_claude_md(self) -> None:
        """Generate CLAUDE.md with Claude Code (or template fallback)."""
        self.app._log("[dim]Generating CLAUDE.md...[/dim]")
        self.app.run_worker(self._generate_claude_md_worker, thread=True)

    def _generate_claude_md_worker(self) -> None:
        """Worker function to generate CLAUDE.md in background thread."""
        from flow_claude.setup_ui import claude_generator

        try:
            # Check if Claude Code is available
            if claude_generator.check_claude_code_available():
                self.app.call_from_thread(
                    self.app._log, "[yellow]Analyzing project with Claude Code...[/yellow]"
                )
                self.app.call_from_thread(
                    self.app._log, "[dim]This may take up to 3 minutes...[/dim]"
                )
            else:
                self.app.call_from_thread(
                    self.app._log, "[yellow]Claude Code not found, using template...[/yellow]"
                )

            # Generate (tries Claude Code first, falls back to template)
            success, method, error = claude_generator.generate_claude_md(Path.cwd())

            if success:
                if method == "claude_code":
                    self.app.call_from_thread(
                        self.app._log, "[green]✓ CLAUDE.md generated with AI[/green]"
                    )
                else:
                    self.app.call_from_thread(
                        self.app._log, "[green]✓ CLAUDE.md created from template[/green]"
                    )
            else:
                self.app.call_from_thread(
                    self.app._log, f"[red]Error: {error}[/red]"
                )

        except Exception as e:
            self.app.call_from_thread(
                self.app._log, f"[red]Error generating CLAUDE.md: {e}[/red]"
            )

    def _show_help(self) -> None:
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
        self.app._log(help_text)

    def get_matching_commands(self, partial_command: str) -> list:
        """Get slash commands matching the partial input.

        Args:
            partial_command: Partial command typed by user (e.g., "/par")

        Returns:
            List of formatted matching commands with descriptions
        """
        matches = []
        for cmd, desc in self.SLASH_COMMANDS.items():
            if cmd.startswith(partial_command.lower()) or cmd.startswith(partial_command):
                matches.append(f"[cyan]{cmd}[/cyan] - {desc}")
        return matches
