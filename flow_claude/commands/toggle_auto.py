#!/usr/bin/env python3
"""Toggle autonomous mode by managing user-proxy.md file."""

import sys
from pathlib import Path
import shutil


def toggle_autonomous_mode(project_root: Path = None) -> dict:
    """Toggle autonomous mode by creating/removing user-proxy.md.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        dict with 'success', 'mode', and 'message' fields
    """
    if project_root is None:
        project_root = Path.cwd()

    user_proxy_file = project_root / '.claude' / 'agents' / 'user-proxy.md'
    template_file = Path(__file__).parent.parent / 'templates' / 'agents' / 'user.md'

    # Check current state
    if user_proxy_file.exists():
        # File exists -> Autonomous mode OFF -> Turn it ON by removing file
        user_proxy_file.unlink()
        return {
            'success': True,
            'mode': 'ON',
            'message': 'Autonomous mode: ON (user-proxy.md removed)'
        }
    else:
        # File missing -> Autonomous mode ON -> Turn it OFF by creating file
        # Ensure .claude/agents directory exists
        user_proxy_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy template
        if template_file.exists():
            shutil.copy(template_file, user_proxy_file)
            return {
                'success': True,
                'mode': 'OFF',
                'message': 'Autonomous mode: OFF (user-proxy.md created)'
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
