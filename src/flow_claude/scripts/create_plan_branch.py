#!/usr/bin/env python3
"""Create plan branch with metadata commit."""
import argparse
import asyncio
import json
import subprocess
import sys


async def create_plan_branch(
    session_name: str,
    user_request: str,
    tasks: list,
    **kwargs
) -> dict:
    """Create plan branch with structured metadata commit.

    Args:
        session_name: Unique session name
        user_request: Original user request
        tasks: List of task definitions
        **kwargs: Optional fields:
            - design_doc: Complete design documentation (architecture, patterns, structure)
            - tech_stack: Technology stack

    Returns:
        Dict with success status
    """
    try:
        branch_name = f"plan/{session_name}"

        # Create branch from flow (without switching)
        subprocess.run(
            ['git', 'branch', branch_name, 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Switch to the new branch temporarily for commit
        subprocess.run(
            ['git', 'checkout', branch_name],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Build commit message
        commit_lines = [
            "Initialize execution plan v1",
            "",
            "## Session Information",
            f"Session name: {session_name}",
            f"User Request: {user_request}",
            "Plan Version: v1",
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

        # Add tasks
        commit_lines.append("## Tasks")
        for task in tasks:
            depends_on = task.get('depends_on', [])

            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Description: {task['description']}",
                f"Depends on: {', '.join(depends_on) if depends_on else 'None'}",
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

        # Switch back to flow branch
        subprocess.run(
            ['git', 'checkout', 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        return {
            "success": True,
            "branch": branch_name,
            "session_name": session_name
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
        description='Create plan branch with metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create a plan with task dependencies (DAG)
  python -m flow_claude.scripts.create_plan_branch \\
    --session-name="build-conference-website" \\
    --user-request="Build a conference website" \\
    --architecture="Static HTML/CSS/JS website with responsive design" \\
    --design-doc="Project Structure: index.html (main page), css/ (styles), js/ (scripts). Design: Modern single-page layout with sticky navigation, hero section, schedule grid, speaker cards. Mobile-first responsive design with breakpoints at 768px and 1024px. Components organized by section (nav, hero, schedule, speakers, footer). Follow BEM naming convention for CSS classes." \\
    --tech-stack="HTML5, CSS3, JavaScript ES6" \\
    --tasks='[{"id":"001","description":"Create HTML structure","depends_on":[]},{"id":"002","description":"Add CSS styling","depends_on":["001"]},{"id":"003","description":"Add JavaScript","depends_on":["001"]},{"id":"004","description":"Test layout","depends_on":["002","003"]}]'

Output:
  JSON with success status and plan branch information
        '''
    )
    parser.add_argument(
        '--session-name',
        type=str,
        required=True,
        metavar='NAME',
        help='Meaningful session name describing the work (e.g., "build-user-authentication", "add-responsive-nav"). Use lowercase with hyphens.'
    )
    parser.add_argument(
        '--user-request',
        type=str,
        required=True,
        metavar='TEXT',
        help='Original user request describing what needs to be built'
    )
    parser.add_argument(
        '--tasks',
        type=str,
        required=True,
        metavar='JSON',
        help='JSON array of task objects. Each task must have: id, description, depends_on (upstream task IDs)'
    )
    parser.add_argument(
        '--design-doc',
        type=str,
        default='',
        metavar='TEXT',
        help='Complete design documentation (can be long, like CLAUDE.md). Should include: architecture overview, how features integrate with existing codebase, project structure, design patterns, architectural decisions, interface contracts. This is worker\'s primary reference document.'
    )
    parser.add_argument(
        '--tech-stack',
        type=str,
        default='',
        metavar='TEXT',
        help='Technology stack: languages, frameworks, libraries, tools (e.g., "Python 3.10, Flask 2.3, SQLAlchemy")'
    )
    args = parser.parse_args()

    # Parse JSON fields
    try:
        tasks = json.loads(args.tasks)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    # Run async function
    result = asyncio.run(create_plan_branch(
        session_name=args.session_name,
        user_request=args.user_request,
        tasks=tasks,
        design_doc=args.design_doc,
        technology_stack=args.tech_stack
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
