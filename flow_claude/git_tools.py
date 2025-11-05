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


@tool("read_plan_file", "Read a file from the current plan branch (e.g., plan.md, system-overview.md)", {"file_name": str})
async def read_plan_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read a file from the current plan branch.

    NEW in V6.2: Plan branches now contain actual MD files instead of just
    commit messages. This tool reads those files.

    Args:
        args: Dictionary with 'file_name' key (e.g., "plan.md", "system-overview.md")

    Returns:
        MCP tool response with file contents as text

    Example:
        Input: {"file_name": "plan.md"}
        Output: {
            "content": [{
                "type": "text",
                "text": "# Execution Plan v1\n\n..."
            }]
        }
    """
    file_name = args.get("file_name", "")

    # Validate file_name (handle empty strings and whitespace)
    if not file_name or not file_name.strip():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "file_name is required (cannot be empty or whitespace)"}, indent=2)
            }],
            "isError": True
        }

    try:
        # Get current plan branch from git config
        result = subprocess.run(
            ['git', 'config', '--local', 'flow-claude.current-plan'],
            capture_output=True,
            text=True,
            check=False,  # Don't raise on non-zero exit (config might not exist)
            timeout=5
        )

        plan_branch = result.stdout.strip()

        if not plan_branch:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "No active plan branch found",
                        "hint": "Planning agent should set 'flow-claude.current-plan' config"
                    }, indent=2)
                }],
                "isError": True
            }

        # Read file from plan branch
        result = subprocess.run(
            ['git', 'show', f'{plan_branch}:{file_name}'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        return {
            "content": [{
                "type": "text",
                "text": result.stdout
            }]
        }

    except subprocess.CalledProcessError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to read file from plan branch: {e.stderr}",
                    "file_name": file_name,
                    "plan_branch": plan_branch if 'plan_branch' in locals() else "unknown"
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
                    "file_name": file_name
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
                    "file_name": file_name
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
            - mcp__git__parse_task
            - mcp__git__parse_plan
            - mcp__git__get_provides
            - mcp__git__read_plan_file (NEW in V6.2)
    """
    return create_sdk_mcp_server(
        name="git",
        version="1.0.0",
        tools=[parse_task, parse_plan, get_provides, read_plan_file]
    )
