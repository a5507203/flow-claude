"""Custom MCP tools for git operations in Flow-Claude.

This module provides custom tools for parsing git commits and querying
git metadata. These tools are exposed to Claude agents via the MCP protocol.
"""

import subprocess
import json
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


@tool("get_provides", "Get list of available preconditions from merged tasks on main branch", {})
async def get_provides(args: Dict[str, Any]) -> Dict[str, Any]:
    """Query main branch merge commits for available provides.

    This tool examines all merge commits on the main branch and
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
        # Get all merge commit messages from main branch
        result = subprocess.run(
            ['git', 'log', 'main', '--merges', '--format=%B'],
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
    """
    return create_sdk_mcp_server(
        name="git",
        version="1.0.0",
        tools=[parse_task, parse_plan, get_provides, parse_worker_commit_tool]
    )
