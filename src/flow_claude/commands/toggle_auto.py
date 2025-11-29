#!/usr/bin/env python3
"""Toggle autonomous mode by managing user.md file."""

import sys
from pathlib import Path
import shutil


def toggle_autonomous_mode(project_root: Path = None) -> dict:
    """Toggle autonomous mode by creating/removing user.md.

    When user.md exists: auto is ON (user agent enabled)
    When user.md missing: auto is OFF

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        dict with 'success', 'mode', and 'message' fields
    """
    if project_root is None:
        project_root = Path.cwd()

    user_file = project_root / '.claude' / 'agents' / 'user.md'
    template_file = Path(__file__).parent.parent / 'templates' / 'agents' / 'user.md'

    # Check current state
    if user_file.exists():
        # user.md exists -> Turn OFF by removing file
        user_file.unlink()
        return {
            'success': True,
            'mode': 'OFF',
            'message': 'Autonomous mode: OFF, you can ask user for clarifications'
        }
    else:
        # user.md missing -> Turn ON by creating file
        # Ensure .claude/agents directory exists
        user_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy template
        if template_file.exists():
            shutil.copy(template_file, user_file)
            return {
                'success': True,
                'mode': 'ON',
                'message': 'Autonomous mode: ON, ask user agent for clarifications instead of asking user' 
            }
        else:
            return {
                'success': False,
                'mode': 'unknown',
                'message': f'Error: Template not found at {template_file}'
            }


def main():
    """CLI entry point."""
    result = toggle_autonomous_mode()

    if result['success']:
        print(result['message'])
        return 0
    else:
        print(f"ERROR: {result['message']}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
