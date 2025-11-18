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

    Supported fields (as specified in prompts/planner.md):
        - Session Goal, Session ID, Plan Branch, Plan Version (required)
        - Depends on, Enables (actively used for dependency tracking)
        - Parallel with, Completed Tasks (optional, for future extensibility)

    Note: Parser supports 'Parallel with:' and 'Completed Tasks:' fields
    for extensibility, but these are not currently required by planner.md.
    If present, they will be parsed; if absent, empty lists are returned.

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
        Dictionary with plan information including tasks list and architecture

    Example:
        {
            'session_id': 'session-20250101-120000',
            'user_request': 'Add user authentication',
            'plan_version': 'v1',
            'architecture': 'System uses MVC pattern...',
            'design_patterns': 'Repository pattern for...',
            'technology_stack': 'Python 3.10, Flask...',
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

    # Extract architecture sections (commit-only architecture)
    architecture_text = sections.get('architecture', '')
    design_patterns_text = sections.get('design_patterns', '')
    tech_stack_text = sections.get('technology_stack', '')

    # Extract tasks (each starts with ### Task NNN)
    tasks = []
    task_pattern = r'### Task (\d+[a-z]?)\s*\n(.*?)(?=### Task |\Z)'
    matches = list(re.finditer(task_pattern, message, re.DOTALL))

    # Check if there are task sections that didn't match (likely missing IDs)
    task_sections_count = message.count('### Task')
    if task_sections_count > len(matches):
        # Some task headers are malformed
        import logging
        logging.warning(
            f"Found {task_sections_count} task sections but only {len(matches)} have valid IDs. "
            f"Task headers must be formatted as '### Task 001' with a numeric ID."
        )
        # Also check for common mistakes
        if '### Task \n' in message or '### Task\n' in message:
            logging.error("Found task headers without IDs - tasks will not be parsed correctly!")

    for match in matches:
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
        'architecture': architecture_text,
        'design_patterns': design_patterns_text,
        'technology_stack': tech_stack_text,
        'tasks': tasks,
        'total_tasks': len(tasks),
        'estimated_total_time': extract_field(estimates_text, 'Estimated Total Time'),
        'dependency_graph': sections.get('dependency_graph', ''),
    }


