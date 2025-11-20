"""CLAUDE.md update/creation utilities.

Handles CLAUDE.md initialization for Flow-Claude.
"""

from pathlib import Path


def update_claude_md(cwd: Path) -> tuple[bool, str, str]:
    """Update or create CLAUDE.md with Flow-Claude instruction.

    If CLAUDE.md exists, prepends the instruction to the top.
    If it doesn't exist, creates it with the instruction.

    Args:
        cwd: Current working directory where CLAUDE.md should be created/updated

    Returns:
        tuple: (success: bool, status: str, error_message: str)
            status: "created", "updated", or "unchanged"
    """
    claude_md = cwd / "CLAUDE.md"
    instruction = "#IMPORTANT (DO NOT CHANGE) /n **Understand your-workflow and read the SKILL.md before working\n\n**"

    try:
        if claude_md.exists():
            # Read existing content
            existing_content = claude_md.read_text(encoding='utf-8')

            # Check if instruction already exists at the top
            if existing_content.startswith("Understand your-workflow and read the SKILL.md before working"):
                return True, "unchanged", ""

            # Prepend instruction to existing content
            new_content = instruction + existing_content
            claude_md.write_text(new_content, encoding='utf-8')
            return True, "updated", ""
        else:
            # Create new CLAUDE.md with instruction
            claude_md.write_text(instruction, encoding='utf-8')
            return True, "created", ""
    except Exception as e:
        return False, "failed", str(e)
