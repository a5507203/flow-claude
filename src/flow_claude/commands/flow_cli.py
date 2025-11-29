"""
Flow CLI - Project Initialization

Initializes a project for Claude Code UI-native autonomous development.
Run once per project to create necessary file structure.
"""

import sys
import json
import shutil
import click
from pathlib import Path


def merge_settings(existing: dict, template: dict) -> dict:
    """Merge template settings into existing settings.

    Args:
        existing: Existing settings dictionary
        template: Template settings dictionary

    Returns:
        Merged settings dictionary
    """
    result = existing.copy()

    # Merge permissions
    if "permissions" in template:
        if "permissions" not in result:
            result["permissions"] = {}

        template_perms = template["permissions"]
        result_perms = result["permissions"]

        # Merge allow list
        if "allow" in template_perms:
            if "allow" not in result_perms:
                result_perms["allow"] = []
            # Add items that don't already exist
            for item in template_perms["allow"]:
                if item not in result_perms["allow"]:
                    result_perms["allow"].append(item)

        # Merge deny list
        if "deny" in template_perms:
            if "deny" not in result_perms:
                result_perms["deny"] = []
            for item in template_perms["deny"]:
                if item not in result_perms["deny"]:
                    result_perms["deny"].append(item)

        # Merge ask list
        if "ask" in template_perms:
            if "ask" not in result_perms:
                result_perms["ask"] = []
            for item in template_perms["ask"]:
                if item not in result_perms["ask"]:
                    result_perms["ask"].append(item)

    # Merge hooks
    if "hooks" in template:
        if "hooks" not in result:
            result["hooks"] = {}

        template_hooks = template["hooks"]
        result_hooks = result["hooks"]

        for hook_name, hook_configs in template_hooks.items():
            if hook_name not in result_hooks:
                result_hooks[hook_name] = hook_configs
            else:
                # Merge hook configurations - add new ones that don't exist
                existing_hooks = result_hooks[hook_name]
                for new_config in hook_configs:
                    # Check if this config already exists (compare by structure)
                    config_exists = False
                    for existing_config in existing_hooks:
                        if json.dumps(new_config, sort_keys=True) == json.dumps(existing_config, sort_keys=True):
                            config_exists = True
                            break
                    if not config_exists:
                        existing_hooks.append(new_config)

    return result


def copy_template_files(project_root: Path) -> dict:
    """Copy template files to project directory.

    Creates .claude/ directory structure and copies all templates.

    Args:
        project_root: Project root directory

    Returns:
        Dict with counts of files copied
    """
    from importlib.resources import files

    # Get templates directory from package
    try:
        # Try to get from installed package
        template_dir = Path(files('flow_claude') / 'templates')
    except Exception:
        # Fallback to relative path (development mode)
        template_dir = Path(__file__).parent.parent / 'templates'

    if not template_dir.exists():
        print(f"ERROR: Templates directory not found: {template_dir}")
        return {"error": "Templates not found"}

    results = {
        "skills": 0,
        "commands": 0,
        "agents": 0,
        "settings": 0
    }

    # Create .claude directory structure
    claude_dir = project_root / '.claude'
    claude_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (claude_dir / 'skills').mkdir(exist_ok=True)
    (claude_dir / 'commands').mkdir(exist_ok=True)
    (claude_dir / 'agents').mkdir(exist_ok=True)

    # Copy skills
    skills_src = template_dir / 'skills'
    if skills_src.exists():
        for skill_dir in skills_src.iterdir():
            if skill_dir.is_dir():
                dest_dir = claude_dir / 'skills' / skill_dir.name
                dest_dir.mkdir(exist_ok=True)

                # Copy SKILL.md (uppercase)
                skill_file = skill_dir / 'SKILL.md'
                if skill_file.exists():
                    shutil.copy(skill_file, dest_dir / 'SKILL.md')
                    results["skills"] += 1

    # Copy commands
    commands_src = template_dir / 'commands'
    if commands_src.exists():
        for cmd_file in commands_src.glob('*.md'):
            shutil.copy(cmd_file, claude_dir / 'commands' / cmd_file.name)
            results["commands"] += 1

    # Copy agents
    agents_src = template_dir / 'agents'
    if agents_src.exists():
        # Copy user.md (default: autonomous mode OFF)
        user_proxy = agents_src / 'user.md'
        if user_proxy.exists():
            shutil.copy(user_proxy, claude_dir / 'agents' / 'user.md')
            results["agents"] += 1

    # Copy or merge settings.local.json to .claude/ directory
    settings_file = template_dir / 'settings.local.json'
    if settings_file.exists():
        dest_settings = claude_dir / 'settings.local.json'
        if not dest_settings.exists():
            # No existing file, just copy
            shutil.copy(settings_file, dest_settings)
            results["settings"] = 1
        else:
            # Existing file - merge template settings into it
            try:
                with open(settings_file, 'r') as f:
                    template_settings = json.load(f)
                with open(dest_settings, 'r') as f:
                    existing_settings = json.load(f)

                merged_settings = merge_settings(existing_settings, template_settings)

                with open(dest_settings, 'w') as f:
                    json.dump(merged_settings, f, indent=2)

                results["settings"] = 2  # 2 indicates merged
            except (json.JSONDecodeError, IOError):
                # If we can't parse/read the existing file, don't overwrite
                results["settings"] = 0
    else:
        results["settings"] = 0

    return results


