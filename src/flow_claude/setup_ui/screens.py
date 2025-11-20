"""Textual UI screens for Flow-Claude setup.

Contains BranchSelectionScreen and ClaudeMdPromptScreen.
"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from . import claude_generator, git_utils


class BranchSelectionScreen(Screen):
    """Screen for selecting base branch to create flow branch."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("escape", "app.pop_screen", "Cancel", show=False),
    ]

    def __init__(self, branches: list[str], current_branch: Optional[str] = None):
        super().__init__()
        self.branches = branches
        self.current_branch = current_branch
        self.selected_branch = None
        # Map sanitized IDs to original branch names (handles branches with /)
        self.id_to_branch = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("[bold cyan]Flow Branch Setup[/bold cyan]"),
            Label(""),
            Label("Flow-Claude uses a dedicated 'flow' branch for development work."),
            Label("This keeps your work isolated until you're ready to merge."),
            Label(""),
            Label("[bold]Select base branch for flow branch:[/bold]"),
            Label(""),
        )

        # Create ListView (will populate in on_mount)
        list_view = ListView(id="branch-list")
        list_view.border_title = "Available Branches"

        yield VerticalScroll(list_view)
        yield Footer()

    def on_mount(self) -> None:
        """Populate ListView after it's mounted."""
        list_view = self.query_one("#branch-list", ListView)

        for idx, branch in enumerate(self.branches):
            # Sanitize branch name for ID (branch names can contain /)
            safe_id = f"branch-{idx}"
            self.id_to_branch[safe_id] = branch

            if branch == self.current_branch:
                label = f"{branch} [dim](current)[/dim]"
            else:
                label = branch
            list_view.append(ListItem(Label(label), id=safe_id))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle branch selection."""
        item_id = event.item.id
        if item_id and item_id in self.id_to_branch:
            branch_name = self.id_to_branch[item_id]
            self.selected_branch = branch_name
            # Dismiss screen (not exit app) so callback can run
            self.dismiss(result={"flow_branch_created": True, "base_branch": branch_name})


class ClaudeMdPromptScreen(Screen):
    """Screen for prompting CLAUDE.md generation."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.generation_complete = False
        self.generation_result = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("[bold cyan]CLAUDE.md Initialization[/bold cyan]", id="title-label"),
            Label("", id="line1"),
            Label("Flow-Claude will add workflow instructions to CLAUDE.md.", id="line2"),
            Label("This helps Claude Code understand how to use Flow-Claude.", id="line3"),
            Label("", id="line4"),
            Label("[bold]Initialize CLAUDE.md for Flow-Claude?[/bold]", id="question-label"),
            Label("", id="line5"),
        )

        # Create ListView (will populate in on_mount)
        list_view = ListView(id="claude-md-list")
        list_view.border_title = "Select Option"

        yield VerticalScroll(list_view)
        yield Footer()

    def on_mount(self) -> None:
        """Populate ListView after it's mounted."""
        list_view = self.query_one("#claude-md-list", ListView)
        list_view.append(ListItem(Label("Yes, initialize CLAUDE.md"), id="option-yes"))
        list_view.append(ListItem(Label("No, skip"), id="option-no"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle option selection."""
        item_id = event.item.id
        if item_id == "option-yes":
            # Start generation in background worker
            self.start_generation()
        elif item_id == "option-no":
            # Skip generation, dismiss immediately
            self.dismiss(result={"generate_claude_md": False})

    def start_generation(self) -> None:
        """Show progress UI and start background update/creation."""
        # Update UI to show progress immediately
        list_view = self.query_one("#claude-md-list", ListView)
        list_view.display = False  # Hide the list

        # Update labels to show progress
        self.query_one("#title-label", Label).update("[bold cyan]Initializing CLAUDE.md...[/bold cyan]")
        self.query_one("#line1", Label).update("")
        self.query_one("#line2", Label).update("[yellow]Updating CLAUDE.md...[/yellow]")
        self.query_one("#line3", Label).update("[dim]Adding Flow-Claude instructions...[/dim]")
        self.query_one("#question-label", Label).update("")
        self.query_one("#line4", Label).update("")
        self.query_one("#line5", Label).update("")

        # Start background worker
        self.generate_and_commit()

    def on_key(self, event) -> None:
        """Handle any key press after generation completes."""
        if self.generation_complete:
            # User pressed a key, dismiss immediately
            self.dismiss(result=self.generation_result)

    def generate_and_commit(self) -> None:
        """Generate CLAUDE.md and commit to flow branch in background thread."""
        # Run in thread to keep UI responsive
        self.run_worker(self._do_generation, thread=True)

    def _do_generation(self) -> None:
        """Worker function that runs in background thread."""
        cwd = Path.cwd()

        # Update/create CLAUDE.md (runs in background thread)
        success, status, error = claude_generator.update_claude_md(cwd)

        if success:
            if status == "created":
                self.app.call_from_thread(
                    self.query_one("#line2", Label).update, "[green]✓ CLAUDE.md created[/green]"
                )
            elif status == "updated":
                self.app.call_from_thread(
                    self.query_one("#line2", Label).update, "[green]✓ CLAUDE.md updated (instruction prepended)[/green]"
                )
            elif status == "unchanged":
                self.app.call_from_thread(
                    self.query_one("#line2", Label).update, "[green]✓ CLAUDE.md already has Flow-Claude instruction[/green]"
                )

            self.app.call_from_thread(
                self.query_one("#line3", Label).update, "[yellow]Committing to flow branch...[/yellow]"
            )

            # Commit to flow branch (runs in background thread)
            commit_message = f'Initialize CLAUDE.md for Flow-Claude ({status})'
            commit_success, commit_error = git_utils.commit_to_flow_branch('CLAUDE.md', commit_message)

            if commit_success:
                self.app.call_from_thread(
                    self.query_one("#line3", Label).update, "[green]✓ Committed to flow branch[/green]"
                )
                self.app.call_from_thread(
                    self.query_one("#line4", Label).update, ""
                )
                self.app.call_from_thread(
                    self.query_one("#question-label", Label).update,
                    "[green][bold]Success![/bold] Press any key to continue...[/green]"
                )

                # Mark generation as complete so key handler works
                self.generation_complete = True
                self.generation_result = {"generate_claude_md": True}
            else:
                self.app.call_from_thread(
                    self.query_one("#line3", Label).update,
                    f"[yellow]Warning: Could not commit to flow branch[/yellow]"
                )
                self.app.call_from_thread(
                    self.query_one("#line4", Label).update,
                    f"[dim]{commit_error}[/dim]"
                )
                self.app.call_from_thread(
                    self.query_one("#question-label", Label).update,
                    "[yellow]CLAUDE.md updated but not committed. Press any key to continue...[/yellow]"
                )
                self.generation_complete = True
                self.generation_result = {"generate_claude_md": True}
        else:
            self.app.call_from_thread(
                self.query_one("#line2", Label).update, f"[red]Error: {error}[/red]"
            )
            self.app.call_from_thread(
                self.query_one("#line3", Label).update, ""
            )
            self.app.call_from_thread(
                self.query_one("#line4", Label).update, ""
            )
            self.app.call_from_thread(
                self.query_one("#question-label", Label).update,
                "[red]Failed to update CLAUDE.md. Press any key to continue...[/red]"
            )
            self.generation_complete = True
            self.generation_result = {"generate_claude_md": False}
