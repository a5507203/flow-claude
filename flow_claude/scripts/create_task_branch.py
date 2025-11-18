#!/usr/bin/env python3
"""Create task branch with metadata commit."""
import argparse
import asyncio
import json
import subprocess
import sys


async def create_task_branch(
    task_id: str,
    description: str,
    session_id: str,
    plan_branch: str,
    **kwargs
) -> dict:
    """Create task branch with metadata commit.

    Args:
        task_id: Task ID (e.g., '001')
        description: Task description
        session_id: Parent session ID
        plan_branch: Parent plan branch name
        **kwargs: preconditions, provides, files, priority, estimated_time, etc.

    Returns:
        Dict with success status
    """
    try:
        branch_name = f"task/{task_id}-{description.lower().replace(' ', '-')[:30]}"

        # Create branch from flow
        subprocess.run(
            ['git', 'checkout', '-b', branch_name, 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Build commit message
        commit_lines = [
            f"Initialize {branch_name}",
            "",
            "## Task Metadata",
            f"ID: {task_id}",
            f"Description: {description}",
            f"Status: pending",
            ""
        ]

        # Dependencies
        preconditions = kwargs.get('preconditions', [])
        provides = kwargs.get('provides', [])
        commit_lines.extend([
            "## Dependencies",
            "Preconditions:",
        ])
        for pre in preconditions:
            commit_lines.append(f"  - {pre}")
        commit_lines.append("Provides:")
        for prov in provides:
            commit_lines.append(f"  - {prov}")
        commit_lines.append("")

        # Files
        files = kwargs.get('files', [])
        commit_lines.append("## Files")
        commit_lines.append("Files to modify:")
        for f in files:
            commit_lines.append(f"  - {f}")
        commit_lines.append("")

        # Context
        commit_lines.extend([
            "## Context",
            f"Session ID: {session_id}",
            f"Plan Branch: {plan_branch}",
            f"Priority: {kwargs.get('priority', 'medium')}",
            f"Estimated Time: {kwargs.get('estimated_time', 'N/A')}",
            ""
        ])

        commit_message = '\n'.join(commit_lines)

        # Create empty commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            check=True,
            capture_output=True,
            timeout=10
        )

        return {
            "success": True,
            "branch": branch_name,
            "task_id": task_id
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
            "success": False
        }
    except Exception as e:
        return {
            "error": f"Failed to create task branch: {str(e)}",
            "success": False
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Create task branch')
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--plan-branch', required=True)
    parser.add_argument('--preconditions', default='[]', help='JSON array')
    parser.add_argument('--provides', default='[]', help='JSON array')
    parser.add_argument('--files', default='[]', help='JSON array')
    parser.add_argument('--priority', default='medium')
    parser.add_argument('--estimated-time', default='N/A')

    args = parser.parse_args()

    # Parse JSON
    try:
        preconditions = json.loads(args.preconditions)
        provides = json.loads(args.provides)
        files = json.loads(args.files)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    result = asyncio.run(create_task_branch(
        task_id=args.task_id,
        description=args.description,
        session_id=args.session_id,
        plan_branch=args.plan_branch,
        preconditions=preconditions,
        provides=provides,
        files=files,
        priority=args.priority,
        estimated_time=args.estimated_time
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
