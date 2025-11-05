"""Git commit message parsing utilities for Flow-Claude.

This module provides functions to parse structured commit messages into
Python dictionaries for task metadata, execution plans, and dependencies.
"""

import re
from typing import Dict, List, Any


def parse_commit_message(message: str) -> Dict[str, str]:
    """Parse structured commit message into sections.

    Sections start with ## Header
    Content is everything until next ## or end of message

    Args:
        message: Commit message text

    Returns:
        Dictionary mapping section names to content
        Section names are lowercased with spaces replaced by underscores

    Example:
        Input:
            "Initialize task

            ## Task Metadata
            ID: 001
            Description: Create User model

            ## Dependencies
            Preconditions: []"

        Output:
            {
                'task_metadata': 'ID: 001\\nDescription: Create User model',
                'dependencies': 'Preconditions: []'
            }
    """
    sections = {}
    current_section = None
    current_lines = []

    for line in message.split('\n'):
        if line.startswith('##'):
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()

            # Start new section
            section_name = line.strip('#').strip().lower().replace(' ', '_')
            current_section = section_name
            current_lines = []
        elif current_section:
            current_lines.append(line)

    # Save last section
    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()

    return sections


def extract_field(text: str, field: str) -> str:
    """Extract field value from text like 'Field: value'.

    Args:
        text: Text containing field definitions
        field: Field name to extract

    Returns:
        Field value as string, or empty string if not found

    Example:
        extract_field("ID: 001\\nDescription: Test", "ID") -> "001"
    """
    pattern = rf'^{re.escape(field)}:\s*(.+)$'
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_list(text: str, field: str) -> List[str]:
    """Extract list items after field header.

    Lists are expected to be in format:
        Field:
          - item1
          - item2

    Args:
        text: Text containing list
        field: Field name introducing the list

    Returns:
        List of items (without leading dashes)

    Example:
        extract_list("Provides:\\n  - User model\\n  - User.email", "Provides")
        -> ["User model", "User.email"]
    """
    lines = text.split('\n')
    in_list = False
    items = []

    for line in lines:
        # Check if this line contains the field header
        if field.lower() in line.lower() and ':' in line:
            in_list = True
            # Check if value is on same line after colon
            parts = line.split(':', 1)
            if len(parts) > 1:
                value = parts[1].strip()
                if value and value != '[]':
                    # Handle inline list like "Preconditions: []" or single item
                    if value.startswith('[') and value.endswith(']'):
                        # Parse as list literal
                        value = value.strip('[]').strip()
                        if value:
                            items.extend([v.strip().strip('"\'') for v in value.split(',')])
                    else:
                        items.append(value)
            continue

        if in_list:
            stripped = line.strip()
            if stripped.startswith('- '):
                # List item
                items.append(stripped[2:].strip())
            elif stripped.startswith('*'):
                # Alternative list marker
                items.append(stripped[1:].strip())
            elif stripped and not stripped.startswith(' ') and ':' in stripped:
                # New field started, stop parsing list
                break

    return items


def parse_context(text: str) -> Dict[str, Any]:
    """Parse context section from task metadata.

    Args:
        text: Context section text

    Returns:
        Dictionary with context fields

    Example:
        Input:
            "Session Goal: Add user auth\\nSession ID: session-123\\n
             Related Tasks:\\n  - Depends on: []\\n  - Enables: [002, 003]"

        Output:
            {
                'session_goal': 'Add user auth',
                'session_id': 'session-123',
                'related_tasks': {
                    'depends_on': [],
                    'enables': ['002', '003'],
                    'parallel_with': []
                }
            }
    """
    return {
        'session_goal': extract_field(text, 'Session Goal'),
        'session_id': extract_field(text, 'Session ID'),
        'plan_branch': extract_field(text, 'Plan Branch'),
        'plan_version': extract_field(text, 'Plan Version'),
        'related_tasks': {
            'depends_on': extract_list(text, 'Depends on'),
            'enables': extract_list(text, 'Enables'),
            'parallel_with': extract_list(text, 'Parallel with'),
        },
        'completed_tasks': extract_list(text, 'Completed Tasks'),
    }


