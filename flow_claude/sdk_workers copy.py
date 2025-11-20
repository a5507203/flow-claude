"""SDK-based worker management for flow-claude.

This module provides worker management using Claude SDK's query() function
for parallel task execution.
"""

import asyncio
import json
import os
import traceback
from pathlib import Path
from typing import Dict, Any, List, AsyncGenerator, Optional

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
                            cwd: str, instructions: str) -> tuple[bool, Optional[str]]:
    """Validate worker parameters before launching.

    Performs comprehensive validation to catch errors early before expensive
    SDK initialization. Returns validation result and error message.

    Args:
        worker_id: Worker identifier
        task_branch: Git branch for the task
        session_info: Session metadata
        cwd: Working directory path
        instructions: Task instructions

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if all validations pass
        - (False, error_msg) if validation fails
    """
    import re
    import subprocess

    # Validate worker_id format (should be numeric string)
    if not re.match(r'^\d+$', worker_id):
        return False, f"Worker ID must be numeric string (e.g., '1', '2'), got: {worker_id!r}"

    # Validate session_info has required fields
    if not isinstance(session_info, dict):
        return False, f"session_info must be dict, got: {type(session_info).__name__}"

    required_session_fields = ['session_id', 'plan_branch', 'model']
    for field in required_session_fields:
        if field not in session_info:
            return False, f"session_info missing required field: {field!r}"
        if not session_info[field]:
            return False, f"session_info field {field!r} is empty"

    # Validate model is valid
    valid_models = ['sonnet', 'opus', 'haiku']
    model = session_info.get('model', '').lower()
    if model not in valid_models:
        return False, f"Invalid model {model!r}, must be one of: {valid_models}"

    # Validate task_branch exists in git
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', task_branch],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path.cwd()  # Check from main repo
        )
        if result.returncode != 0:
            return False, f"Task branch {task_branch!r} does not exist in git repository"
    except subprocess.TimeoutExpired:
        return False, f"Git command timed out while checking branch {task_branch!r}"
    except Exception as e:
        return False, f"Failed to verify task branch {task_branch!r}: {e}"

    # Validate working directory
    working_dir = Path(cwd)
    if not working_dir.exists():
        return False, f"Working directory does not exist: {cwd}"

    if not working_dir.is_dir():
        return False, f"Working directory path is not a directory: {cwd}"

    # Check if it's accessible
    if not os.access(working_dir, os.R_OK | os.X_OK):
        return False, f"Working directory not accessible (read/execute permissions required): {cwd}"

    # Validate it's a git repository (worktree or regular)
    git_dir = working_dir / '.git'
    if not git_dir.exists():
        return False, f"Working directory is not a git repository (no .git): {cwd}"

    # Validate instruction file exists and is readable
    instruction_file = working_dir / '.flow-claude' / 'WORKER_INSTRUCTIONS.md'
    if not instruction_file.exists():
        return False, f"Worker instruction file not found: {instruction_file}"

    if not instruction_file.is_file():
        return False, f"Worker instruction file is not a regular file: {instruction_file}"

    if not os.access(instruction_file, os.R_OK):
        return False, f"Worker instruction file not readable: {instruction_file}"

    # Validate instructions aren't empty
    if not instructions or not instructions.strip():
        return False, "Task instructions cannot be empty"

    # All validations passed
    return True, None


