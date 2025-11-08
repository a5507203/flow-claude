"""Custom MCP tools for git operations in Flow-Claude.

This module provides custom tools for parsing git commits and querying
git metadata. These tools are exposed to Claude agents via the MCP protocol.
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except ImportError:
    # Fallback for development/testing
    def tool(name: str, description: str, schema: Dict[str, Any]):
        """Decorator fallback for when SDK is not installed."""
        def decorator(func):
            func._tool_name = name
            func._tool_description = description
            func._tool_schema = schema
            return func
        return decorator

    def create_sdk_mcp_server(name: str, version: str, tools: list):
        """Fallback MCP server creator."""
        return {"name": name, "version": version, "tools": tools}

from .parsers import (
    parse_commit_message,
    parse_task_metadata,
    parse_plan_commit,
    extract_provides_from_merge_commits,
    parse_worker_commit,
)


@tool("parse_task", "Parse task metadata from the first commit on a task branch", {"branch": str})
async def parse_task(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse task metadata from first commit on task branch.

    This tool reads the initialization commit from a task branch and
    extracts the structured metadata (ID, description, preconditions,
    provides, files, context, etc.)

    Args:
        args: Dictionary with 'branch' key (e.g., "task/001-user-model")

    Returns:
        MCP tool response with parsed metadata as JSON

    Example:
        Input: {"branch": "task/001-user-model"}
        Output: {
            "content": [{
                "type": "text",
                "text": "{\"id\": \"001\", \"description\": \"...\", ...}"
            }]
        }
    """
    branch = args.get("branch", "")

    if not branch:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "Branch name is required"}, indent=2)
            }],
            "isError": True
        }

    try:
        # Get first commit message from branch
        result = subprocess.run(
            ['git', 'log', branch, '--reverse', '--format=%B', '-n', '1'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        # Parse commit message into sections
        sections = parse_commit_message(result.stdout)

        # Extract task metadata
        metadata = parse_task_metadata(sections)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(metadata, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }


@tool("parse_plan", "Parse execution plan from the latest commit on a plan branch", {"branch": str})
async def parse_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse execution plan from latest commit on plan branch.

    This tool reads the most recent commit from a plan branch and
    extracts the execution plan including all tasks, dependencies,
    and estimates.

    Args:
        args: Dictionary with 'branch' key (e.g., "plan/session-20250101-120000")

    Returns:
        MCP tool response with parsed plan as JSON

    Example:
        Input: {"branch": "plan/session-20250101-120000"}
        Output: {
            "content": [{
                "type": "text",
                "text": "{\"session_id\": \"...\", \"tasks\": [...], ...}"
            }]
        }
    """
    branch = args.get("branch", "")

    if not branch:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "Branch name is required"}, indent=2)
            }],
            "isError": True
        }

    try:
        # Get latest commit message from plan branch
        result = subprocess.run(
            ['git', 'log', branch, '--format=%B', '-n', '1'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        # Parse plan commit
        plan = parse_plan_commit(result.stdout)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(plan, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }


@tool("get_provides", "Get list of available preconditions from merged tasks on master branch", {})
async def get_provides(args: Dict[str, Any]) -> Dict[str, Any]:
    """Query master branch merge commits for available provides.

    This tool examines all merge commits on the master branch and
    extracts the "Provides" sections to determine what capabilities
    are currently available for task preconditions.

    Args:
        args: Empty dictionary (no parameters needed)

    Returns:
        MCP tool response with list of available provides

    Example:
        Output: {
            "content": [{
                "type": "text",
                "text": "[\"User model class\", \"User.email field\", ...]"
            }]
        }
    """
    try:
        # Get all merge commit messages from master branch
        result = subprocess.run(
            ['git', 'log', 'master', '--merges', '--format=%B'],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        # Extract all provides
        provides = extract_provides_from_merge_commits(result.stdout)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(provides, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr}",
                    "provides": []
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "provides": []
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "provides": []
                }, indent=2)
            }],
            "isError": True
        }


@tool("parse_worker_commit", "Parse worker's latest commit with design and TODO progress", {"branch": str})
async def parse_worker_commit_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the latest commit on a worker's task branch.

    This tool extracts structured information from worker commits in the
    commit-only architecture where design.md and todo.md are embedded in
    commit messages.

    Args:
        args: Dictionary with 'branch' key (e.g., "task/001-user-model")

    Returns:
        MCP tool response with parsed commit data as JSON

    Example:
        Input: {"branch": "task/001-user-model"}
        Output: {
            "content": [{
                "type": "text",
                "text": "{
                    \"task_id\": \"001\",
                    \"commit_type\": \"implementation\",
                    \"step_number\": 2,
                    \"total_steps\": 6,
                    \"implementation\": \"Added User class with fields\",
                    \"design\": {
                        \"overview\": \"...\",
                        \"architecture_decisions\": [...],
                        \"interfaces_provided\": [...]
                    },
                    \"todo_list\": [
                        {\"number\": 1, \"description\": \"...\", \"completed\": true},
                        {\"number\": 2, \"description\": \"...\", \"completed\": true},
                        {\"number\": 3, \"description\": \"...\", \"completed\": false}
                    ],
                    \"progress\": {
                        \"status\": \"in_progress\",
                        \"completed\": 2,
                        \"total\": 6
                    }
                }"
            }]
        }
    """
    branch = args.get("branch", "")

    if not branch:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "branch parameter is required"}, indent=2)
            }],
            "isError": True
        }

    try:
        # Get latest commit message on the branch
        result = subprocess.run(
            ['git', 'log', branch, '-n', '1', '--format=%B'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        commit_message = result.stdout

        if not commit_message.strip():
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": f"No commits found on branch {branch}"
                    }, indent=2)
                }],
                "isError": True
            }

        # Parse the commit message
        parsed = parse_worker_commit(commit_message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(parsed, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to read commit from branch: {e.stderr}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "branch": branch
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "create_plan_branch",
    "Create plan branch with metadata commit",
    {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "user_request": {"type": "string"},
            "architecture": {"type": "string"},
            "design_patterns": {"type": "string"},
            "technology_stack": {"type": "string"},
            "tasks": {"type": "array"},
            "estimated_total_time": {"type": "string"},
            "dependency_graph": {"type": "string"}
        },
        "required": ["session_id", "user_request", "tasks"]
    }
)
async def create_plan_branch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create plan branch with initial plan commit.

    Creates branch plan/session-{session_id} from master, commits plan metadata
    in exact parsers.py format, and returns to master branch.

    Args:
        args: Dictionary with required fields:
            - session_id: e.g., "session-20250106-140530"
            - user_request: Original user request
            - architecture: Architecture description
            - design_patterns: Design patterns description
            - technology_stack: Technology stack description
            - tasks: List of task dicts with full metadata
            - estimated_total_time: e.g., "45 minutes"
            - dependency_graph: Wave breakdown description

    Returns:
        MCP tool response with success status, branch name, and commit SHA
    """
    session_id = args.get("session_id", "")
    user_request = args.get("user_request", "")
    architecture = args.get("architecture", "")
    design_patterns = args.get("design_patterns", "")
    technology_stack = args.get("technology_stack", "")
    tasks = args.get("tasks", [])
    estimated_total_time = args.get("estimated_total_time", "")
    dependency_graph = args.get("dependency_graph", "")

    # Validate required fields
    if not session_id:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "session_id is required"}, indent=2)}],
            "isError": True
        }
    if not user_request:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "user_request is required"}, indent=2)}],
            "isError": True
        }
    if not tasks:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "tasks list is required"}, indent=2)}],
            "isError": True
        }

    branch_name = f"plan/{session_id}"

    try:
        # Validate this is a git repository
        repo_check = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True,
            timeout=5
        )
        if repo_check.returncode != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "Not a git repository",
                        "hint": "The current directory is not initialized as a git repository.",
                        "action_required": "Initialize git repository first: git init",
                        "current_directory": str(Path.cwd())
                    }, indent=2)
                }],
                "isError": True
            }

        # Check if branch already exists
        check_result = subprocess.run(
            ['git', 'rev-parse', '--verify', branch_name],
            capture_output=True,
            timeout=5
        )
        if check_result.returncode == 0:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Branch {branch_name} already exists",
                        "hint": "Use a different session_id or delete the existing branch first"
                    }, indent=2)
                }],
                "isError": True
            }

        # Store current branch to return to it later
        current_branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        current_branch = current_branch_result.stdout.strip() or "master"

        # Create plan branch from master (force checkout master first)
        subprocess.run(
            ['git', 'checkout', '-f', 'master'],
            capture_output=True,
            check=True,
            timeout=10
        )
        subprocess.run(
            ['git', 'checkout', '-b', branch_name],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Copy instruction files from flow_claude/prompts/
        prompts_dir = Path(__file__).parent / "prompts"
        instruction_files = [
            ("orchestrator.md", "ORCHESTRATOR_INSTRUCTIONS.md"),
            ("planner.md", "PLANNER_INSTRUCTIONS.md"),
            ("worker.md", "WORKER_INSTRUCTIONS.md"),
            ("user.md", "USER_PROXY_INSTRUCTIONS.md")
        ]

        copied_files = []
        for source_file, dest_file in instruction_files:
            source_path = prompts_dir / source_file
            if source_path.exists():
                shutil.copy2(source_path, dest_file)
                copied_files.append(dest_file)
            else:
                # Rollback on error
                subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
                subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "error": f"Source file not found: {source_path}",
                            "rollback": "Branch creation rolled back"
                        }, indent=2)
                    }],
                    "isError": True
                }

        # Stage instruction files
        subprocess.run(
            ['git', 'add'] + copied_files,
            capture_output=True,
            check=True,
            timeout=10
        )

        # Build plan commit message
        from datetime import datetime
        created_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build tasks section
        tasks_section = ""
        for task in tasks:
            task_id = task.get("id", "")
            description = task.get("description", "")
            status = task.get("status", "pending")
            preconditions = task.get("preconditions", [])
            provides = task.get("provides", [])
            files = task.get("files", [])
            estimated_time = task.get("estimated_time", "")
            priority = task.get("priority", "medium")

            tasks_section += f"\n### Task {task_id}\n"
            tasks_section += f"ID: {task_id}\n"
            tasks_section += f"Description: {description}\n"
            tasks_section += f"Status: {status}\n"

            if preconditions:
                tasks_section += "Preconditions:\n"
                for pre in preconditions:
                    tasks_section += f"  - {pre}\n"
            else:
                tasks_section += "Preconditions: []\n"

            if provides:
                tasks_section += "Provides:\n"
                for prov in provides:
                    tasks_section += f"  - {prov}\n"
            else:
                tasks_section += "Provides: []\n"

            if files:
                tasks_section += "Files:\n"
                for file in files:
                    tasks_section += f"  - {file}\n"

            tasks_section += f"Estimated Time: {estimated_time}\n"
            tasks_section += f"Priority: {priority}\n"

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")

        commit_message = f"""Initialize execution plan v1

