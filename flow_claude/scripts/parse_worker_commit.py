#!/usr/bin/env python3
"""Parse worker's latest commit with design and TODO progress."""
import argparse
import asyncio
import json
import subprocess
import sys

try:
    from .parsers import parse_worker_commit
except ImportError:
    from parsers import parse_worker_commit


async def parse_worker_commit_script(branch: str) -> dict:
    """Parse the latest commit on a worker's task branch.

    Args:
        branch: Task branch name

    Returns:
        Dict with worker progress (design, todo, status)
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
                "error": f"No commits found on branch {branch}",
                "branch": branch
            }

        # Parse using shared parser
        progress = parse_worker_commit(commit_message)

        return {
            "success": True,
            "branch": branch,
            **progress
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr}",
            "branch": branch
        }
    except Exception as e:
        return {
            "error": f"Failed to parse worker commit: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Parse worker progress from git commit'
    )
    parser.add_argument('--branch', required=True, help='Task branch name')

    args = parser.parse_args()

    result = asyncio.run(parse_worker_commit_script(args.branch))
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
