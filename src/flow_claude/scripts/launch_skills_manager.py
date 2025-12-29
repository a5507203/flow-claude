"""Persistent Skill Manager with session resume and caching.

Manages skill extraction for workers using:
1. Session resume pattern for multi-task efficiency
2. Prompt caching for skill catalog and plan metadata
3. Structured extraction workflow
"""
import argparse
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from functools import lru_cache

from claude_agent_sdk import ClaudeAgentOptions, query
from importlib.resources import files






@lru_cache(maxsize=1) #lru_cache to ensure same str passes into system prompt
def load_skills() -> str:
    """Load all SKILL.md files into a single catalog string.

    Returns:
        Concatenated skill content for appended to claude preset
    """
    skills_dir = files('flow_claude').joinpath('templates/skills')
    catalog_parts = ["# Available Skills Catalog\n"]

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding='utf-8')
            catalog_parts.append(f"\n---\n\n## Skill: {skill_dir.name}\n\n{content}")

    return "\n".join(catalog_parts)

@lru_cache(maxsize=1)
def load_workflow() -> str:
    """Load skill-manager.md workflow document.
    """
    return files('flow_claude').joinpath(
        'templates/agents/skill-manager.md'
    ).read_text(encoding='utf-8')



def build_skill_manager_options() -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with cached configurations.
    Returns:
        Configured ClaudeAgentOptions
    """
    # Load skill manager agent prompt
    workflow = load_workflow()
    skill_catalog = load_skills()

    # Build system prompt, appending workflow & concated skills
    system_prompt = {
        "type": "preset",
        "preset": "claude_code",
        "append": f"{workflow}\n\n---\n\n{skill_catalog}"
    }

    # Find Claude CLI path
    import shutil
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
        setting_sources=["user", "project", "local"],
        cli_path= cli_path
    )
    return options


async def extract_skills_for_task(
    plan_branch: str,
    task_branch: str,
    worker_path: str
) -> Dict[str, Any]:
    """Extract skills for a single task.
    Each call gets prompt cache hit if within 5 minutes of previous call

    Args:
        plan_branch: Plan branch for context
        task_branch: Task branch to extract skills for
        worker_path: Worker worktree path for output

    Returns:
        Dict with extraction result
    """
    #tools, system prompt
    options = build_skill_manager_options()  
    
    #user prompt
    prompt = f"""Extract skills for a worker.

**Plan Branch:** {plan_branch}
**Task Branch:** {task_branch}
**Worker Path:** {worker_path}

Follow your workflow:
1. Read .claude/task_summaries.json for previous extractions
2. Read plan metadata for context
3. Read task metadata for requirements
4. Map requirements to skill sections (reference catalog in your context)
5. Run extract_worker_skill with appropriate sections
6. Update task_summaries.json with this extraction

Report completion as JSON when done.
"""
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
    """Sequential skill extraction using caches on system propmpt + skill files.

    First task: Cache WRITE 
    Subsequent tasks: Cache READ 

    Args:
        plan_branch: Plan branch name
        tasks: List of dicts with 'task_branch' and 'worker_path'

    Returns:
        0 for success, 1 if one or more task extractions failed
    """
    has_failure = False

    for i, task in enumerate(tasks):
        print(f"[SkillManager] Processing {task['task_branch']} ({i+1}/{len(tasks)})",
              flush=True)

        result = await extract_skills_for_task(
            plan_branch,
            task['task_branch'],
            task['worker_path']
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