@click.command()
def main():
    """
    Initialize Flow-Claude for Claude Code UI.

    Creates .claude/ directory structure with skills, commands, and agents.
    Run once per project, then use Claude Code UI for development.
    """
    try:
        from flow_claude.setup_ui import run_setup_ui

        project_root = Path.cwd()

        print("\n>>> Flow-Claude Initialization\n")
        print("=" * 60)

        # Step 1: Run setup UI (flow branch + CLAUDE.md)
        print("\n[1/4] Setting up git repository and flow branch...\n")
        try:
            setup_results = run_setup_ui()

            # Report what was set up
            if setup_results.get("flow_branch_created"):
                base_branch = setup_results.get('base_branch', 'unknown')
                print(f"  [OK] Created 'flow' branch from '{base_branch}'")
            else:
                print("  [OK] Flow branch already exists")

            if setup_results.get("claude_md_generated"):
                status = setup_results.get("claude_md_status", "updated")
                if status == "created":
                    print("  [OK] CLAUDE.md created with Flow-Claude instruction")
                elif status == "updated":
                    print("  [OK] CLAUDE.md updated (instruction prepended)")
                elif status == "unchanged":
                    print("  [OK] CLAUDE.md already has Flow-Claude instruction")

        except Exception as e:
            print(f"  [WARN] Warning: Setup UI encountered an issue: {e}")
            print("  --> Continuing with template file creation...")

        # Step 2: Copy template files
        print("\n[2/4] Creating Claude Code project structure...\n")
        results = copy_template_files(project_root)

        if "error" in results:
            print(f"  [ERROR] Error: {results['error']}")
            sys.exit(1)

        # Summary output
        print(f"  [OK] Created {results['skills']} skills")
        print(f"  [OK] Created {results['commands']} commands")
        print(f"  [OK] Created {results['agents']} agent(s)")
        settings_result = results.get('settings', 0)
        if settings_result == 1:
            print("  [OK] Copied settings.local.json")
        elif settings_result == 2:
            print("  [OK] Merged settings into existing settings.local.json")

        # Step 3: Commit the changes to flow branch
        print("\n[3/4] Committing Flow-Claude configuration to flow branch...\n")
        try:
            import subprocess

            # Check current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, check=True
            )
            current_branch = result.stdout.strip()

            # Switch to flow branch if not already on it
            if current_branch != 'flow':
                print(f"  [INFO] Switching from '{current_branch}' to 'flow' branch...")
                subprocess.run(['git', 'checkout', 'flow'], check=True, capture_output=True)
                print("  [OK] Switched to 'flow' branch")

            # Add all .claude files
            subprocess.run(['git', 'add', '.claude/'], check=True)

            # Commit the changes
            commit_result = subprocess.run(
                ['git', 'commit', '-m', 'Initialize Flow-Claude configuration\n\nAdded .claude/ directory with skills, commands, agents, and settings.'],
                capture_output=True, text=True
            )

            if commit_result.returncode == 0:
                print("  [OK] Committed Flow-Claude configuration to 'flow' branch")
            else:
                # Check if nothing to commit
                if 'nothing to commit' in commit_result.stdout or 'nothing to commit' in commit_result.stderr:
                    print("  [OK] Flow-Claude configuration already committed")
                else:
                    print(f"  [WARN] Could not commit: {commit_result.stderr.strip()}")

        except subprocess.CalledProcessError as e:
            print(f"  [WARN] Git commit failed: {e}")
            print("  --> You can manually commit the .claude/ directory to flow branch")
        except Exception as e:
            print(f"  [WARN] Could not commit changes: {e}")
            print("  --> You can manually commit the .claude/ directory to flow branch")

        # Step 4: Final instructions
        print("\n[4/4] Initialization complete!\n")
        print("=" * 60)
        print("\n[FILES] Project structure created:\n")

        print("[CONFIG] Configuration:\n")
        print("  - Autonomous mode: OFF (type \\auto to toggle)")
        print("  - Max parallel workers: 5 (type \\parallel <N> to change)")
        print("  - Flow branch: 'flow' (all development happens here)")
        print("\n[OK] Initialization complete.\n")
        print("=" * 60)

        print("\n[NEXT] Next steps:\n")
        print("  1. Open this project in Claude Code UI")
        print("  2. Start a chat and describe what you want to build")
        print("  3. The orchestrator will handle the rest!\n")
        print("\n Happy vibe coding!\n")
    except ImportError as e:
        print(f"ERROR: Required module not found: {e}", file=sys.stderr)
        print("Install Flow-Claude with: pip install -e .", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Initialization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
