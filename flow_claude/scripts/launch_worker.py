"""SDK-based worker management for flow-claude.

This module provides worker management using Claude SDK's query() function
for parallel task execution.
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List, AsyncGenerator, Optional

# Fix Windows console encoding for Unicode support
if sys.platform == 'win32':
    import io
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, query, tool, create_sdk_mcp_server
from flow_claude.utils.mcp_loader import load_project_mcp_config


def extract_mcp_server_names(allowed_tools: List[str]) -> set:
    """Extract MCP server names from tool names.

    MCP tool names follow the pattern: mcp__<servername>__<toolname>

    Args:
        allowed_tools: List of tool names that may include MCP tools

    Returns:
        Set of unique MCP server names extracted from tool names

    Example:
        >>> extract_mcp_server_names(['mcp__playwright__screenshot', 'mcp__playwright__navigate'])
        {'playwright'}

        >>> extract_mcp_server_names(['mcp__custom__action', 'mcp__other__tool', 'Bash'])
        {'custom', 'other'}
    """
    server_names = set()

    for tool in allowed_tools:
        # Check if it's an MCP tool (starts with 'mcp__')
        if tool.startswith('mcp__'):
            # Split by '__' and extract server name (second part)
            parts = tool.split('__')
            if len(parts) >= 3:  # mcp__servername__toolname
                server_name = parts[1]
                server_names.add(server_name)

    return server_names


def build_worker_mcp_servers(working_dir: Path, allowed_tools: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build MCP servers configuration for a worker.

    Loads MCP configuration from .mcp.json in the working directory
    and filters to only include servers needed by the worker's allowed_tools.

    Args:
        working_dir: Worker's working directory (worktree path)
        allowed_tools: Optional list of additional tool names the worker is allowed to use

    Returns:
        Dict of MCP server configurations ready for ClaudeAgentOptions

    Example:
        >>> servers = build_worker_mcp_servers(Path(".worktrees/worker-1"), ['mcp__playwright__screenshot'])
        >>> list(servers.keys())
        ['git', 'playwright']

    File locations:
        - Main project: <project_root>/.mcp.json
        - Worker worktrees: <worktree_root>/.mcp.json (e.g., .worktrees/worker-1/.mcp.json)
    """

    # Start with core git MCP server (always available to workers)
    worker_mcp_servers = {

    }

    # Load project MCP config from .mcp.json in worker's directory
    project_mcp_config = load_project_mcp_config(working_dir)

    # Extract MCP server names needed from allowed_tools
    # and add them from project config (external MCP servers)
    if allowed_tools and project_mcp_config:
        needed_server_names = extract_mcp_server_names(allowed_tools)
        for server_name in needed_server_names:
            if server_name in project_mcp_config:
                worker_mcp_servers[server_name] = project_mcp_config[server_name]

    return worker_mcp_servers


def _validate_worker_params(worker_id: str, task_branch: str,
                            session_info: Dict[str, Any],
                            cwd: str) -> tuple[bool, Optional[str]]:
    """Validate essential worker parameters before launching.

    Performs minimal validation to catch critical errors early before expensive
    SDK initialization (fail fast).

    Args:
        worker_id: Worker identifier
        task_branch: Git branch for the task
        session_info: Session metadata
        cwd: Working directory path

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if all validations pass
        - (False, error_msg) if validation fails
    """
    import subprocess

    # Validate task_branch exists in git (fail fast - avoid wasting SDK initialization)
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', task_branch],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path.cwd()
        )
        if result.returncode != 0:
            return False, f"Task branch {task_branch!r} does not exist in git repository"
    except subprocess.TimeoutExpired:
        return False, f"Git command timed out while checking branch {task_branch!r}"
    except Exception as e:
        return False, f"Failed to verify task branch {task_branch!r}: {e}"

    # Validate working directory exists and is a git repository
    working_dir = Path(cwd)
    if not working_dir.exists():
        return False, f"Working directory does not exist: {cwd}"

    if not working_dir.is_dir():
        return False, f"Working directory is not a directory: {cwd}"

    git_dir = working_dir / '.git'
    if not git_dir.exists():
        return False, f"Not a git repository (no .git): {cwd}"

    # All validations passed
    return True, None


