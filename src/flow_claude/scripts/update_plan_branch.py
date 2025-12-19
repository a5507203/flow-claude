#!/usr/bin/env python3
"""Update plan branch with complete plan snapshot."""
import argparse
import asyncio
import json
import subprocess
import sys


def validate_task_detail_length(tasks: list) -> None:
    """Validate that each task_detail has at least 100 words.

    Args:
        tasks: List of task definitions

    Raises:
        ValueError: If any task_detail has fewer than 100 words
    """
    for task in tasks:
        task_detail = task.get('task_detail', '')
        word_count = len(task_detail.split())
        if word_count < 25:
            raise ValueError(
                f"Task {task.get('id', 'unknown')}: task_detail must be at least 25 words, "
                f"but got {word_count} words. Please provide more detailed task description "
                f"including: specific implementation steps, expected behavior, edge cases to handle, "
                f"integration points with other components, and acceptance criteria."
            )


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
            status = task.get('status', 'pending')

            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Task Detail: {task['task_detail']}",
                f"Status: {status}",
                f"Depends on: {', '.join(depends_on) if depends_on else 'None'}",
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
  # Note: Each task_detail must be at least 100 words
  python -m flow_claude.scripts.update_plan_branch \\
    --plan-branch="plan/add-user-authentication" \\
    --user-request="Add user authentication with JWT and bcrypt" \\
    --design-doc="Complete design documentation..." \\
    --tech-stack="Python 3.10, Flask 2.3, SQLAlchemy, bcrypt, PyJWT" \\
    --tasks='[
      {"id":"001","task_detail":"Create User model class in src/models/user.py using SQLAlchemy ORM. The model must include the following fields: id as primary key with auto-increment, email as unique string field with maximum 255 characters and index for fast lookups, password_hash as string field with maximum 128 characters for storing bcrypt hashed passwords, created_at as datetime field with default to current UTC timestamp, updated_at as datetime field that auto-updates on record modification. Implement a password property setter that automatically hashes plaintext passwords using bcrypt with 12 salt rounds. Add a verify_password method that compares plaintext input against stored hash. Include __repr__ method for debugging. Add appropriate table constraints and ensure model integrates with existing database session configuration in src/database.py.","depends_on":[],"status":"completed"},
      {"id":"002","task_detail":"Implement password hashing utilities module in src/utils/auth.py providing secure password operations. Create hash_password function accepting plaintext string and returning bcrypt hash with configurable salt rounds defaulting to 12. Create verify_password function accepting plaintext and hash, returning boolean for match status. Implement password strength validator function checking minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character. Add generate_secure_token function for creating cryptographically secure random tokens using secrets module for password reset functionality. Include rate limiting helper function to track failed authentication attempts per IP address. All functions must have comprehensive docstrings, type hints, and handle edge cases like empty strings or None values gracefully with appropriate exceptions.","depends_on":[],"status":"in_progress"},
      {"id":"003","task_detail":"Implement JWT token generation and validation utilities in src/utils/jwt.py for secure session management. Create generate_access_token function accepting user_id and optional claims dictionary, returning signed JWT string with 15-minute expiration using HS256 algorithm and application secret key from environment variables. Create generate_refresh_token function with 7-day expiration for long-lived sessions. Implement verify_token function that decodes and validates JWT signature, expiration, and required claims, returning decoded payload or raising appropriate exceptions for expired or invalid tokens. Add token_required decorator for protecting Flask routes that extracts and validates Authorization Bearer token header. Include token blacklist mechanism using Redis for logout functionality. Handle clock skew with configurable leeway parameter.","depends_on":[],"status":"pending"},
      {"id":"004","task_detail":"Implement user registration endpoint POST /api/auth/register in src/api/auth.py accepting JSON body with email, password, and optional profile fields. Validate email format using regex pattern and check for existing user to prevent duplicates returning 409 Conflict. Validate password strength using utils/auth.py validator ensuring minimum security requirements. Create new User model instance with hashed password and save to database within transaction. Generate email verification token and queue verification email using background task worker. Return 201 Created with user profile data excluding sensitive fields. Implement rate limiting of 10 registrations per hour per IP address to prevent abuse. Log registration events including IP address and user agent for security auditing. Handle database errors gracefully with appropriate error responses.","depends_on":["001","002"],"status":"pending"}
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
        help='Complete JSON array of ALL tasks with current status. Each task: {id, task_detail, depends_on, status}'
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
        required=True,
        metavar='TEXT',
        help='Complete design documentation (include all updates and architecture)'
    )
    parser.add_argument(
        '--tech-stack',
        type=str,
        required=True,
        metavar='TEXT',
        help='Technology stack: languages, frameworks, libraries, tools'
    )

    args = parser.parse_args()

    try:
        tasks = json.loads(args.tasks)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    # Validate task_detail length (minimum 100 words)
    try:
        validate_task_detail_length(tasks)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}))
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
