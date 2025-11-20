#!/usr/bin/env python3
"""Create task branch with metadata commit."""
import argparse
import asyncio
import json
import subprocess
import sys


async def create_task_branch(
    task_id: str,
    instruction: str,
    plan_branch: str,
    **kwargs
) -> dict:
    """Create task branch with metadata commit.

    Args:
        task_id: Task ID (e.g., '001')
        instruction: Task instruction (what needs to be done)
        plan_branch: Parent plan branch name (session-id is extracted from this)
        **kwargs: depends_on, key_files, priority

    Returns:
        Dict with success status
    """
    # Extract session_id from plan_branch (e.g., "plan/session-name" -> "session-name")
    session_id = plan_branch.replace('plan/', '') if plan_branch.startswith('plan/') else plan_branch
    try:
        branch_name = f"task/{task_id}-{instruction.lower().replace(' ', '-')[:30]}"

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
            f"Instruction: {instruction}",
            f"Status: pending",
            ""
        ]

        # Dependencies
        depends_on = kwargs.get('depends_on', [])
        if depends_on:
            commit_lines.extend([
                "## Dependencies",
                f"Depends on: {', '.join(depends_on)}",
                ""
            ])

        # Key files
        key_files = kwargs.get('key_files', [])
        if key_files:
            commit_lines.extend([
                "## Key Files",
                ', '.join(key_files),
                ""
            ])

        # Context
        commit_lines.extend([
            "## Context",
            f"Session ID: {session_id}",
            f"Plan Branch: {plan_branch}",
            f"Priority: {kwargs.get('priority', 'medium')}",
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
    parser = argparse.ArgumentParser(
        description='Create task branch with metadata commit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create a task with detailed instruction
  python -m flow_claude.scripts.create_task_branch \\
    --task-id="001" \\
    --instruction="Create HTML structure with navigation and hero section. Use Write tool to create index.html. Include semantic HTML5 tags. Add nav, header, and main sections." \\
    --plan-branch="plan/build-conference-website" \\
    --depends-on='[]' \\
    --key-files='["index.html"]' \\
    --priority="high"

  # Create a task with tool usage guidance
  python -m flow_claude.scripts.create_task_branch \\
    --task-id="002" \\
    --instruction="Add CSS styling for responsive layout. Use Write tool to create css/styles.css. Implement mobile-first design with breakpoints at 768px and 1024px. Use Flexbox for navigation layout." \\
    --plan-branch="plan/build-conference-website" \\
    --depends-on='["001"]' \\
    --key-files='["css/styles.css"]' \\
    --priority="medium"

Output:
  JSON with success status and task branch name (e.g., task/001-create-html-structure)
        '''
    )
    parser.add_argument(
        '--task-id',
        type=str,
        required=True,
        metavar='ID',
        help='Unique task ID (e.g., "001", "002a"). Use zero-padded numbers for proper sorting.'
    )
    parser.add_argument(
        '--instruction',
        type=str,
        required=True,
        metavar='TEXT',
        help='Detailed task instruction: what needs to be done, which MCP tools to use (if any), and specific implementation guidance. Will be slugified for branch name.'
    )
    parser.add_argument(
        '--plan-branch',
        type=str,
        required=True,
        metavar='BRANCH',
        help='Parent plan branch name (e.g., "plan/build-user-authentication"). Session ID is extracted from this.'
    )
    parser.add_argument(
        '--depends-on',
        type=str,
        default='[]',
        metavar='JSON',
        help='JSON array of upstream task IDs that must complete before this task (e.g., ["001", "002"]). Empty array [] means no dependencies.'
    )
    parser.add_argument(
        '--key-files',
        type=str,
        default='[]',
        metavar='JSON',
        help='JSON array of key files this task will create or modify (e.g., ["index.html", "css/styles.css"]). Use relative paths from project root.'
    )
    parser.add_argument(
        '--priority',
        type=str,
        default='medium',
        metavar='LEVEL',
        choices=['low', 'medium', 'high'],
        help='Task priority: low, medium, or high. Default: medium'
    )

    args = parser.parse_args()

    # Parse JSON
    try:
        depends_on = json.loads(args.depends_on)
        key_files = json.loads(args.key_files)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    result = asyncio.run(create_task_branch(
        task_id=args.task_id,
        instruction=args.instruction,
        plan_branch=args.plan_branch,
        depends_on=depends_on,
        key_files=key_files,
        priority=args.priority
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