async def run_worker(worker_id: str, task_branch: str,
                    session_info: Dict[str, Any],
                    cwd: str,
                    allowed_tools: Optional[List[str]] = None) -> None:
    """Run a single worker using SDK query() function.

    Args:
        worker_id: Worker identifier (e.g., "1", "2")
        task_branch: Git branch for the task
        session_info: Session metadata (plan_branch, model). session_id is extracted from plan_branch.
        cwd: Working directory - the worktree path where worker operates (REQUIRED - absolute path)
        allowed_tools: Optional list of additional MCP tools to allow beyond core tools
    """
    # Extract session_id from plan_branch
    plan_branch = session_info['plan_branch']
    session_id = plan_branch.replace('plan/', '') if plan_branch.startswith('plan/') else plan_branch

    print(f"[Worker-{worker_id}] Starting...")
    print(f"[Worker-{worker_id}]   Task branch: {task_branch}")
    print(f"[Worker-{worker_id}]   Session: {session_id}")

    # VALIDATION: Validate parameters before expensive SDK initialization
    validation_success, validation_error = _validate_worker_params(
        worker_id, task_branch, session_info, cwd
    )

    if not validation_success:
        # Validation failed - report error
        error_msg = f"Worker-{worker_id} validation failed: {validation_error}"
        print(f"[Worker-{worker_id}] ERROR: {error_msg}")
        return
    # Convert to absolute path (support both relative and absolute input)
    # Orchestrator typically provides relative path like ".worktrees/worker-1"
    if not os.path.isabs(cwd):
        # Relative path - join with project root
        working_dir = Path(os.getcwd()) / cwd
    else:
        # Already absolute - use as-is
        working_dir = Path(cwd)

    # Resolve to canonical absolute path
    working_dir = working_dir.resolve()
    print(f"[Worker-{worker_id}]   Working directory: {working_dir}")

    # Determine worker prompt file path
    from importlib.resources import files

    worker_prompt_file = str(files('flow_claude').joinpath('templates/agents/worker-template.md'))

    try:
        worker_prompt = {
            "type": "preset",
            "preset": "claude_code",
            "append": "**Instructions:** See "+worker_prompt_file+" for your full workflow."
        }

        # Build worker allowed tools list
        # Core tools always available to workers
        # NOTE: AskUserQuestion is excluded - workers must work autonomously
        core_worker_tools = [
            'Bash', 'Glob', 'Grep', 'Read', 'Edit', 'Write', 'NotebookEdit',
            'WebFetch', 'TodoWrite', 'WebSearch', 'BashOutput', 'KillShell',
            'Skill', 'SlashCommand'
        ]

        # Add core git MCP tools (always available)
        core_git_mcp_tools = [
        ]

        # Combine core tools with additional allowed tools from orchestrator
        worker_allowed_tools = core_worker_tools + core_git_mcp_tools
        if allowed_tools:
            worker_allowed_tools.extend(allowed_tools)

        # Remove AskUserQuestion if accidentally added - workers must be autonomous
        if 'AskUserQuestion' in worker_allowed_tools:
            worker_allowed_tools.remove('AskUserQuestion')
            print(f"[Worker-{worker_id}] Warning: Removed AskUserQuestion tool - workers must work autonomously")

        # Build MCP servers configuration for this worker
        # Uses helper function to load .mcp.json and filter based on allowed_tools
        worker_mcp_servers = build_worker_mcp_servers(working_dir, allowed_tools)

        # Find Claude CLI path
        import shutil
        cli_path = shutil.which('claude')
        if not cli_path and os.name == 'nt':  # Windows fallback
            cli_path = shutil.which('claude.cmd')

        print(f"[Worker-{worker_id}] Claude CLI path: {cli_path}")

        # Create worker-specific options
        options = ClaudeAgentOptions(
            system_prompt=worker_prompt,
            agents={},  # Workers don't need subagents
            allowed_tools=worker_allowed_tools,
            mcp_servers=worker_mcp_servers,  # Dynamically built from .mcp.json
            cwd=str(working_dir),
            permission_mode='acceptEdits',
            setting_sources=["user", "project", "local"],
            cli_path=cli_path,
            hooks={}  # Explicitly set CLI path
        )

        # Worker will read task instruction from the task branch's first commit
        prompt = f"You are worker {worker_id}. Read your task instruction from task branch {task_branch} using read_task_metadata, then complete the task."



        # Track initialization state to distinguish init errors from runtime errors
        first_message_received = False
        message_count = 0

        # Execute worker using query() function
        try:
            print(f"[Worker-{worker_id}] Initializing Claude SDK...")

            async for message in query(prompt=prompt, options=options):
                message_count += 1

                # Mark initialization as successful after first message
                if not first_message_received:
                    first_message_received = True
                    print(f"[Worker-{worker_id}] Initialized successfully (first message received)")

                # Handle message display (parse, format, log)
                print(message)

        except Exception as sdk_error:
            # Distinguish between initialization and runtime errors
            if not first_message_received:
                # Initialization error - SDK failed before first message
                error_phase = "initialization"
                print(f"[Worker-{worker_id}] INITIALIZATION ERROR")
                print(f"[Worker-{worker_id}]   SDK failed before receiving first message")
                print(f"[Worker-{worker_id}]   This usually indicates:")
                print(f"[Worker-{worker_id}]     - Working directory issues (doesn't exist, not accessible)")
                print(f"[Worker-{worker_id}]     - Git repository issues (invalid worktree)")
                print(f"[Worker-{worker_id}]     - Claude CLI configuration issues")
                print(f"[Worker-{worker_id}]     - Permission or path problems")
                print(f"[Worker-{worker_id}]     - MCP server initialization failures")
            else:
                # Runtime error - SDK failed after receiving messages
                error_phase = "runtime"
                print(f"[Worker-{worker_id}] RUNTIME ERROR")
                print(f"[Worker-{worker_id}]   Worker was running successfully ({message_count} messages processed)")
                print(f"[Worker-{worker_id}]   Error occurred during execution")

            # Re-raise to be handled by main exception handler
            raise sdk_error

        # Query completed naturally
        print(f"[Worker-{worker_id}] Completed task {task_branch}")
        return

    except Exception as e:
        # Handle errors - log full traceback AND diagnostic information
        error_traceback = traceback.format_exc()

        # Determine error phase if available from inner exception handler
        try:
            # Check if error_phase was set by SDK query wrapper
            error_phase = locals().get('error_phase', 'unknown')
            first_msg_received = locals().get('first_message_received', False)
            msg_count = locals().get('message_count', 0)
        except:
            error_phase = 'unknown'
            first_msg_received = False
            msg_count = 0

        # Collect comprehensive diagnostic information
        diagnostic_info = []
        diagnostic_info.append(f"Worker: {worker_id}")
        diagnostic_info.append(f"Task Branch: {task_branch}")
        diagnostic_info.append(f"Error Phase: {error_phase}")
        if error_phase == 'initialization':
            diagnostic_info.append(f"First Message Received: No (SDK initialization failed)")
        elif error_phase == 'runtime':
            diagnostic_info.append(f"Messages Processed: {msg_count}")
        diagnostic_info.append(f"Error: {str(e)}")
        diagnostic_info.append(f"Error Type: {type(e).__name__}")

        # Check exception for additional attributes (some SDK exceptions have details)
        if hasattr(e, 'args') and len(e.args) > 1:
            diagnostic_info.append(f"Error Args: {e.args}")
        if hasattr(e, '__dict__'):
            extra_attrs = {k: v for k, v in e.__dict__.items() if not k.startswith('_')}
            if extra_attrs:
                diagnostic_info.append(f"Error Attributes: {extra_attrs}")

        # Working directory diagnostics
        try:
            diagnostic_info.append(f"Working Directory: {working_dir}")
            diagnostic_info.append(f"  - Exists: {working_dir.exists()}")
            if working_dir.exists():
                diagnostic_info.append(f"  - Accessible: {os.access(working_dir, os.R_OK | os.X_OK)}")
                diagnostic_info.append(f"  - Is Directory: {working_dir.is_dir()}")

                # Check git repository status
                git_file = working_dir / ".git"
                if git_file.exists():
                    if git_file.is_file():
                        diagnostic_info.append(f"  - Git: Worktree (has .git file)")
                    elif git_file.is_dir():
                        diagnostic_info.append(f"  - Git: Repository (has .git directory)")
                else:
                    diagnostic_info.append(f"  - Git: No .git found")
        except Exception as diag_error:
            diagnostic_info.append(f"  - Could not check directory: {diag_error}")

        # Environment diagnostics
        try:
            import subprocess
            import sys
            import platform

            diagnostic_info.append(f"Environment:")
            diagnostic_info.append(f"  - Python: {sys.version.split()[0]}")
            diagnostic_info.append(f"  - Platform: {platform.system()} {platform.release()}")

            # Try to get git version
            try:
                git_result = subprocess.run(
                    ['git', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if git_result.returncode == 0:
                    diagnostic_info.append(f"  - Git: {git_result.stdout.strip()}")
            except Exception:
                diagnostic_info.append(f"  - Git: Not available or error")

            # Try to get current directory status
            try:
                cwd = os.getcwd()
                diagnostic_info.append(f"  - Process CWD: {cwd}")
            except Exception:
                pass

        except Exception as env_error:
            diagnostic_info.append(f"  - Could not collect environment info: {env_error}")

        # Log comprehensive error information
        print(f"[Worker-{worker_id}] ===== WORKER ERROR DIAGNOSTIC =====")
        for line in diagnostic_info:
            print(f"[Worker-{worker_id}] {line}")
        print(f"[Worker-{worker_id}] ===== TRACEBACK =====")
        print(f"{error_traceback}")
        print(f"[Worker-{worker_id}] ===== END DIAGNOSTIC =====")


async def launch_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Launch worker in background using SDK query() function.

    This allows the orchestrator to continue immediately without blocking,
    while the worker executes in the background using the Claude SDK.

    Args:
        args: Dict with worker_id, task_branch, cwd (relative or absolute path to worktree),
              plan_branch, model. session_id is extracted from plan_branch.
              Relative paths are resolved relative to project root.

    Returns:
        Dict with success status message
    """
    try:
        import asyncio

        # VALIDATE PARAMETERS BEFORE CREATING BACKGROUND TASK
        worker_id = args["worker_id"]
        task_branch = args["task_branch"]
        cwd = args["cwd"]
        session_info = {
            'plan_branch': args["plan_branch"],
            'model': args.get("model", "sonnet")
        }

        validation_success, validation_error = _validate_worker_params(
            worker_id, task_branch, session_info, cwd
        )

        if not validation_success:
            # Validation failed - return error immediately to orchestrator
            error_msg = f"Worker-{worker_id} validation failed: {validation_error}"
            print(f"[SDKWorkerManager] ERROR: {error_msg}")

            return {
                "content": [{
                    "type": "text",
                    "text": error_msg
                }],
                "isError": True
            }

        # Validation passed - run worker synchronously
        print(f"[launch_worker] Starting worker-{worker_id} synchronously...")

        await run_worker(
            worker_id,
            task_branch,
            session_info,
            cwd,
            args.get("allowed_tools")  # Optional additional tools to allow
        )

        print(f"[launch_worker] Worker-{worker_id} completed")

        # Return success message after worker completes
        return {
            "content": [{
                "type": "text",
                "text": f"Worker-{worker_id} has completed task branch {task_branch}."
            }],
            "isError": False
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to launch worker: {str(e)}"
                }, indent=2)
            }],
            "isError": True
        }


def main():
    """CLI entry point."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Launch worker agent')
    parser.add_argument('--worker-id', type=int, required=True, help='Worker ID (e.g., 1, 2)')
    parser.add_argument('--task-branch', type=str, required=True, help='Task branch name')
    parser.add_argument('--cwd', type=str, required=True, help='Working directory (worktree path)')
    parser.add_argument('--plan-branch', type=str, required=True, help='Plan branch name (session ID extracted from this)')
    parser.add_argument('--model', type=str, default='sonnet', help='Claude model (sonnet, opus, haiku)')

    args = parser.parse_args()

    # Build args dict
    args_dict = {
        "worker_id": str(args.worker_id),  # Convert to string for internal use
        "task_branch": args.task_branch,
        "cwd": args.cwd,
        "plan_branch": args.plan_branch,
        "model": args.model
    }

    # Run async function
    result = asyncio.run(launch_worker(args_dict))

    # Print result
    if result.get("isError"):
        print(json.dumps({"success": False, "error": result["content"][0]["text"]}, indent=2), file=sys.stderr)
        return 1
    else:
        print(json.dumps({"success": True, "message": result["content"][0]["text"]}, indent=2))
        return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