async def run_worker(worker_id: str, task_branch: str,
                    session_info: Dict[str, Any],
                    cwd: str, instructions: str,
                    allowed_tools: Optional[List[str]] = None) -> AsyncGenerator:
    """Run a single worker using SDK query() function.

    Args:
        worker_id: Worker identifier (e.g., "1", "2")
        task_branch: Git branch for the task
        session_info: Session metadata (session_id, plan_branch, model)
        cwd: Working directory - the worktree path where worker operates (REQUIRED - absolute path)
        instructions: Task-specific instructions written by the orchestrator LLM
        allowed_tools: Optional list of additional MCP tools to allow beyond core tools

    Yields:
        Dict with worker_id, message type, and content
    """
    # Check max_parallel limit
    if len(self.active_workers) >= self.max_parallel:
        error_msg = f"Cannot launch worker-{worker_id}: max_parallel limit ({self.max_parallel}) reached. Currently {len(self.active_workers)} workers active: {list(self.active_workers.keys())}"
        print(f"[SDKWorkerManager] ERROR: {error_msg}")
        yield {
            'worker_id': worker_id,
            'type': 'error',
            'message': error_msg
        }
        return

    # Log startup in debug mode only
    if self.debug:
        print(f"[SDKWorkerManager] Launching worker-{worker_id} for {task_branch}")

    # VALIDATION: Validate parameters before expensive SDK initialization
    validation_success, validation_error = self._validate_worker_params(
        worker_id, task_branch, session_info, cwd, instructions
    )

    if not validation_success:
        
        # Validation failed - report error immediately via control queue
        error_msg = f"Worker-{worker_id} validation failed: {validation_error}"
        print(f"[SDKWorkerManager] ERROR: {error_msg}")

        # Inject completion event to control queue (orchestrator needs to know)
        if self.control_queue:
            elapsed_time = 0.0  # No execution time - failed before start
            await self._inject_completion_event(
                worker_id, task_branch, exit_code=1,
                elapsed_time=elapsed_time,
                error_message=validation_error
            )

        # Yield error message (for generator consumer)
        yield {
            'worker_id': worker_id,
            'type': 'error',
            'message': validation_error
        }
        return

    # TODO create the uncomplete file
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

    # All pre-flight checks now handled by _validate_worker_params()
    # Determine worker prompt file path (shared prompts in parent directory)

    parent_dir = Path(os.getcwd())
    #TODO change to the path in the flow-claude package e.g., \flow_claude\templates
    worker_prompt_file = ""


    try:

        worker_prompt = {
            "type": "preset",
            "preset": "claude_code",
            "append": "**Instructions:** See "+worker_prompt_file+" for your full workflow."
        }

        # Build worker allowed tools list
        # Core tools always available to workers
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

        # Build MCP servers configuration for this worker
        # Uses helper function to load .mcp.json and filter based on allowed_tools
        worker_mcp_servers = build_worker_mcp_servers(working_dir, allowed_tools)

        # Log loaded MCP servers in debug mode
        if self.debug and worker_mcp_servers:
            print(f"[SDKWorkerManager] Worker-{worker_id} MCP servers: {list(worker_mcp_servers.keys())}")

        # Create worker-specific options
        options = ClaudeAgentOptions(
            system_prompt=worker_prompt,
            agents={},  # Workers don't need subagents
            allowed_tools=worker_allowed_tools,
            mcp_servers=worker_mcp_servers,  # Dynamically built from .mcp.json
            cwd=str(working_dir),
            permission_mode='acceptEdits',
            setting_sources=["user", "project", "local"]
        )

        # Use the instructions provided by the orchestrator
        prompt = instructions



        # Track initialization state to distinguish init errors from runtime errors
        first_message_received = False
        message_count = 0

        # Execute worker using ClaudeSDKClient (persistent session)
        # This properly supports MCP servers unlike query()
        try:
            #TODO debug can be removed
            if self.debug:
                print(f"[SDKWorkerManager] Initializing ClaudeSDKClient for worker-{worker_id}...")

            async with ClaudeSDKClient(options=options) as client:
                # Send the prompt to the client
                await client.query(prompt)

                # Receive responses
                async for message in client.receive_response():
                    message_count += 1

                    # Mark initialization as successful after first message
                    if not first_message_received:
                        first_message_received = True
                        print(f"[SDKWorkerManager] Worker-{worker_id} initialized successfully (first message received)")

                    # Handle message display (parse, format, log)
                    print(message)

        

        except Exception as sdk_error:
            # Distinguish between initialization and runtime errors
            if not first_message_received:
                # Initialization error - SDK failed before first message
                error_phase = "initialization"
                print(f"[SDKWorkerManager] Worker-{worker_id} INITIALIZATION ERROR")
                print(f"[SDKWorkerManager]   SDK failed before receiving first message")
                print(f"[SDKWorkerManager]   This usually indicates:")
                print(f"[SDKWorkerManager]     - Working directory issues (doesn't exist, not accessible)")
                print(f"[SDKWorkerManager]     - Git repository issues (invalid worktree)")
                print(f"[SDKWorkerManager]     - Claude CLI configuration issues")
                print(f"[SDKWorkerManager]     - Permission or path problems")
                print(f"[SDKWorkerManager]     - MCP server initialization failures")
            else:
                # Runtime error - SDK failed after receiving messages
                error_phase = "runtime"
                print(f"[SDKWorkerManager] Worker-{worker_id} RUNTIME ERROR")
                print(f"[SDKWorkerManager]   Worker was running successfully ({message_count} messages processed)")
                print(f"[SDKWorkerManager]   Error occurred during execution")

            # Re-raise to be handled by main exception handler
            raise sdk_error

        # TODO delele the file Query completed naturally - mark worker as complete
    
            elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
            print(f"[SDKWorkerManager] Worker-{worker_id} completed task {task_branch}")

            # IMPORTANT: Inject completion event BEFORE yielding the message
            # This ensures the event reaches control_queue even if consumer breaks early
            if self.control_queue:
                await self._inject_completion_event(worker_id, task_branch, 0, elapsed)

            # Now yield the completed message (consumer can safely break after this)
            yield {
                'worker_id': worker_id,
                'type': 'completed',
                'elapsed_time': elapsed,
                'task_branch': task_branch
            }
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

        # Calculate elapsed time
        if worker_id in self.active_workers:
            elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
            diagnostic_info.append(f"Elapsed Time: {elapsed:.2f}s")
        else:
            elapsed = 0
            diagnostic_info.append(f"Elapsed Time: Worker never started properly")

        # Log comprehensive error information
        print(f"[SDKWorkerManager] ===== WORKER ERROR DIAGNOSTIC =====")
        for line in diagnostic_info:
            print(f"[SDKWorkerManager] {line}")
        print(f"[SDKWorkerManager] ===== TRACEBACK =====")
        print(f"{error_traceback}")
        print(f"[SDKWorkerManager] ===== END DIAGNOSTIC =====")

        # IMPORTANT: Inject error event BEFORE yielding the message
        # This ensures the event reaches control_queue even if consumer breaks early
        if self.control_queue:
            # Create concise error summary for orchestrator
            error_summary = f"{type(e).__name__}: {str(e)}"
            if error_phase != 'unknown':
                error_summary = f"[{error_phase}] {error_summary}"

            await self._inject_completion_event(
                worker_id, task_branch, exit_code=1,
                elapsed_time=elapsed,
                error_message=error_summary
            )

        # Now yield the error message with comprehensive diagnostics
        yield {
            'worker_id': worker_id,
            'type': 'error',
            'error': str(e),
            'traceback': error_traceback,
            'diagnostics': '\n'.join(diagnostic_info)
        }


