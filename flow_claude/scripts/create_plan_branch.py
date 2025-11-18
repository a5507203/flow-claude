#!/usr/bin/env python3
"""Create plan branch with metadata commit."""
import argparse
import asyncio
import json
import subprocess
import sys


async def create_plan_branch(
    session_id: str,
    user_request: str,
    architecture: str,
    tasks: list,
    **kwargs
) -> dict:
    """Create plan branch with structured metadata commit.

    Args:
        session_id: Unique session ID
        user_request: Original user request
        architecture: Architecture description
        tasks: List of task definitions
        **kwargs: Additional fields (design_patterns, tech_stack, waves, etc.)

    Returns:
        Dict with success status
    """
    try:
        branch_name = f"plan/{session_id}"

        # Create branch from flow
        subprocess.run(
            ['git', 'checkout', '-b', branch_name, 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Build commit message
        commit_lines = [
            f"Initialize execution plan v1",
            "",
            "## Session Information",
            f"Session ID: {session_id}",
            f"User Request: {user_request}",
            "Plan Version: v1",
            "",
            "## Architecture",
            architecture,
            ""
        ]

        # Add optional sections
        if kwargs.get('design_patterns'):
            commit_lines.extend([
                "## Design Patterns",
                kwargs['design_patterns'],
                ""
            ])

        if kwargs.get('technology_stack'):
            commit_lines.extend([
                "## Technology Stack",
                kwargs['technology_stack'],
                ""
            ])

        # Add tasks
        commit_lines.append("## Tasks")
        for task in tasks:
            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Description: {task['description']}",
                f"Priority: {task.get('priority', 'medium')}",
                f"Estimated Time: {task.get('estimated_time', 'N/A')}",
                ""
            ])

        # Add waves if provided
        if kwargs.get('waves'):
            commit_lines.append("## Dependency Graph")
            for wave in kwargs['waves']:
                wave_num = wave['wave']
                task_ids = ', '.join(wave['tasks'])
                commit_lines.append(f"Wave {wave_num}: [{task_ids}]")

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
            "session_id": session_id
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
            "success": False
        }
    except Exception as e:
        return {
            "error": f"Failed to create plan branch: {str(e)}",
            "success": False
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Create plan branch with metadata'
    )
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--user-request', required=True)
    parser.add_argument('--architecture', required=True)
    parser.add_argument('--tasks', required=True, help='JSON array of tasks')
    parser.add_argument('--design-patterns', default='')
    parser.add_argument('--tech-stack', default='')
    parser.add_argument('--waves', default='', help='JSON array of waves')

    args = parser.parse_args()

    # Parse JSON fields
    try:
        tasks = json.loads(args.tasks)
        waves = json.loads(args.waves) if args.waves else []
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    # Run async function
    result = asyncio.run(create_plan_branch(
        session_id=args.session_id,
        user_request=args.user_request,
        architecture=args.architecture,
        tasks=tasks,
        design_patterns=args.design_patterns,
        technology_stack=args.tech_stack,
        waves=waves
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
