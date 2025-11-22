#!/usr/bin/env python3
"""Read the latest commit message from any git branch."""
import argparse
import asyncio
import json
import subprocess
import sys


async def parse_branch_latest_commit(branch: str) -> dict:
    """Read the latest commit on a git branch.

    Args:
        branch: Branch name (e.g., task/001-xxx, plan/xxx, or any branch)

    Returns:
        Dict with commit message
    """
    try:
        # Get latest commit message
        result = subprocess.run(
            ['git', 'log', branch, '--format=%B', '-n', '1'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
            timeout=10
        )

        commit_message = result.stdout.strip()

        if not commit_message:
            return {
                "success": False,
                "error": f"No commits found on branch {branch}",
                "branch": branch
            }

        return {
            "success": True,
            "branch": branch,
            "message": commit_message
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Git command failed: {e.stderr}",
            "branch": branch
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read branch commit: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Read the latest commit message from any git branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Check worker progress on task branch
  python -m flow_claude.scripts.parse_branch_latest_commit \\
    --branch="task/001-create-html-structure"

  # Check plan branch latest update
  python -m flow_claude.scripts.parse_branch_latest_commit \\
    --branch="plan/build-conference-website"

Output:
  JSON with the latest commit message from the specified branch
        '''
    )
    parser.add_argument(
        '--branch',
        type=str,
        required=True,
        metavar='BRANCH',
        help='Branch name (e.g., "task/001-xxx", "plan/xxx", or any git branch)'
    )

    args = parser.parse_args()

    result = asyncio.run(parse_branch_latest_commit(args.branch))
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
