import os
import re
import yaml
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional




class SkillLoader:
    def __init__(self):
        # Regex to match H2 headers like "## Header Name"
        self.header_pattern = re.compile(r'(?m)^##\s+(.+?)\s*$')

    def load_bundle(self, skills_dir: str, required_headers: List[str],skill_filename = "SKILL.md") -> str:
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
        
        # 3. Construct Final Output
        final_context = [f"# {frontmatter.get('name', 'Skill')} (Sections: {required_headers})"]
        
        for header in required_headers:
            if header in sections:
                final_context.append(sections[header])
            else:
                # Log warning in production, simplified here
                print(f"Warning: Section '## {header}' not found in text.")

        return "\n\n".join(final_context)

    def _parse_frontmatter(self, content: str) -> tuple[Dict, str]:
        """Separates YAML frontmatter from markdown body."""
        # Pattern matches content between first two --- lines
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if not match:
            # Fallback if no frontmatter found
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
        
        # Split by H2 headers
        # parts will look like: [Pre-text, Header1, Content1, Header2, Content2...]
        parts = self.header_pattern.split(body)
        
        # Skip preamble (text before the first ## header) if strictly header-based
        # or store it if needed. Assuming skills start with ## headers based on your template.
        
        # Iterate in pairs (Header, Content)
        # parts[0] is text before first header (usually empty or description)
        for i in range(1, len(parts), 2):
            header_name = parts[i].strip()
            # Reconstruct the section with the header included for context clarity
            section_content = f"## {header_name}\n{parts[i+1].strip()}"
            sections[header_name] = section_content
            
        return sections

def write_skills(content, output_path):
    """
    Write extracted skill content to a markdown file in the worker's worktree.

    Args:
        content: The concatenated skill context to write
        output_path: Absolute or relative path to output file (e.g., .worktrees/worker-1/worker_skills.md)

    Returns:
        Dict with success status and file path or error message
    """
    try:
        # Convert to path object to check validity
        output_file = Path(output_path)

        # Ensure parent directory exists
        output_file.parent.mkdir(exist_ok=True)

        output_file = os.path.join(output_file, "worker_skills.md")
        # Write content to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "success": True,
            "path": str(Path(output_file).resolve())
        }

    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied writing to: {output_path}"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Destination path invalid for: {output_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write skills file: {str(e)}"
        }


def extract_skills(skills_dict, output_path):
    """
    Extract skill bundles (chunkIDs using ## header) and write to a markdown file on worker branch.

    Args:
        skills_dict: Mapping of skill directory paths to list of wanted segment headers
                     e.g., {"path/to/git-tools": ["Read Tools","Write Tools"]}
        output_path: Path to write the combined skills markdown file

    Returns:
        Dict with success status, output path, and optional error message
    """
    try:
        loader = SkillLoader()
        context_parts = [] 

        #args_dict format = skill folder path: chunk loaded
        for skill_dir, segment_list in skills_dict.items():  
            
            #Load & store skill portion if path valid
            if not os.path.isdir(skill_dir):
                return {
                    "success": False,
                    "error": f"Skill directory not found: {skill_dir}"
                }

            context = loader.load_bundle(skill_dir,segment_list)
            context_parts.append(context)
    
        #concat portions with formatting
        full_context = "\n\n---\n\n".join(context_parts)
        
        
        #write to worker task branch as md file
        write_result = write_skills(full_context, output_path)

        if not write_result["success"]:
            return write_result
    
        return {
            "success": True,
            "skill_summary": full_context,
            "output_path": output_path
        }


    except Exception as e:
        return {
            "error": f"Failed to extract skill segments: {str(e)}",
            "success": False
        }


def main():
    #CLI entry point.
    parser = argparse.ArgumentParser(description='Create relevant worker skills file')
    parser.add_argument('--skill_dict', type=str, required=True, help='JSON dict of skill_dir:header list (e.g., \'{"path/to/git-tools": ["Shared Definitions","Read Tools"]}\')')
    parser.add_argument('--output_path', type=str, required=True, help='Path to write worker md file (e.g., .worktrees/worker-1/worker_skills.md)')
    
    args = parser.parse_args()

    # Parse JSON skill dictionary
    try:
        skills_dict = json.loads(args.skill_dict)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON in --skill-dict: {e}"}, indent=2), file=sys.stderr)
        return 1
    
    #Extract and write to destination
    result = extract_skills(skills_dict,args.output_path)

    # Print result
    if not result.get("success"):
        print(json.dumps({"success": False, "error": result["error"]}, indent=2), file=sys.stderr)
        return 1
    else:
        print(json.dumps({"success": True}, indent=2))
        return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

"""
--- Usage Example ---
#Creates sample worker skills md file for git-tools in utils/skills_test folder based on adapted git_tools SKILL.md file

if __name__ == "__main__":
    # Setup
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_path = os.path.join(script_dir, "utils","skills_test")
    skills_dict = {skills_path: ["Write Tools","Read Tools"]}

    try:
        # Simulate Orchestrator Request
        result = extract_skills(skills_dict,skills_path)
        print(result)
                
    except Exception as e:
        print(f"Error: {e}")
"""