async def launch_worker_async(args: Dict[str, Any]) -> Dict[str, Any]:
    """Launch worker in background using SDK query() function.

    This allows the orchestrator to continue immediately without blocking,
    while the worker executes in the background using the Claude SDK.

    Args:
        args: Dict with worker_id, task_branch, cwd (relative or absolute path to worktree),
              session_id, plan_branch, model, and instructions.
              Relative paths are resolved relative to project root.

    Returns:
        Dict with success status message
    """
    try:
        # Get SDK worker manager (it will already be initialized with proper logger)
 
        import asyncio
        import logging

        # VALIDATE PARAMETERS BEFORE CREATING BACKGROUND TASK
        # This gives immediate feedback to orchestrator instead of waiting for control queue
        worker_id = args["worker_id"]
        task_branch = args["task_branch"]
        cwd = args["cwd"]
        instructions = args["instructions"]
        session_info = {
            'session_id': args["session_id"],
            'plan_branch': args["plan_branch"],
            'model': args.get("model", "sonnet")
        }

        validation_success, validation_error = _validate_worker_params(
            worker_id, task_branch, session_info, cwd, instructions
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

        # Validation passed - create async task for worker
        # Create a wrapped task that handles exceptions properly
        async def safe_worker_wrapper():
            """Wrapper to ensure exceptions don't cause unhandled errors."""
            try:
                await _run_sdk_worker_task(
                    worker_id,
                    task_branch,
                    session_info,
                    cwd,
                    instructions,
                    args.get("allowed_tools")  # Optional additional tools to allow
                )
            except Exception as e:
                # Log but don't raise - prevents unhandled exception in TaskGroup
                logger = logging.getLogger("flow_claude.orchestrator")
                logger.error(f"Worker-{worker_id} wrapper caught exception: {e}")

        # Start worker with safe wrapper
        worker_task = asyncio.create_task(safe_worker_wrapper())

        # Store the task reference in manager for stop_worker functionality
        # Note: Worker is added to active_workers in run_worker after validation
        if worker_id in manager.active_workers:
            manager.active_workers[worker_id]['task'] = worker_task

        logger = logging.getLogger("flow_claude.orchestrator")
        logger.debug(f"Created async task for worker-{worker_id}: {worker_task}")

        # Return a simple, clean message without JSON
        return {
            "content": [{
                "type": "text",
                "text": f"Worker-{worker_id} has been launched in the background for task branch {task_branch}. The worker is now executing the task autonomously."
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


async def _run_sdk_worker_task(worker_id: str, task_branch: str,
                               session_info: Dict[str, Any],
                               cwd: str, instructions: str,
                               allowed_tools: Optional[List[str]] = None):
    """Helper to run SDK worker as async task.

    This collects all output from the worker and handles completion.
    """
    import logging
    logger = logging.getLogger(f"flow_claude.worker-{worker_id}")

    try:
        logger.info(f"Starting SDK worker-{worker_id} for {task_branch}")
        logger.debug(f"Working directory: {cwd}")
        if allowed_tools:
            logger.debug(f"Additional allowed tools: {allowed_tools}")

        # Collect all messages from the worker
        messages_received = 0
        async for message in run_worker(worker_id, task_branch,
                                                session_info, cwd, instructions,
                                                allowed_tools):
            messages_received += 1
            # Log the message for debugging
            if message.get('type') == 'error':
                error_msg = message.get('error', message.get('message'))
                logger.error(f"Worker-{worker_id} error: {error_msg}")
                # Log traceback if available
                if 'traceback' in message:
                    logger.error(f"Worker-{worker_id} traceback:\n{message['traceback']}")
                # Important: Still continue processing other messages
            elif message.get('type') == 'completed':
                logger.info(f"Worker-{worker_id} completed task {task_branch}")
                break  # Exit cleanly on completion
            # Messages are already logged by the manager

        if messages_received == 0:
            logger.warning(f"Worker-{worker_id} produced no output")

    except asyncio.CancelledError:
        # Task was cancelled - this is normal during shutdown
        logger.info(f"Worker-{worker_id} task was cancelled")
        raise  # Re-raise to properly handle cancellation
    except Exception as e:
        # Log the actual error with full traceback for debugging
        logger.error(f"Worker-{worker_id} task failed with exception: {str(e)}", exc_info=True)
        # Don't re-raise - this prevents the "unhandled error in TaskGroup" issue
        # The error has been logged and the manager already injected a completion event


def create_worker_tools_server():
    """Create MCP server with worker management tools.

    Returns:
        MCP server instance with worker tools

    Usage:
        In CLI setup:
            options = ClaudeAgentOptions(
                mcp_servers={
                    "git": create_git_tools_server(),
                    "workers": create_worker_tools_server()
                },
                ...
            )

        Agents can then use:
            - mcp__workers__launch_worker_async: Launch worker in background
            - mcp__workers__get_worker_status: Check status of all worker slots
            - mcp__workers__stop_worker: Stop a running worker by worker ID
    """
    return create_sdk_mcp_server(
        name="workers",
        version="1.0.0",
        tools=[
            launch_worker_async,
            get_worker_status,
            stop_worker
        ]
    )