def parse_task_metadata(sections: Dict[str, str]) -> Dict[str, Any]:
    """Parse task metadata from commit message sections.

    Args:
        sections: Dictionary from parse_commit_message()

    Returns:
        Structured task metadata dictionary

    Example:
        {
            'id': '001',
            'description': 'Create User model',
            'status': 'pending',
            'preconditions': [],
            'provides': ['User model class', 'User.email field'],
            'files': ['src/auth/models.py'],
            'session_goal': 'Add user authentication',
            ...
        }
    """
    metadata_text = sections.get('task_metadata', '')
    dependencies_text = sections.get('dependencies', '')
    files_text = sections.get('files', '')
    context_text = sections.get('context', '')
    estimates_text = sections.get('estimates', '')
    impl_text = sections.get('implementation_notes', '')

    # Parse context into structured format
    context = parse_context(context_text) if context_text else {}

    return {
        'id': extract_field(metadata_text, 'ID'),
        'description': extract_field(metadata_text, 'Description'),
        'status': extract_field(metadata_text, 'Status'),
        'preconditions': extract_list(dependencies_text, 'Preconditions'),
        'provides': extract_list(dependencies_text, 'Provides'),
        'files': extract_list(files_text, 'Files to modify'),
        'session_goal': context.get('session_goal', ''),
        'session_id': context.get('session_id', ''),
        'plan_branch': context.get('plan_branch', ''),
        'plan_version': context.get('plan_version', ''),
        'related_tasks': context.get('related_tasks', {}),
        'completed_tasks': context.get('completed_tasks', []),
        'estimated_time': extract_field(estimates_text, 'Estimated Time'),
        'priority': extract_field(estimates_text, 'Priority'),
        'implementation_notes': impl_text.strip() if impl_text else '',
    }


def parse_plan_commit(message: str) -> Dict[str, Any]:
    """Parse execution plan from plan branch commit.

    Args:
        message: Plan commit message

    Returns:
        Dictionary with plan information including tasks list

    Example:
        {
            'session_id': 'session-20250101-120000',
            'user_request': 'Add user authentication',
            'plan_version': 'v1',
            'tasks': [
                {'id': '001', 'description': '...', ...},
                {'id': '002', 'description': '...', ...},
            ],
            'total_tasks': 2,
            'estimated_total_time': '25 minutes'
        }
    """
    sections = parse_commit_message(message)

    # Extract session info
    session_text = sections.get('session_information', '')

    # Extract plan version from various possible locations
    plan_version = extract_field(sections.get('version', ''), 'Plan Version')
    if not plan_version:
        plan_version = extract_field(session_text, 'Plan Version')
    if not plan_version:
        # Try to extract from title like "Create execution plan v1"
        first_line = message.split('\n')[0]
        version_match = re.search(r'v(\d+)', first_line, re.IGNORECASE)
        if version_match:
            plan_version = f"v{version_match.group(1)}"

    # Extract tasks (each starts with ### Task NNN)
    tasks = []
    task_pattern = r'### Task (\d+[a-z]?)\s*\n(.*?)(?=### Task |\Z)'
    for match in re.finditer(task_pattern, message, re.DOTALL):
        task_id = match.group(1)
        task_text = match.group(2)

        task = {
            'id': task_id,
            'description': extract_field(task_text, 'Description'),
            'preconditions': extract_list(task_text, 'Preconditions'),
            'provides': extract_list(task_text, 'Provides'),
            'files': extract_list(task_text, 'Files'),
            'estimated_time': extract_field(task_text, 'Estimated Time'),
            'priority': extract_field(task_text, 'Priority'),
        }
        tasks.append(task)

    # Extract estimates
    estimates_text = sections.get('estimates', '') or sections.get('updated_estimates', '')

    return {
        'session_id': extract_field(session_text, 'Session ID'),
        'user_request': extract_field(session_text, 'User Request'),
        'created': extract_field(session_text, 'Created'),
        'plan_version': plan_version or 'v1',
        'tasks': tasks,
        'total_tasks': len(tasks),
        'estimated_total_time': extract_field(estimates_text, 'Estimated Total Time'),
        'dependency_graph': sections.get('dependency_graph', ''),
    }


def extract_provides_from_merge_commits(log_output: str) -> List[str]:
    """Extract all 'Provides' items from merge commit messages.

    Args:
        log_output: Output from 'git log main --merges --format=%B'

    Returns:
        List of all provided capabilities from merged tasks

    Example:
        Input: "Merge task/001\\n\\n## Provides\\n- User model\\n- User.email\\n\\n..."
        Output: ["User model", "User.email"]
    """
    provides = []
    in_provides_section = False

    for line in log_output.split('\n'):
        # Check if entering Provides section
        if re.match(r'^##\s*Provides', line, re.IGNORECASE):
            in_provides_section = True
            continue

        # Check if exiting Provides section (new section starts)
        if in_provides_section and line.startswith('##'):
            in_provides_section = False
            continue

        # Extract provide items
        if in_provides_section:
            stripped = line.strip()
            if stripped.startswith('- '):
                provides.append(stripped[2:].strip())
            elif stripped.startswith('* '):
                provides.append(stripped[2:].strip())

    return provides
