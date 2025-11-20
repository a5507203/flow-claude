#!/usr/bin/env python3
"""Read worker's latest commit with progress information."""
import argparse
import asyncio
import json
import subprocess
import sys


async def parse_worker_commit(branch: str) -> dict:
    """Read the latest commit on a worker's task branch.

    Args:
        branch: Task branch name

    Returns:
        Dict with commit message
    """
    try:
        # Get latest commit message
        result = subprocess.run(
            ['git', 'log', branch, '--format=%B', '-n', '1'],
            capture_output=True,
            text=True,
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
            "error": f"Failed to read worker commit: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Read worker progress commit message from git branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Check worker progress
  python -m flow_claude.scripts.parse_worker_commit \\
    --branch="task/001-create-html-structure"

Output:
  JSON with commit message showing worker's design, TODO list, and progress
        '''
    )
    parser.add_argument(
        '--branch',
        required=True,
        metavar='BRANCH',
        help='Task branch name (e.g., "task/001-create-html-structure")'
    )

    args = parser.parse_args()

    result = asyncio.run(parse_worker_commit(args.branch))
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
