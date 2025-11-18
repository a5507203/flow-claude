#!/usr/bin/env python3
"""Update plan commit with completed tasks and new tasks."""
import argparse
import asyncio
import json
import subprocess
import sys


async def update_plan_branch(
    plan_branch: str,
    completed_tasks: list,
    new_tasks: list,
    plan_version: str
) -> dict:
    """Update plan with new wave of tasks.

    Args:
        plan_branch: Plan branch to update
        completed_tasks: List of completed task IDs
        new_tasks: List of new task definitions
        plan_version: New version number

    Returns:
        Dict with success status
    """
    try:
        # Checkout plan branch
        subprocess.run(
            ['git', 'checkout', plan_branch],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Build commit message
        commit_lines = [
            f"Update execution plan {plan_version}",
            "",
            "## Completed Tasks",
        ]

        for task_id in completed_tasks:
            commit_lines.append(f"- Task {task_id}: ✓ Complete")

        commit_lines.extend([
            "",
            "## New Wave Tasks",
        ])

        for task in new_tasks:
            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Description: {task['description']}",
                ""
            ])

        commit_message = '\n'.join(commit_lines)

        # Create commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            check=True,
            capture_output=True,
            timeout=10
        )

        return {
            "success": True,
            "plan_branch": plan_branch,
            "version": plan_version,
            "completed_count": len(completed_tasks),
            "new_tasks_count": len(new_tasks)
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
            "success": False
        }
    except Exception as e:
        return {
            "error": f"Failed to update plan: {str(e)}",
            "success": False
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Update plan branch')
    parser.add_argument('--plan-branch', required=True)
    parser.add_argument('--completed', required=True, help='JSON array of completed task IDs')
    parser.add_argument('--new-tasks', required=True, help='JSON array of new tasks')
    parser.add_argument('--version', required=True)

    args = parser.parse_args()

    try:
        completed = json.loads(args.completed)
        new_tasks = json.loads(args.new_tasks)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    result = asyncio.run(update_plan_branch(
        plan_branch=args.plan_branch,
        completed_tasks=completed,
        new_tasks=new_tasks,
        plan_version=args.version
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
