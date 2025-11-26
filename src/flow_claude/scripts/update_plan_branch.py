#!/usr/bin/env python3
"""Update plan branch with complete plan snapshot."""
import argparse
import asyncio
import json
import subprocess
import sys


async def update_plan_branch(
    plan_branch: str,
    user_request: str,
    tasks: list,
    plan_version: str,
    **kwargs
) -> dict:
    """Update plan with complete snapshot of all information.

    Args:
        plan_branch: Plan branch to update
        user_request: Original user request
        tasks: Complete list of ALL tasks (with status)
        plan_version: New version number
        **kwargs: Optional fields:
            - design_doc: Complete design documentation (includes architecture)
            - tech_stack: Technology stack

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

        # Extract session name from branch
        session_name = plan_branch.replace('plan/', '')

        # Build commit message (complete snapshot)
        commit_lines = [
            f"Update execution plan {plan_version}",
            "",
            "## Session Information",
            f"Session name: {session_name}",
            f"User Request: {user_request}",
            f"Plan Version: {plan_version}",
            ""
        ]

        # Add optional sections
        if kwargs.get('design_doc'):
            commit_lines.extend([
                "## Design Doc",
                kwargs['design_doc'],
                ""
            ])

        if kwargs.get('technology_stack'):
            commit_lines.extend([
                "## Technology Stack",
                kwargs['technology_stack'],
                ""
            ])

        # Add all tasks (complete list)
        commit_lines.append("## Tasks")
        for task in tasks:
            depends_on = task.get('depends_on', [])
            key_files = task.get('key_files', [])
            status = task.get('status', 'pending')

            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Description: {task['description']}",
                f"Status: {status}",
                f"Priority: {task.get('priority', 'medium')}",
                f"Depends on: {', '.join(depends_on) if depends_on else 'None'}",
                f"Key files: {', '.join(key_files) if key_files else 'None'}",
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

        # Count task statuses
        completed = sum(1 for t in tasks if t.get('status') == 'completed')
        pending = sum(1 for t in tasks if t.get('status') == 'pending')
        in_progress = sum(1 for t in tasks if t.get('status') == 'in_progress')

        return {
            "success": True,
            "plan_branch": plan_branch,
            "version": plan_version,
            "total_tasks": len(tasks),
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending
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
    parser = argparse.ArgumentParser(
        description='Update plan branch with complete plan snapshot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Update plan with task status changes
  python -m flow_claude.scripts.update_plan_branch \\
    --plan-branch="plan/add-user-authentication" \\
    --user-request="Add user authentication with JWT and bcrypt" \\
    --architecture="Use MVC pattern with Flask backend..." \\
    --design-doc="Complete design documentation..." \\
    --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT" \\
    --tasks='[
      {"id":"001","description":"Create User model","depends_on":[],"key_files":["src/models/user.py"],"priority":"high","status":"completed"},
      {"id":"002","description":"Implement password hashing","depends_on":[],"key_files":["src/utils/auth.py"],"priority":"high","status":"in_progress"},
      {"id":"003","description":"Create JWT tokens","depends_on":[],"key_files":["src/utils/jwt.py"],"priority":"high","status":"pending"},
      {"id":"004","description":"User registration endpoint","depends_on":["001","002"],"key_files":["src/api/auth.py"],"priority":"medium","status":"pending"}
    ]' \\
    --version="v2"

Output:
  JSON with success status and task statistics
        '''
    )
    parser.add_argument(
        '--plan-branch',
        type=str,
        required=True,
        metavar='BRANCH',
        help='Plan branch to update (e.g., "plan/add-user-authentication")'
    )
    parser.add_argument(
        '--user-request',
        type=str,
        required=True,
        metavar='TEXT',
        help='Original user request (unchanged from initial plan)'
    )
    parser.add_argument(
        '--tasks',
        type=str,
        required=True,
        metavar='JSON',
        help='Complete JSON array of ALL tasks with current status. Each task: {id, description, depends_on, key_files, priority, status}'
    )
    parser.add_argument(
        '--version',
        type=str,
        required=True,
        metavar='VERSION',
        help='New plan version (e.g., "v2", "v3")'
    )
    parser.add_argument(
        '--design-doc',
        type=str,
        default='',
        metavar='TEXT',
        help='Complete design documentation (include all updates and architecture)'
    )
    parser.add_argument(
        '--tech-stack',
        type=str,
        default='',
        metavar='TEXT',
        help='Technology stack: languages, frameworks, libraries, tools'
    )

    args = parser.parse_args()

    try:
        tasks = json.loads(args.tasks)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    result = asyncio.run(update_plan_branch(
        plan_branch=args.plan_branch,
        user_request=args.user_request,
        tasks=tasks,
        plan_version=args.version,
        design_doc=args.design_doc,
        technology_stack=args.tech_stack
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
