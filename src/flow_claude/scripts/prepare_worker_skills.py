"""Prepare worker skills by copying skill folders to worktree's .claude/skills directory.

This enables native Claude Code skill discovery and trigger matching for workers.
Skills are copied with their supporting files (scripts, reference docs) intact,
while SKILL.md is regenerated with only the requested sections.
"""
import os
import re
import yaml
import json
import sys
import shutil
import argparse
from pathlib import Path
from typing import Dict, Any, List


class SkillLoader:
    def __init__(self):
        # Regex to match H2 headers like "## Header Name"
        self.header_pattern = re.compile(r'(?m)^##\s+(.+?)\s*$')

    def load_bundle(self, skills_dir: str, required_headers: List[str], skill_filename="SKILL.md") -> str:
        """
        Loads a specific skill file, parses the requested bundle configuration,
        and returns the sliced context string.
        """
        file_path = os.path.join(skills_dir, skill_filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Skill file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Parse Frontmatter and Body
        frontmatter, body = self._parse_frontmatter(content)

        # 2. Slice the Markdown Body
        sections = self._parse_markdown_sections(body)

        # 3. Construct Final Output with frontmatter preserved
        final_parts = []

        # Reconstruct frontmatter
        if frontmatter:
            final_parts.append("---")
            final_parts.append(yaml.dump(frontmatter, default_flow_style=False).strip())
            final_parts.append("---")
            final_parts.append("")

        # Add skill title
        final_parts.append(f"# {frontmatter.get('name', 'Skill')}")
        final_parts.append("")

        for header in required_headers:
            if header in sections:
                final_parts.append(sections[header])
                final_parts.append("")
            else:
                print(f"Warning: Section '## {header}' not found in {skills_dir}")

        return "\n".join(final_parts)

    def _parse_frontmatter(self, content: str) -> tuple[Dict, str]:
        """Separates YAML frontmatter from markdown body."""
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if not match:
            return {}, content

        yaml_text = match.group(1)
        body_text = match.group(2)

        try:
            metadata = yaml.safe_load(yaml_text) or {}
            return metadata, body_text
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}")

    def _parse_markdown_sections(self, body: str) -> Dict[str, str]:
        """
        Splits markdown into a dictionary where Key = Header Name, Value = Section Content.
        """
        sections = {}
        parts = self.header_pattern.split(body)

        for i in range(1, len(parts), 2):
            header_name = parts[i].strip()
            section_content = f"## {header_name}\n{parts[i+1].strip()}"
            sections[header_name] = section_content

        return sections


def write_skill_to_worktree(
    skill_src_dir: Path,
    worktree_path: Path,
    skill_name: str,
    extracted_content: str
) -> Dict[str, Any]:
    """
    Copy skill folder to worker's .claude/skills/ directory with extracted SKILL.md.

    Args:
        skill_src_dir: Source skill directory (e.g., templates/skills/pptx)
        worktree_path: Worker's worktree path (e.g., .worktrees/worker-1)
        skill_name: Name of the skill (used for destination folder)
        extracted_content: Extracted SKILL.md content with only requested sections

    Returns:
        Dict with success status and paths
    """
    try:
        # Create destination directory
        dest_dir = worktree_path / ".claude" / "skills" / skill_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files and subdirectories EXCEPT SKILL.md and SKILL_new.md
        for item in skill_src_dir.iterdir():
            if item.name in ("SKILL.md", "SKILL_new.md"):
                continue  # Skip original skill files

            dest_item = dest_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

        # Write extracted SKILL.md
        skill_md_path = dest_dir / "SKILL.md"
        with open(skill_md_path, 'w', encoding='utf-8') as f:
            f.write(extracted_content)

        return {
            "success": True,
            "skill_name": skill_name,
            "dest_path": str(dest_dir),
            "skill_md_path": str(skill_md_path)
        }

    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied writing to: {dest_dir}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to copy skill {skill_name}: {str(e)}"
        }


