"""SetupUI app for Flow-Claude initialization.

Coordinates flow branch setup and CLAUDE.md generation.
"""

from pathlib import Path

from textual.app import App

from . import git_utils
from .screens import BranchSelectionScreen, ClaudeMdPromptScreen


class SetupUI(App):
    """Textual UI for Flow-Claude setup (flow branch + CLAUDE.md)."""

    CSS = """
    Container {
        height: auto;
        padding: 1 2;
    }

    ListView {
        height: auto;
        max-height: 15;
        border: solid $panel;
        background: $surface;
    }

    Label {
        width: 100%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_results = {
            "flow_branch_created": False,
            "base_branch": None,
            "claude_md_generated": False,
        }

    def on_mount(self) -> None:
        """Run setup checks when app starts."""
        self.run_setup()

    def run_setup(self) -> None:
        """Run setup process: git init (if needed), flow branch, then CLAUDE.md."""
        # Step 0: Check if directory is a git repo
        if not git_utils.check_is_git_repo():
            # Not a git repo - initialize with flow branch
            success, error = git_utils.initialize_git_repo()
            if success:
                self.setup_results["flow_branch_created"] = True
                self.setup_results["base_branch"] = "main"
                # Flow branch already created during init, skip to CLAUDE.md
                self.check_and_prompt_claude_md()
            else:
                # Failed to initialize - exit setup
                # TODO: Show error to user
                self.exit(result=self.setup_results)
            return

        # Step 1: Check if flow branch exists
        if not git_utils.check_flow_branch_exists():
            self.setup_flow_branch()
        else:
            # Flow branch exists - skip to CLAUDE.md check
            self.check_and_prompt_claude_md()

    def setup_flow_branch(self) -> None:
        """Show branch selection screen and create flow branch."""
        branches, current_branch = git_utils.get_branches()

        if not branches:
            # No branches yet - create main and use it
            if git_utils.create_main_branch():
                selected_base = 'main'
                if git_utils.create_flow_branch(selected_base):
                    self.setup_results["flow_branch_created"] = True
                    self.setup_results["base_branch"] = selected_base

            # Continue to CLAUDE.md check
            self.check_and_prompt_claude_md()
        else:
            # Show branch selection screen
            def handle_branch_selection(result):
                if result and result.get("flow_branch_created"):
                    base_branch = result.get("base_branch")
                    if git_utils.create_flow_branch(base_branch):
                        self.setup_results["flow_branch_created"] = True
                        self.setup_results["base_branch"] = base_branch

                # Continue to CLAUDE.md check
                self.check_and_prompt_claude_md()

            screen = BranchSelectionScreen(branches=branches, current_branch=current_branch)
            self.push_screen(screen, callback=handle_branch_selection)

    def check_and_prompt_claude_md(self) -> None:
        """Check if CLAUDE.md exists in flow branch and prompt for generation.

        Always runs, even if flow branch exists. Checks if CLAUDE.md exists
        specifically in the flow branch.
        """
        # Check if CLAUDE.md exists in flow branch
        if git_utils.check_claude_md_in_flow_branch():
            # CLAUDE.md already exists in flow branch - checkout flow and exit
            git_utils.checkout_flow_branch()
            self.exit(result=self.setup_results)
            return

        # Check if directory is empty (only non-hidden files)
        files = [f for f in Path.cwd().iterdir() if not f.name.startswith('.')]
        if not files:
            # Empty directory, skip prompt but checkout flow branch
            git_utils.checkout_flow_branch()
            self.exit(result=self.setup_results)
            return

        # Show CLAUDE.md prompt screen
        def handle_claude_md_selection(result):
            # Screen already handled generation and commit synchronously
            # (which includes checkout to flow branch)
            if result and result.get("generate_claude_md"):
                self.setup_results["claude_md_generated"] = True
            else:
                # User skipped CLAUDE.md, still need to checkout flow
                git_utils.checkout_flow_branch()

            # Exit setup
            self.exit(result=self.setup_results)

        screen = ClaudeMdPromptScreen()
        self.push_screen(screen, callback=handle_claude_md_selection)


def run_setup_ui() -> dict:
    """Run the setup UI and return results.

    Returns:
        dict: Setup results with keys:
            - flow_branch_created: bool
            - base_branch: str or None
            - claude_md_generated: bool
    """
    app = SetupUI()
    result = app.run()
    return result if result else {
        "flow_branch_created": False,
        "base_branch": None,
        "claude_md_generated": False,
    }
