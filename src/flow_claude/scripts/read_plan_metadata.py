#!/usr/bin/env python3
"""Read execution plan from the latest commit on a plan branch."""
import argparse
import asyncio
import json
import subprocess
import sys


async def read_plan_metadata(branch: str) -> dict:
    """Read execution plan from latest commit on plan branch.

    Args:
        branch: Plan branch name (e.g., 'plan/build-conference-website')

    Returns:
        Dict with commit message
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
            "error": f"Failed to read plan: {str(e)}",
            "branch": branch
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Read execution plan commit message from git branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Read plan commit message
  python -m flow_claude.scripts.read_plan_metadata \\
    --branch="plan/build-conference-website"

Output:
  JSON with commit message that Claude can read directly
        '''
    )
    parser.add_argument(
        '--branch',
        type=str,
        required=True,
        metavar='BRANCH',
        help='Plan branch name (e.g., "plan/build-conference-website")'
    )

    args = parser.parse_args()

    # Run async function
    result = asyncio.run(read_plan_metadata(args.branch))

    # Output JSON
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
