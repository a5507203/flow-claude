"""CLAUDE.md generation utilities.

Handles CLAUDE.md generation using Claude Code CLI with fallback to template.
"""

import subprocess
from pathlib import Path


def check_claude_code_available() -> bool:
    """Check if Claude Code CLI is available.

    Returns:
        bool: True if claude command is available, False otherwise
    """
    try:
        result = subprocess.run(
            'claude --version',
            shell=True,  # Windows needs shell=True to find .cmd files
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def generate_with_claude_code(cwd: Path) -> tuple[bool, str]:
    """Generate CLAUDE.md using Claude Code CLI.

    Args:
        cwd: Current working directory where CLAUDE.md should be created

    Returns:
        tuple: (success: bool, error_message: str)
    """
    try:
        prompt = "Please create a CLAUDE.md file for this project with proper documentation structure. Write the file now."

        # Use echo to pipe prompt to claude code
        result = subprocess.run(
            f'echo {prompt} | claude code --print --dangerously-skip-permissions',
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes for Claude Code to analyze and generate
        )

        # Check if CLAUDE.md was created
        claude_md = cwd / "CLAUDE.md"
        if claude_md.exists():
            return True, ""
        else:
            return False, "CLAUDE.md file not created by Claude Code"

    except subprocess.TimeoutExpired:
        return False, "Claude Code generation timed out (>180s)"
    except Exception as e:
        return False, f"Claude Code error: {e}"


def generate_template() -> str:
    """Generate static CLAUDE.md template.

    Returns:
        str: CLAUDE.md template content
    """
    return """# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

[Describe your project here]

## Architecture

[Describe the architecture and key components]

## Development Workflow

[Describe how to develop, test, and deploy]

## Key Files

[List important files and their purposes]

## Coding Standards

[Describe coding standards and conventions]

## Common Tasks

### Running the project
```bash
# Add commands here
```

### Running tests
```bash
# Add commands here
```

## Important Notes

[Any important notes or gotchas for Claude to be aware of]
"""


def generate_claude_md(cwd: Path) -> tuple[bool, str, str]:
    """Generate CLAUDE.md file.

    Tries Claude Code CLI first, falls back to template if unavailable or fails.

    Args:
        cwd: Current working directory where CLAUDE.md should be created

    Returns:
        tuple: (success: bool, method: str, error_message: str)
            method: "claude_code", "template", or "failed"
    """
    claude_md = cwd / "CLAUDE.md"

    # Try Claude Code first
    if check_claude_code_available():
        success, error = generate_with_claude_code(cwd)
        if success:
            return True, "claude_code", ""
        # If Claude Code failed, fall through to template

    # Fallback to static template
    try:
        template = generate_template()
        with open(claude_md, 'w') as f:
            f.write(template)
        return True, "template", ""
    except Exception as e:
        return False, "failed", str(e)