def extract_provides_from_merge_commits(log_output: str) -> List[str]:
    """Extract all 'Provides' items from merge commit messages.

    Args:
        log_output: Output from 'git log flow --merges --format=%B'

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


def parse_worker_commit(message: str) -> Dict[str, Any]:
    """Parse worker progressive commit with embedded design and TODO list.

    Worker commits in the commit-only architecture contain:
    - Design: Architecture decisions and interfaces
    - TODO List: Implementation checklist with completion status
    - Progress: Current status and completion metrics
    - Implementation: What was done in this specific commit

    Args:
        message: Git commit message from worker

    Returns:
        Dictionary with parsed worker commit data

    Example:
        Input commit message:
            [task-001] Implement: Create models/user.py (1/6)

            ## Implementation
            Created models/user.py with SQLAlchemy base.

            ## Design
            ### Overview
            Implementing User model with bcrypt.

            ### Architecture Decisions
            - SQLAlchemy ORM
            - Bcrypt for passwords

            ### Interfaces Provided
            - User(email, password)

            ## TODO List
            - [x] 1. Create models/user.py
            - [ ] 2. Add User class
            - [ ] 3. Add password hashing

            ## Progress
            Status: in_progress
            Completed: 1/6 tasks

        Output:
            {
                'task_id': '001',
                'commit_type': 'implementation',
                'step_number': 1,
                'total_steps': 6,
                'implementation': 'Created models/user.py with SQLAlchemy base.',
                'design': {
                    'overview': 'Implementing User model with bcrypt.',
                    'architecture_decisions': ['SQLAlchemy ORM', 'Bcrypt for passwords'],
                    'interfaces_provided': ['User(email, password)']
                },
                'todo_list': [
                    {'number': 1, 'description': 'Create models/user.py', 'completed': True},
                    {'number': 2, 'description': 'Add User class', 'completed': False},
                    {'number': 3, 'description': 'Add password hashing', 'completed': False}
                ],
                'progress': {
                    'status': 'in_progress',
                    'completed': 1,
                    'total': 6
                }
            }
    """
    sections = parse_commit_message(message)

    # Parse commit title to extract task ID and step info
    first_line = message.split('\n')[0]
    task_id = ''
    commit_type = 'unknown'
    step_number = None
    total_steps = None

    # Extract task ID from [task-XXX] prefix
    task_match = re.search(r'\[task-(\d+[a-z]?)\]', first_line, re.IGNORECASE)
    if task_match:
        task_id = task_match.group(1)

    # Determine commit type
    if 'Initialize:' in first_line or 'initialize:' in first_line:
        commit_type = 'initial_design'
    elif 'Implement:' in first_line or 'implement:' in first_line:
        commit_type = 'implementation'
        # Extract step number (X/Y)
        step_match = re.search(r'\((\d+)/(\d+)\)', first_line)
        if step_match:
            step_number = int(step_match.group(1))
            total_steps = int(step_match.group(2))

    # Parse Design section
    design_text = sections.get('design', '')
    design = {
        'overview': '',
        'architecture_decisions': [],
        'interfaces_provided': []
    }

    if design_text:
        # Extract Overview subsection
        overview_match = re.search(r'###\s*Overview\s*\n(.*?)(?=###|\Z)', design_text, re.DOTALL | re.IGNORECASE)
        if overview_match:
            design['overview'] = overview_match.group(1).strip()

        # Extract Architecture Decisions subsection
        arch_match = re.search(r'###\s*Architecture Decisions\s*\n(.*?)(?=###|\Z)', design_text, re.DOTALL | re.IGNORECASE)
        if arch_match:
            arch_text = arch_match.group(1).strip()
            for line in arch_text.split('\n'):
                stripped = line.strip()
                if stripped.startswith('- '):
                    design['architecture_decisions'].append(stripped[2:].strip())
                elif stripped.startswith('* '):
                    design['architecture_decisions'].append(stripped[2:].strip())

        # Extract Interfaces Provided subsection
        interfaces_match = re.search(r'###\s*Interfaces Provided\s*\n(.*?)(?=###|\Z)', design_text, re.DOTALL | re.IGNORECASE)
        if interfaces_match:
            interfaces_text = interfaces_match.group(1).strip()
            for line in interfaces_text.split('\n'):
                stripped = line.strip()
                if stripped.startswith('- '):
                    design['interfaces_provided'].append(stripped[2:].strip())
                elif stripped.startswith('* '):
                    design['interfaces_provided'].append(stripped[2:].strip())

    # Parse TODO List section
    todo_text = sections.get('todo_list', '')
    todo_list = []

    if todo_text:
        # Match patterns like "- [x] 1. Description" or "- [ ] 2. Description"
        todo_pattern = r'-\s*\[([ xX])\]\s*(\d+)\.\s*(.+)'
        for match in re.finditer(todo_pattern, todo_text):
            completed = match.group(1).lower() == 'x'
            number = int(match.group(2))
            description = match.group(3).strip()
            todo_list.append({
                'number': number,
                'description': description,
                'completed': completed
            })

    # Parse Progress section
    progress_text = sections.get('progress', '')
    progress = {
        'status': 'unknown',
        'completed': 0,
        'total': 0
    }

    if progress_text:
        status = extract_field(progress_text, 'Status')
        if status:
            progress['status'] = status

        completed_str = extract_field(progress_text, 'Completed')
        if completed_str:
            # Parse "X/Y tasks" format
            completed_match = re.search(r'(\d+)/(\d+)', completed_str)
            if completed_match:
                progress['completed'] = int(completed_match.group(1))
                progress['total'] = int(completed_match.group(2))

    # Parse Implementation section
    implementation = sections.get('implementation', '').strip()

    return {
        'task_id': task_id,
        'commit_type': commit_type,
        'step_number': step_number,
        'total_steps': total_steps,
        'implementation': implementation,
        'design': design,
        'todo_list': todo_list,
        'progress': progress
    }