## Session Information
Session ID: {session_id}
User Request: {user_request}
Created: {created_timestamp}
Plan Branch: {branch_name}
Plan Version: v1

## Architecture
{architecture}

## Design Patterns
{design_patterns}

## Technology Stack
{technology_stack}

## Tasks{tasks_section}

## Estimates
Estimated Total Time: {estimated_total_time}
Total Tasks: {total_tasks}
Completed: {completed_tasks}/{total_tasks} tasks

## Dependency Graph
{dependency_graph}
"""

        # Create plan commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Get commit SHA
        commit_sha_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        commit_sha = commit_sha_result.stdout.strip()

        # Return to original branch
        subprocess.run(
            ['git', 'checkout', current_branch],
            capture_output=True,
            check=True,
            timeout=10
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "branch_name": branch_name,
                    "commit_sha": commit_sha
                }, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "create_task_branch",
    "Create task branch with metadata commit",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "branch_slug": {"type": "string"},
            "description": {"type": "string"},
            "preconditions": {"type": "array"},
            "provides": {"type": "array"},
            "files": {"type": "array"},
            "session_goal": {"type": "string"},
            "session_id": {"type": "string"},
            "plan_branch": {"type": "string"},
            "plan_version": {"type": "string"},
            "depends_on": {"type": "array"},
            "enables": {"type": "array"},
            "parallel_with": {"type": "array"},
            "completed_tasks": {"type": "array"},
            "estimated_time": {"type": "string"},
            "priority": {"type": "string"}
        },
        "required": ["task_id", "branch_slug", "description", "preconditions", "provides", "files", "session_goal", "session_id", "plan_branch", "plan_version"]
    }
)
async def create_task_branch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create task branch with task metadata commit.

    Creates branch task/{task_id}-{branch_slug} from master, commits task metadata
    in exact parsers.py format, and returns to master branch.

    Args:
        args: Dictionary with required fields:
            - task_id: e.g., "001"
            - branch_slug: e.g., "user-model"
            - description: Task description
            - preconditions: List of precondition strings
            - provides: List of capability strings
            - files: List of file paths
            - session_goal: Overall session goal
            - session_id: e.g., "session-20250106-140530"
            - plan_branch: e.g., "plan/session-20250106-140530"
            - plan_version: e.g., "v1"
            - depends_on: List of task dependencies
            - enables: List of tasks this enables
            - parallel_with: List of parallel tasks
            - completed_tasks: List of completed task IDs
            - estimated_time: e.g., "8 minutes"
            - priority: e.g., "high"

    Returns:
        MCP tool response with success status, branch name, and commit SHA
    """
    task_id = args.get("task_id", "")
    branch_slug = args.get("branch_slug", "")
    description = args.get("description", "")
    preconditions = args.get("preconditions", [])
    provides = args.get("provides", [])
    files = args.get("files", [])
    session_goal = args.get("session_goal", "")
    session_id = args.get("session_id", "")
    plan_branch = args.get("plan_branch", "")
    plan_version = args.get("plan_version", "v1")
    depends_on = args.get("depends_on", [])
    enables = args.get("enables", [])
    parallel_with = args.get("parallel_with", [])
    completed_tasks = args.get("completed_tasks", [])
    estimated_time = args.get("estimated_time", "")
    priority = args.get("priority", "medium")

    # Validate required fields
    if not task_id:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "task_id is required"}, indent=2)}],
            "isError": True
        }
    if not branch_slug:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "branch_slug is required"}, indent=2)}],
            "isError": True
        }
    if not description:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "description is required"}, indent=2)}],
            "isError": True
        }

    branch_name = f"task/{task_id}-{branch_slug}"

    try:
        # Check if branch already exists
        check_result = subprocess.run(
            ['git', 'rev-parse', '--verify', branch_name],
            capture_output=True,
            timeout=5
        )
        if check_result.returncode == 0:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Branch {branch_name} already exists",
                        "hint": "Use a different task_id or branch_slug, or delete the existing branch first"
                    }, indent=2)
                }],
                "isError": True
            }

        # Store current branch to return to it later
        current_branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        current_branch = current_branch_result.stdout.strip() or "master"

        # Create task branch from master (force checkout master first)
        subprocess.run(
            ['git', 'checkout', '-f', 'master'],
            capture_output=True,
            check=True,
            timeout=10
        )
        subprocess.run(
            ['git', 'checkout', '-b', branch_name],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Copy instruction files from flow_claude/prompts/
        prompts_dir = Path(__file__).parent / "prompts"
        instruction_files = [
            ("orchestrator.md", "ORCHESTRATOR_INSTRUCTIONS.md"),
            ("planner.md", "PLANNER_INSTRUCTIONS.md"),
            ("worker.md", "WORKER_INSTRUCTIONS.md"),
            ("user.md", "USER_PROXY_INSTRUCTIONS.md")
        ]

        copied_files = []
        for source_file, dest_file in instruction_files:
            source_path = prompts_dir / source_file
            if source_path.exists():
                shutil.copy2(source_path, dest_file)
                copied_files.append(dest_file)
            else:
                # Rollback on error
                subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
                subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "error": f"Source file not found: {source_path}",
                            "rollback": "Branch creation rolled back"
                        }, indent=2)
                    }],
                    "isError": True
                }

        # Stage instruction files
        subprocess.run(
            ['git', 'add'] + copied_files,
            capture_output=True,
            check=True,
            timeout=10
        )

        # Build preconditions section
        preconditions_section = ""
        if preconditions:
            preconditions_section = "Preconditions:\n"
            for pre in preconditions:
                preconditions_section += f"  - {pre}\n"
        else:
            preconditions_section = "Preconditions: []\n"

        # Build provides section
        provides_section = ""
        if provides:
            provides_section = "Provides:\n"
            for prov in provides:
                provides_section += f"  - {prov}\n"
        else:
            provides_section = "Provides: []\n"

        # Build files section
        files_section = ""
        if files:
            files_section = "Files to modify:\n"
            for file in files:
                files_section += f"  - {file}\n"
        else:
            files_section = "Files to modify: []\n"

        # Build context section
        depends_on_str = str(depends_on) if depends_on else "[]"
        enables_str = str(enables) if enables else "[]"
        parallel_with_str = str(parallel_with) if parallel_with else "[]"
        completed_tasks_str = str(completed_tasks) if completed_tasks else "[]"

        commit_message = f"""Initialize task/{task_id}-{branch_slug}

## Task Metadata
ID: {task_id}
Description: {description}
Status: pending

## Dependencies
{preconditions_section}
{provides_section}

## Files
{files_section}

## Context
Session Goal: {session_goal}
Session ID: {session_id}
Plan Branch: {plan_branch}
Plan Version: {plan_version}
Depends on: {depends_on_str}
Enables: {enables_str}
Parallel with: {parallel_with_str}
Completed Tasks: {completed_tasks_str}

## Estimates
Estimated Time: {estimated_time}
Priority: {priority}
"""

        # Create task metadata commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Get commit SHA
        commit_sha_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        commit_sha = commit_sha_result.stdout.strip()

        # Return to original branch
        subprocess.run(
            ['git', 'checkout', current_branch],
            capture_output=True,
            check=True,
            timeout=10
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "branch_name": branch_name,
                    "commit_sha": commit_sha
                }, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        # Attempt rollback
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)
        subprocess.run(['git', 'branch', '-D', branch_name], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "rollback": "Attempted to rollback branch creation"
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "update_plan_branch",
    "Update plan commit with completed tasks and new wave tasks",
    {
        "type": "object",
        "properties": {
            "plan_branch": {"type": "string"},
            "completed_task_ids": {"type": "array"},
            "new_tasks": {"type": "array"},
            "architecture_updates": {"type": "string"}
        },
        "required": ["plan_branch"]
    }
)
async def update_plan_branch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update plan branch with completed task status and new wave tasks.

    This tool updates an existing plan branch by:
    1. Checking out plan branch
    2. Parsing current plan commit
    3. Marking tasks as completed
    4. Appending architecture learnings
    5. Adding new wave tasks
    6. Creating new plan commit with incremented version
    7. Returning to original branch

    Args:
        args: Dictionary with fields:
            - plan_branch: e.g., "plan/session-20250106-140530"
            - completed_task_ids: List of task IDs to mark complete (optional)
            - new_tasks: List of new task dicts (optional)
            - architecture_updates: Additional learnings to append (optional)

    Returns:
        MCP tool response with success status, plan version, and commit SHA
    """
    plan_branch = args.get("plan_branch", "")
    completed_task_ids = args.get("completed_task_ids", [])
    new_tasks = args.get("new_tasks", [])
    architecture_updates = args.get("architecture_updates", "")

    # Validate required fields
    if not plan_branch:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": "plan_branch is required"}, indent=2)}],
            "isError": True
        }

    try:
        # Store current branch to return to it later
        current_branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        current_branch = current_branch_result.stdout.strip() or "main"

        # Checkout plan branch
        subprocess.run(
            ['git', 'checkout', plan_branch],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Get current plan commit
        commit_result = subprocess.run(
            ['git', 'log', '-n', '1', '--format=%B'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        # Parse current plan
        current_plan = parse_plan_commit(commit_result.stdout)

        # Determine new version by counting commits on plan branch
        version_result = subprocess.run(
            ['git', 'rev-list', '--count', plan_branch],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        commit_count = int(version_result.stdout.strip())
        new_version = f"v{commit_count + 1}"

        # Update task statuses
        tasks = current_plan.get("tasks", [])
        for task in tasks:
            if task.get("id") in completed_task_ids:
                task["status"] = "completed"

        # Add new tasks if provided
        if new_tasks:
            tasks.extend(new_tasks)

        # Update architecture with learnings
        architecture = current_plan.get("architecture", "")
        if architecture_updates:
            architecture += f"\n\n### Learnings from Wave {commit_count}:\n{architecture_updates}"

        # Calculate stats
        total_tasks = len(tasks)
        completed_count = sum(1 for t in tasks if t.get("status") == "completed")

        # Build tasks section
        tasks_section = ""
        for task in tasks:
            task_id = task.get("id", "")
            description = task.get("description", "")
            status = task.get("status", "pending")
            preconditions = task.get("preconditions", [])
            provides = task.get("provides", [])
            files = task.get("files", [])
            estimated_time = task.get("estimated_time", "")
            priority = task.get("priority", "medium")

            tasks_section += f"\n### Task {task_id}\n"
            tasks_section += f"ID: {task_id}\n"
            tasks_section += f"Description: {description}\n"
            tasks_section += f"Status: {status}\n"

            if preconditions:
                tasks_section += "Preconditions:\n"
                for pre in preconditions:
                    tasks_section += f"  - {pre}\n"
            else:
                tasks_section += "Preconditions: []\n"

            if provides:
                tasks_section += "Provides:\n"
                for prov in provides:
                    tasks_section += f"  - {prov}\n"
            else:
                tasks_section += "Provides: []\n"

            if files:
                tasks_section += "Files:\n"
                for file in files:
                    tasks_section += f"  - {file}\n"

            tasks_section += f"Estimated Time: {estimated_time}\n"
            tasks_section += f"Priority: {priority}\n"

        # Build updated plan commit
        from datetime import datetime
        created_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        commit_message = f"""Update execution plan {new_version}

