#!/usr/bin/env python3
"""Get list of available preconditions from merged tasks on flow branch."""
import argparse
import asyncio
import json
import re
import subprocess
import sys


async def get_provides() -> dict:
    """Query flow branch merge commits for available provides.

    Returns:
        Dict with list of available capabilities
    """
    try:
        # Get merge commits on flow branch
        result = subprocess.run(
            ['git', 'log', 'flow', '--merges', '--format=%B', '-n', '50'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        commit_messages = result.stdout

        # Extract provides from merge commits
        provides = []
        provide_pattern = r'## Provides\s*(.*?)(?=\n##|\n\n|$)'

        for match in re.finditer(provide_pattern, commit_messages, re.DOTALL):
            provides_section = match.group(1).strip()
            # Extract list items
            for line in provides_section.split('\n'):
                line = line.strip()
                if line.startswith('- ') or line.startswith('✓ '):
                    capability = line.lstrip('- ✓ ').strip()
                    if capability and capability not in provides:
                        provides.append(capability)

        return {
            "success": True,
            "provides": provides,
            "count": len(provides)
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr}",
            "provides": []
        }
    except subprocess.TimeoutExpired:
        return {
            "error": "Git command timed out",
            "provides": []
        }
    except Exception as e:
        return {
            "error": f"Failed to get provides: {str(e)}",
            "provides": []
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Get available capabilities from completed tasks'
    )

    args = parser.parse_args()

    # Run async function
    result = asyncio.run(get_provides())

    # Output JSON
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
