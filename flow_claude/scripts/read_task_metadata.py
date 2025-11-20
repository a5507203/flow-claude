#!/usr/bin/env python3
"""Read task metadata from the first commit on a task branch."""
import argparse
import asyncio
import json
import subprocess
import sys


async def read_task_metadata(branch: str) -> dict:
    """Read task metadata from first commit on task branch.

    Args:
        branch: Task branch name (e.g., 'task/001-create-html-structure')

    Returns:
        Dict with commit message
    """
    try:
        # Get first commit message on branch
        result = subprocess.run(
            ['git', 'log', branch, '--reverse', '--format=%B', '-n', '1'],
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
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Git command timed out for branch {branch}",
            "branch": branch
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read task: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Read task metadata commit message from git branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Read task metadata
  python -m flow_claude.scripts.read_task_metadata \\
    --branch="task/001-create-html-structure"

Output:
  JSON with commit message that Claude can read directly
        '''
    )
    parser.add_argument(
        '--branch',
        type=str,
        required=True,
        metavar='BRANCH',
        help='Task branch name (e.g., "task/001-create-html-structure")'
    )

    args = parser.parse_args()

    # Run async function
    result = asyncio.run(read_task_metadata(args.branch))

    # Output JSON
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
