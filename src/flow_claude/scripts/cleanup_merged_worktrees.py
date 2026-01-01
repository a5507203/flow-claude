"""Cleanup worktrees whose branches have been merged.

This utility finds git worktrees with branches that have been merged into
a target branch and removes them automatically.

Usage:
    python -m flow_claude.scripts.cleanup_merged_worktrees
    python -m flow_claude.scripts.cleanup_merged_worktrees --target="flow/session-123"
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional


def cleanup_merged_worktrees(target_branch: str = "HEAD") -> list[str]:
    """Find and remove worktrees whose branches are merged into target.

    Args:
        target_branch: Branch to check merge status against (default: current HEAD)

    Returns:
        List of cleaned up worktree paths
    """
    cleaned = []

    # 1. Get list of merged branches
    merged_branches = _get_merged_branches(target_branch)

    # 2. Get worktrees and their branches
    worktrees = _get_worktrees_with_branches()

    # 3. Cleanup worktrees whose branch is merged
    for worktree_path, branch in worktrees.items():
        if branch in merged_branches:
            if _cleanup_worktree(worktree_path):
                print(f"Cleaned up worktree: {worktree_path} (branch: {branch})")
                cleaned.append(worktree_path)
            else:
                print(f"Failed to cleanup worktree: {worktree_path}")

    return cleaned


def _get_merged_branches(target: str) -> set[str]:
    """Get branches merged into target."""
    result = subprocess.run(
        ['git', 'branch', '--merged', target],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )

    if result.returncode != 0:
        print(f"Warning: Failed to get merged branches: {result.stderr}")
        return set()

    # Parse: "  branch-name" or "* current-branch"
    branches = set()
    for line in result.stdout.splitlines():
        branch = line.strip().lstrip('* ')
        if branch:
            branches.add(branch)
    return branches


def _get_worktrees_with_branches() -> dict[str, str]:
    """Get mapping of worktree path -> branch name.

    Only returns worktrees in .worktrees/ directory (worker worktrees).
    Excludes the main worktree.
    """
    result = subprocess.run(
        ['git', 'worktree', 'list', '--porcelain'],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )

    if result.returncode != 0:
        print(f"Warning: Failed to list worktrees: {result.stderr}")
        return {}

    # Parse porcelain format:
    # worktree /path/to/worktree
    # HEAD abc123def
    # branch refs/heads/branch-name
    # (blank line)
    worktrees = {}
    current_path: Optional[str] = None

    for line in result.stdout.splitlines():
        if line.startswith('worktree '):
            current_path = line[9:]
        elif line.startswith('branch refs/heads/'):
            branch = line[18:]
            if current_path and '.worktrees' in current_path:
                # Only include worker worktrees, not the main worktree
                worktrees[current_path] = branch
            current_path = None

    return worktrees


def _cleanup_worktree(path: str) -> bool:
    """Remove worktree, handling missing directory case."""
    try:
        # Check if directory exists
        if not Path(path).exists():
            # Directory missing - use prune to clean stale metadata
            print(f"Worktree directory missing, pruning stale metadata: {path}")
            result = subprocess.run(
                ['git', 'worktree', 'prune'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path.cwd()
            )
            return result.returncode == 0

        # Directory exists - remove normally
        result = subprocess.run(
            ['git', 'worktree', 'remove', path, '--force'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path.cwd()
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Timeout while removing worktree: {path}")
        return False
    except Exception as e:
        print(f"Error removing worktree {path}: {e}")
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Cleanup worktrees whose branches have been merged'
    )
    parser.add_argument(
        '--target',
        type=str,
        default='HEAD',
        help='Target branch to check merge status against (default: HEAD)'
    )

    args = parser.parse_args()

    print(f"Checking for worktrees with branches merged into {args.target}...")

    cleaned = cleanup_merged_worktrees(args.target)

    if cleaned:
        print(f"\nCleaned up {len(cleaned)} worktree(s)")
    else:
        print("\nNo merged worktrees to cleanup")

    return 0


if __name__ == '__main__':
    sys.exit(main())