def prepare_skills(skills_dict: Dict[str, List[str]], worktree_path: str) -> Dict[str, Any]:
    """
    Prepare skills for a worker by copying skill folders to worktree's .claude/skills/.

    Each skill folder is copied with its supporting files (scripts, reference docs),
    and a new SKILL.md is generated with only the requested sections.

    Args:
        skills_dict: Mapping of skill directory paths to list of section headers
                     e.g., {"path/to/pptx": ["Shared Definitions", "Creating Without Template"]}
        worktree_path: Path to worker's worktree (e.g., .worktrees/worker-1)

    Returns:
        Dict with success status and list of prepared skills
    """
    try:
        loader = SkillLoader()
        worktree = Path(worktree_path)
        prepared_skills = []
        errors = []

        # Ensure .claude/skills directory exists
        skills_dest = worktree / ".claude" / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)

        for skill_dir, section_list in skills_dict.items():
            skill_path = Path(skill_dir)

            # Validate source directory
            if not skill_path.is_dir():
                errors.append(f"Skill directory not found: {skill_dir}")
                continue

            # Extract skill name from path
            skill_name = skill_path.name

            # Extract requested sections from SKILL.md
            try:
                extracted_content = loader.load_bundle(str(skill_path), section_list)
            except FileNotFoundError as e:
                errors.append(str(e))
                continue

            # Copy skill folder and write extracted SKILL.md
            result = write_skill_to_worktree(
                skill_src_dir=skill_path,
                worktree_path=worktree,
                skill_name=skill_name,
                extracted_content=extracted_content
            )

            if result["success"]:
                prepared_skills.append({
                    "skill_name": skill_name,
                    "sections": section_list,
                    "dest_path": result["dest_path"]
                })
            else:
                errors.append(result["error"])

        # Return results
        if errors and not prepared_skills:
            return {
                "success": False,
                "error": "; ".join(errors)
            }

        return {
            "success": True,
            "worktree_path": worktree_path,
            "skills_path": str(skills_dest),
            "prepared_skills": prepared_skills,
            "errors": errors if errors else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to prepare skills: {str(e)}"
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Prepare worker skills by copying to worktree .claude/skills/',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Prepare pptx skill with specific sections
  python -m flow_claude.scripts.prepare_worker_skills \\
    --skill_dict='{"src/flow_claude/templates/skills/pptx": ["Shared Definitions", "Creating Without Template"]}' \\
    --worktree_path=".worktrees/worker-1"

  # Prepare multiple skills
  python -m flow_claude.scripts.prepare_worker_skills \\
    --skill_dict='{
      "src/flow_claude/templates/skills/git-tools": ["Shared Definitions", "Read Tools", "Write Tools"],
      "src/flow_claude/templates/skills/pdf": ["Shared Definitions", "Reading and Extraction"]
    }' \\
    --worktree_path=".worktrees/worker-2"

Output:
  Creates .worktrees/worker-N/.claude/skills/{skill-name}/ with:
    - SKILL.md (extracted sections only)
    - All supporting files (scripts/, reference/, examples/, etc.)
        '''
    )
    parser.add_argument(
        '--skill_dict',
        type=str,
        required=True,
        help='JSON dict mapping skill paths to section headers'
    )
    parser.add_argument(
        '--worktree_path',
        type=str,
        required=True,
        help='Path to worker worktree (e.g., .worktrees/worker-1)'
    )

    args = parser.parse_args()

    # Parse JSON skill dictionary
    try:
        skills_dict = json.loads(args.skill_dict)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON in --skill_dict: {e}"}, indent=2), file=sys.stderr)
        return 1

    # Prepare skills
    result = prepare_skills(skills_dict, args.worktree_path)

    # Print result
    if not result.get("success"):
        print(json.dumps({"success": False, "error": result.get("error", "Unknown error")}, indent=2), file=sys.stderr)
        return 1
    else:
        print(json.dumps(result, indent=2))
        return 0


if __name__ == '__main__':
    sys.exit(main())