## Session Information
Session ID: {current_plan.get('session_id', '')}
User Request: {current_plan.get('user_request', '')}
Created: {created_timestamp}
Plan Branch: {plan_branch}
Plan Version: {new_version}

## Architecture
{architecture}

## Design Patterns
{current_plan.get('design_patterns', '')}

## Technology Stack
{current_plan.get('technology_stack', '')}

## Tasks{tasks_section}

## Estimates
Estimated Total Time: {current_plan.get('estimated_total_time', '')}
Total Tasks: {total_tasks}
Completed: {completed_count}/{total_tasks} tasks

## Dependency Graph
{current_plan.get('dependency_graph', '')}
"""

        # Create update commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            capture_output=True,
            check=True,
            timeout=10
        )

        # Get commit SHA
        commit_sha_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        commit_sha = commit_sha_result.stdout.strip()

        # Return to original branch
        subprocess.run(
            ['git', 'checkout', current_branch],
            capture_output=True,
            check=True,
            timeout=10
        )

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "plan_version": new_version,
                    "commit_sha": commit_sha,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_count
                }, indent=2)
            }]
        }

    except subprocess.CalledProcessError as e:
        # Attempt to return to original branch
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
                    "plan_branch": plan_branch
                }, indent=2)
            }],
            "isError": True
        }
    except subprocess.TimeoutExpired:
        # Attempt to return to original branch
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Git command timed out",
                    "plan_branch": plan_branch
                }, indent=2)
            }],
            "isError": True
        }
    except Exception as e:
        # Attempt to return to original branch
        subprocess.run(['git', 'checkout', current_branch], capture_output=True, timeout=5)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unexpected error: {str(e)}",
                    "plan_branch": plan_branch
                }, indent=2)
            }],
            "isError": True
        }


def create_git_tools_server():
    """Create MCP server with git parsing tools.

    Returns:
        MCP server instance with git tools

    Usage:
        In CLI setup:
            options = ClaudeAgentOptions(
                mcp_servers={"git": create_git_tools_server()},
                ...
            )

        Agents can then use:
            - mcp__git__parse_task: Parse task metadata from branch commit
            - mcp__git__parse_plan: Parse plan data from plan branch commit (commit-only)
            - mcp__git__get_provides: Query completed task capabilities from main
            - mcp__git__parse_worker_commit: Parse worker's latest commit (design + TODO progress)
            - mcp__git__create_plan_branch: Create plan branch with instruction files and metadata
            - mcp__git__create_task_branch: Create task branch with instruction files and metadata
            - mcp__git__update_plan_branch: Update plan with completed tasks and new wave tasks
    """
    return create_sdk_mcp_server(
        name="git",
        version="1.0.0",
        tools=[
            parse_task,
            parse_plan,
            get_provides,
            parse_worker_commit_tool,
            create_plan_branch,
            create_task_branch,
            update_plan_branch
        ]
    )
