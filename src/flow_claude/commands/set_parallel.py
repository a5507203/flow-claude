#!/usr/bin/env python3
"""Set maximum parallel workers for the orchestrator."""

import sys
import re
from pathlib import Path


def set_parallel_workers(num_workers: int, project_root: Path = None) -> dict:
    """Set max parallel workers in orchestrator SKILL.md.

    Args:
        num_workers: Number of parallel workers (1-10)
        project_root: Project root directory (defaults to current directory)

    Returns:
        dict with 'success' and 'message' fields
    """
    if project_root is None:
        project_root = Path.cwd()

    # Validate input
    if not 1 <= num_workers <= 10:
        return {
            'success': False,
            'message': f'Error: Number must be between 1 and 10 (got {num_workers})'
        }

    skill_file = project_root / '.claude' / 'skills' / 'your-workflow' / 'SKILL.md'

    if not skill_file.exists():
        return {
            'success': False,
            'message': f'Error: Orchestrator skill not found at {skill_file}'
        }

    # Read file
    content = skill_file.read_text(encoding='utf-8')

    # Update the description line
    pattern = r'(description:.*Max parallel workers: )\d+'
    replacement = rf'\g<1>{num_workers}'

    new_content, count = re.subn(pattern, replacement, content)

    if count == 0:
        return {
            'success': False,
            'message': 'Error: Could not find "Max parallel workers: X" in description'
        }

    # Write back
    skill_file.write_text(new_content, encoding='utf-8')

    return {
        'success': True,
        'message': f'Max parallel workers set to {num_workers}, plrease restart the claude.'
    }


def main():
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: python -m flow_claude.commands.set_parallel <number>", file=sys.stderr)
        print("  where <number> is between 1 and 10", file=sys.stderr)
        return 1

    try:
        num_workers = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid number '{sys.argv[1]}'", file=sys.stderr)
        return 1

    result = set_parallel_workers(num_workers)

    if result['success']:
        print(result['message'])
        return 0
    else:
        print(result['message'], file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
