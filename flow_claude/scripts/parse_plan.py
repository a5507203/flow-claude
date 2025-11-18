#!/usr/bin/env python3
"""Parse execution plan from the latest commit on a plan branch."""
import argparse
import asyncio
import json
import subprocess
import sys

try:
    from .parsers import parse_plan_commit
except ImportError:
    from parsers import parse_plan_commit


async def parse_plan(branch: str) -> dict:
    """Parse execution plan from latest commit on plan branch.

    Args:
        branch: Plan branch name (e.g., 'plan/session-20250118-120000')

    Returns:
        Dict with plan metadata
    """
    try:
        # Get latest commit message on plan branch
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
        plan_data = parse_plan_commit(commit_message)

        return {
            "success": True,
            "branch": branch,
            **plan_data
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
            "error": f"Failed to parse plan: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Parse execution plan from git branch'
    )
    parser.add_argument(
        '--branch',
        required=True,
        help='Plan branch name (e.g., plan/session-20250118-120000)'
    )

    args = parser.parse_args()

    # Run async function
    result = asyncio.run(parse_plan(args.branch))

    # Output JSON
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
