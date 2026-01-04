"""Persistent Skill Manager with session resume and caching.

Manages skill extraction for workers using:
1. Session resume pattern for multi-task efficiency
2. Prompt caching for skill catalog and plan metadata
3. Structured extraction workflow
4. Native Claude Code skill discovery via .claude/skills/
"""
import argparse
import asyncio
import json
import sys
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
from functools import lru_cache

from claude_agent_sdk import ClaudeAgentOptions, query
from importlib.resources import files


def get_project_root() -> Path:
    """Find project root by looking for .claude directory or .git.

    Returns:
        Path to project root, or current directory if not found
    """
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / '.claude').exists() or (parent / '.git').exists():
            return parent
    return current


@lru_cache(maxsize=1)
def load_workflow() -> str:
    """Load skill-manager.md workflow document."""
    return files('flow_claude').joinpath(
        'templates/agents/skill-manager.md'
    ).read_text(encoding='utf-8')


def build_skill_manager_options(project_root: Path) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with cached configurations.

    Skills are discovered via native Claude Code mechanism from .claude/skills/
    relative to project_root. Skill descriptions are loaded into context
    automatically by Claude Code.

    Args:
        project_root: Project root directory (contains .claude/skills/)

    Returns:
        Configured ClaudeAgentOptions

    Note:
        Workflow file (~10KB) is embedded in system prompt. This exceeds
        Windows cmd.exe limit (8KB) but is under CreateProcess limit (32KB).
        If issues occur on Windows, consider file-based workflow loading.
    """
    # Load workflow into system prompt
    # Skills are discovered automatically from .claude/skills/ via setting_sources
    workflow = load_workflow()
    system_prompt = {
        "type": "preset",
        "preset": "claude_code",
        "append": workflow
    }

    # Find Claude CLI path
    cli_path = shutil.which('claude')
    if not cli_path and os.name == 'nt':  # Windows fallback
        cli_path = shutil.which('claude.cmd')

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=[
            'Bash', 'Glob', 'Grep', 'Read', 'Write',
            'TodoWrite'  # Progress tracking
        ],
        permission_mode='acceptEdits',
        # "project" enables skill discovery from .claude/skills/
        setting_sources=["user", "project", "local"],
        # Set cwd to project root so Claude Code finds .claude/skills/
        cwd=str(project_root),
        cli_path=cli_path
    )
    return options


async def extract_skills_for_task(
    plan_branch: str,
    task_branch: str,
    worker_path: str,
    project_root: Path
) -> Dict[str, Any]:
    """Extract skills for a single task.
    Each call gets prompt cache hit if within 5 minutes of previous call

    Args:
        plan_branch: Plan branch for context
        task_branch: Task branch to extract skills for
        worker_path: Worker worktree path for output
        project_root: Project root directory for skill discovery

    Returns:
        Dict with extraction result
    """
    # Build options with project root for skill discovery
    options = build_skill_manager_options(project_root)  
    
    #user prompt
    prompt = f"Prepare skills for worker. Plan: {plan_branch}, Task: {task_branch}, Worker: {worker_path}. Follow workflow: read task_summaries.json, read plan/task metadata, map to skills, run prepare_worker_skills, update task_summaries.json. Report as JSON."
    
    try:
        result_data = None
        cache_info = {"read": 0, "write": 0}

        #Run agent (match skills, write to worker branch, update summary JSON)
        async for message in query(prompt=prompt, options=options):
            # Track cache performance
            if hasattr(message, 'usage'): #Either from assistantmessage or resultsmessage
                cache_info["read"] = message.usage.get('cache_read_input_tokens', 0)
                cache_info["write"] = message.usage.get('cache_creation_input_tokens', 0)

            # Look for completion JSON (after agent completes workflow for task)
            if hasattr(message, 'content'): #no user, so only assistantmessage
                for block in message.content:
                    if hasattr(block, 'text') and '"success"' in block.text: #designated output in text block(text, tool, thinking)
                        try: #Scan for JSON formatting in text
                            import re
                            json_match = re.search(r'\{[^{}]*"success"[^{}]*\}',
                                                   block.text, re.DOTALL)
                            if json_match:
                                result_data = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass

        # Log cache performance
        if cache_info["read"] > 0:
            print(f"[SkillManager] Cache HIT: {cache_info['read']} tokens", flush=True)
        if cache_info["write"] > 0:
            print(f"[SkillManager] Cache WRITE: {cache_info['write']} tokens", flush=True)

        return {
            "success": True,
            "task_branch": task_branch,
            "worker_path": worker_path,
            "extraction": result_data,
            "cache": cache_info
        }

    except Exception as e:
        return {
            "success": False,
            "task_branch": task_branch,
            "error": f"Extraction failed: {e}"
        }
        
async def extract_skills_batch(
    plan_branch: str,
    tasks: List[Dict[str, str]],
) -> bool:
    """Sequential skill extraction using caches on system prompt + skill files.

    First task: Cache WRITE
    Subsequent tasks: Cache READ

    Args:
        plan_branch: Plan branch name
        tasks: List of dicts with 'task_branch' and 'worker_path'

    Returns:
        0 for success, 1 if one or more task extractions failed
    """
    has_failure = False
    project_root = get_project_root()
    print(f"[SkillManager] Project root: {project_root}", flush=True)

    for i, task in enumerate(tasks):
        print(f"[SkillManager] Processing {task['task_branch']} ({i+1}/{len(tasks)})",
              flush=True)

        result = await extract_skills_for_task(
            plan_branch,
            task['task_branch'],
            task['worker_path'],
            project_root
        )
        
        #Print NDJSON for orchestrator to launch worker
        print(json.dumps(result), flush=True)

        if not result.get("success"):
            has_failure = True
    
    return 1 if has_failure else 0

def main():
    """CLI entry point"""

    parser = argparse.ArgumentParser(
        description='Launch Skill Manager agent with prompt caching'
    )
    parser.add_argument('--plan-branch', required=True,
                              help='Plan branch name')
    parser.add_argument('--tasks', required=True,
                              help='JSON array of {task_branch, worker_path}')
    args = parser.parse_args()

    tasks = json.loads(args.tasks)
    result = asyncio.run(extract_skills_batch(args.plan_branch, tasks))
    print(json.dumps(result, indent=2))

    return 0

if __name__ == '__main__':
    sys.exit(main())