"""Git utilities for Flow-Claude setup.

Handles git operations for flow branch and CLAUDE.md management.
"""

import subprocess
from pathlib import Path
from typing import Optional


def check_flow_branch_exists() -> bool:
    """Check if flow branch exists in the repository.

    Returns:
        bool: True if flow branch exists, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', 'flow'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_branches() -> tuple[list[str], Optional[str]]:
    """Get list of branches and current branch.

    Returns:
        tuple: (list of branch names, current branch name or None)
    """
    try:
        # Get all branches
        branches_result = subprocess.run(
            ['git', 'branch', '--format=%(refname:short)'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
            timeout=5
        )
        branches = [b.strip() for b in branches_result.stdout.strip().split('\n') if b.strip()]

        # Get current branch
        current_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=5
        )
        current_branch = current_result.stdout.strip() or None

        return branches, current_branch
    except Exception:
        return [], None


def create_flow_branch(base_branch: str) -> bool:
    """Create flow branch from base branch.

    Args:
        base_branch: Name of the base branch to create from

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            ['git', 'branch', 'flow', base_branch],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def create_main_branch() -> bool:
    """Create main branch if no branches exist.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            ['git', 'checkout', '-b', 'main'],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def check_claude_md_in_flow_branch() -> bool:
    """Check if CLAUDE.md exists in flow branch.

    Returns:
        bool: True if CLAUDE.md exists in flow branch, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'show', 'flow:CLAUDE.md'],
            capture_output=True,
            timeout=5
        )
        # Exit code 0 = file exists
        # Exit code 128 = file doesn't exist
        return result.returncode == 0
    except Exception:
        return False


def commit_to_flow_branch(file_path: str, commit_message: str) -> tuple[bool, str]:
    """Commit file to flow branch and stay on flow branch.

    Args:
        file_path: Path to file to commit (relative to repo root)
        commit_message: Commit message

    Returns:
        tuple: (success: bool, error_message: str)
    """
    try:
        # Checkout flow branch
        subprocess.run(
            ['git', 'checkout', 'flow'],
            capture_output=True,
            check=True,
            timeout=5
        )

        # Add file
        subprocess.run(
            ['git', 'add', file_path],
            capture_output=True,
            check=True,
            timeout=5
        )

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', commit_message],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Stay on flow branch (do not switch back)

        return True, ""

    except subprocess.CalledProcessError as e:
        return False, f"Git command failed: {e}"
    except Exception as e:
        return False, str(e)
