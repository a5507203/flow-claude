"""
Flow CLI - Project Initialization

Initializes a project for Claude Code UI-native autonomous development.
Run once per project to create necessary file structure.
"""

import sys
import shutil
import click
from pathlib import Path


def copy_template_files(project_root: Path, verbose: bool = False) -> dict:
    """Copy template files to project directory.

    Creates .claude/ directory structure and copies all templates.

    Args:
        project_root: Project root directory
        verbose: Print detailed progress

    Returns:
        Dict with counts of files copied
    """
    import pkg_resources

    # Get templates directory from package
    try:
        # Try to get from installed package
        template_dir = Path(pkg_resources.resource_filename('flow_claude', 'templates'))
    except:
        # Fallback to relative path (development mode)
        template_dir = Path(__file__).parent.parent / 'templates'

    if not template_dir.exists():
        print(f"ERROR: Templates directory not found: {template_dir}")
        return {"error": "Templates not found"}

    results = {
        "skills": 0,
        "commands": 0,
        "agents": 0
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
                    if verbose:
                        print(f"  [OK] Copied skill: {skill_dir.name}")

    # Copy commands
    commands_src = template_dir / 'commands'
    if commands_src.exists():
        for cmd_file in commands_src.glob('*.md'):
            shutil.copy(cmd_file, claude_dir / 'commands' / cmd_file.name)
            results["commands"] += 1
            if verbose:
                print(f"  [OK] Copied command: {cmd_file.stem}")

    # Copy agents
    agents_src = template_dir / 'agents'
    if agents_src.exists():
        # Copy user.md (default: autonomous mode OFF)
        user_proxy = agents_src / 'user.md'
        if user_proxy.exists():
            shutil.copy(user_proxy, claude_dir / 'agents' / 'user.md')
            results["agents"] += 1
            if verbose:
                print(f"  [OK] Copied agent: user")

    return results


def create_claude_md_template(project_root: Path) -> bool:
    """Create minimal CLAUDE.md template if it doesn't exist.

    Args:
        project_root: Project root directory

    Returns:
        True if file was created, False if already exists
    """
    claude_md = project_root / 'CLAUDE.md'

    if claude_md.exists():
        return False

    content = """# Project AI Assistant

This project uses Flow-Claude for autonomous development.

## How to Use

Simply describe your development request in Claude Code chat:

```
"Add user authentication with JWT"
"Implement email validation"
"Create API endpoint for user profile"
```

The orchestrator will automatically:
1. Analyze your request
2. Create an execution plan
3. Decompose into tasks
4. Execute tasks in parallel
5. Merge results to flow branch

## Architecture

Flow-Claude uses a git-first architecture where:
- **Plans** are stored as structured git commits
- **Tasks** are executed on separate branches
- **Workers** run in parallel git worktrees
- **State** is tracked through commit history

## Skills

This project has access to the following skills:

### Orchestrator Skill
Main coordination logic for autonomous development.
Location: `.claude/skills/orchestrator/skill.md`

### Git Tools Skill
Provides 7 tools for git-based state management.
Location: `.claude/skills/git-tools/skill.md`

### SDK Workers Skill
Manages worker agents and MCP configuration.
Location: `.claude/skills/sdk-workers/skill.md`

## Configuration

### Autonomous Mode
Toggle with `\\auto` command:
- **OFF** (default): Asks for confirmation before executing
- **ON**: Executes plans automatically

Controlled by `.claude/agents/user.md` existence.

### Max Parallel Workers
Set with `\\parallel <1-10>` command.

Default: 3 workers
Location: `.claude/skills/orchestrator/skill.md` (YAML frontmatter)

## Workflow

When you make a development request:

1. Orchestrator analyzes request
2. Creates plan branch (`plan/session-*`)
3. Creates task branches (`task/*`)
4. Spawns workers in git worktrees
5. Workers execute tasks in parallel
6. Results merge to `flow` branch

## Branches

- `main/master`: Production code
- `flow`: Development base (created by `flow` init)
- `plan/session-*`: Execution plans
- `task/*`: Individual tasks

## Commands

- `\\auto`: Toggle autonomous mode
- `\\parallel <N>`: Set max parallel workers (1-10)

## External MCP Tools

Workers can access external MCP servers defined in `.mcp.json`.

Example:
```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "@playwright/mcp@latest"]
    }
  }
}
```

Orchestrator creates dynamic worker agents (worker-01.md, worker-02.md, etc.) in `.claude/agents/` when needed, granting them access to required tools.

---

**Ready to start?** Just describe what you want to build!
"""

    claude_md.write_text(content, encoding='utf-8')
    return True


@click.command()
@click.option('--verbose', is_flag=True,
              help='Show detailed progress')
def main(verbose):
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
        print("\n[1/3] Setting up git repository and flow branch...\n")
        try:
            setup_results = run_setup_ui()

            # Report what was set up
            if setup_results.get("flow_branch_created"):
                base_branch = setup_results.get('base_branch', 'unknown')
                print(f"  [OK] Created 'flow' branch from '{base_branch}'")

            if setup_results.get("claude_md_generated"):
                print("  [OK] CLAUDE.md generated and committed to flow branch")
            elif not setup_results.get("claude_md_generated"):
                # Setup UI might not have generated CLAUDE.md
                # Create minimal template ourselves
                if create_claude_md_template(project_root):
                    print("  [OK] CLAUDE.md created (minimal template)")

            if not setup_results.get("flow_branch_created") and not setup_results.get("claude_md_generated"):
                print("  [OK] Flow branch and CLAUDE.md already exist")

        except Exception as e:
            print(f"  [WARN] Warning: Setup UI encountered an issue: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            print("  --> Continuing with template file creation...")

        # Step 2: Copy template files
        print("\n[2/3] Creating Claude Code project structure...\n")
        results = copy_template_files(project_root, verbose=verbose)

        if "error" in results:
            print(f"  [ERROR] Error: {results['error']}")
            sys.exit(1)

        if not verbose:
            # Summary output
            print(f"  [OK] Created {results['skills']} skills")
            print(f"  [OK] Created {results['commands']} commands")
            print(f"  [OK] Created {results['agents']} agent(s)")

        # Step 3: Final instructions
        print("\n[3/3] Initialization complete!\n")
        print("=" * 60)
        print("\n[FILES] Project structure created:\n")
        print("  .claude/")
        print("    |-- skills/")
        print("    |   |-- git-tools/       # Git state management")
        print("    |   |-- sdk-workers/     # Worker coordination")
        print("    |   +-- orchestrator/    # Main orchestrator")
        print("    |-- commands/")
        print("    |   |-- auto.md          # Toggle autonomous mode")
        print("    |   +-- parallel.md      # Set max workers")
        print("    +-- agents/")
        print("        +-- user.md    # User confirmation agent")
        print("  CLAUDE.md                   # Main project instructions")

        print("\n[NEXT] Next steps:\n")
        print("  1. Open this project in Claude Code UI")
        print("  2. Start a chat and describe what you want to build")
        print("  3. The orchestrator will handle the rest!\n")

        print("[CONFIG] Configuration:\n")
        print("  - Autonomous mode: OFF (type \\auto to toggle)")
        print("  - Max parallel workers: 3 (type \\parallel <N> to change)")
        print("  - Flow branch: 'flow' (all development happens here)")

        print("\n[EXAMPLE] Example request:\n")
        print('  "Add user authentication with JWT and bcrypt"\n')

        print("=" * 60)
        print("\n[OK] Initialization complete. Happy coding!\n")

    except ImportError as e:
        print(f"ERROR: Required module not found: {e}", file=sys.stderr)
        print("Install Flow-Claude with: pip install -e .", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Initialization failed: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
