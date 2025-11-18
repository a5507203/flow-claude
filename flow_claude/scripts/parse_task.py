#!/usr/bin/env python3
"""Parse task metadata from the first commit on a task branch."""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

try:
    from .parsers import parse_task_metadata
except ImportError:
    # Fallback for direct execution
    from parsers import parse_task_metadata


async def parse_task(branch: str) -> dict:
    """Parse task metadata from first commit on task branch.

    Args:
        branch: Task branch name (e.g., 'task/001-description')

    Returns:
        Dict with task metadata
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
                "error": f"No commits found on branch {branch}",
                "branch": branch
            }

        # Parse using shared parser
        metadata = parse_task_metadata(commit_message)

        return {
            "success": True,
            "branch": branch,
            **metadata
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr}",
            "branch": branch
        }
    except subprocess.TimeoutExpired:
        return {
            "error": f"Git command timed out for branch {branch}",
            "branch": branch
        }
    except Exception as e:
        return {
            "error": f"Failed to parse task: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Parse task metadata from git branch'
    )
    parser.add_argument(
        '--branch',
        required=True,
        help='Task branch name (e.g., task/001-description)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'compact'],
        default='json',
        help='Output format (default: json)'
    )

    args = parser.parse_args()

    # Run async function
    result = asyncio.run(parse_task(args.branch))

    # Output
    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        # Compact format for shell scripts
        if result.get('success'):
            print(f"ID={result.get('id', 'N/A')}")
            print(f"DESC={result.get('description', 'N/A')}")
            print(f"STATUS={result.get('status', 'N/A')}")
        else:
            print(f"ERROR={result.get('error', 'Unknown error')}", file=sys.stderr)
            return 1

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
