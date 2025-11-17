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
from flow_claude.utils.message_formatter import parse_agent_message
from flow_claude.utils.message_handler import create_worker_message_handler
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
    # Lazy import to avoid circular dependency
    from flow_claude.git_tools import create_git_tools_server

    # Start with core git MCP server (always available to workers)
    worker_mcp_servers = {
        "git": create_git_tools_server()
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


class SDKWorkerManager:
    """Manages workers using SDK query() function for parallel execution."""

    def __init__(self, control_queue: Optional[asyncio.Queue] = None,
                 debug: bool = False,
                 log_func: Optional[callable] = None,
                 max_parallel: int = 3):
        """Initialize SDK worker manager.

        Args:
            control_queue: Queue for injecting completion events
            debug: Enable debug logging
            log_func: Function to call for logging
            max_parallel: Maximum number of concurrent workers
        """
        self.control_queue = control_queue
        self.debug = debug
        self.log = log_func or (lambda msg: print(msg))
        self.active_workers = {}  # worker_id -> task info (task_branch, cwd, start_time, task)
        self.max_parallel = max_parallel

    def _validate_worker_params(self, worker_id: str, task_branch: str,
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

    async def run_worker(self, worker_id: str, task_branch: str,
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
            self.log(f"[SDKWorkerManager] ERROR: {error_msg}")
            yield {
                'worker_id': worker_id,
                'type': 'error',
                'message': error_msg
            }
            return

        # Log startup in debug mode only
        if self.debug:
            self.log(f"[SDKWorkerManager] Launching worker-{worker_id} for {task_branch}")

        # VALIDATION: Validate parameters before expensive SDK initialization
        validation_success, validation_error = self._validate_worker_params(
            worker_id, task_branch, session_info, cwd, instructions
        )

        if not validation_success:
            # Validation failed - report error immediately via control queue
            error_msg = f"Worker-{worker_id} validation failed: {validation_error}"
            self.log(f"[SDKWorkerManager] ERROR: {error_msg}")

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

        # Track active worker (only after validation passes)
        self.active_workers[worker_id] = {
            'task_branch': task_branch,
            'cwd': cwd,
            'start_time': asyncio.get_event_loop().time()
        }

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
        worker_prompt_file = parent_dir / ".flow-claude" / "WORKER_INSTRUCTIONS.md"

        # Fallback to worktree if not found in parent
        if not worker_prompt_file.exists():
            flow_claude_dir = working_dir / ".flow-claude"
            worker_prompt_file = flow_claude_dir / "WORKER_INSTRUCTIONS.md"

        try:

            worker_prompt = {
                "type": "preset",
                "preset": "claude_code",
                "append": "**Instructions:** See .flow-claude/WORKER_INSTRUCTIONS.md for your full workflow."
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
                'mcp__git__parse_task',
                'mcp__git__parse_plan',
                'mcp__git__parse_worker_commit',
                'mcp__git__get_provides'
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
                self.log(f"[SDKWorkerManager] Worker-{worker_id} MCP servers: {list(worker_mcp_servers.keys())}")

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

            # Create message handler for this worker
            message_handler = create_worker_message_handler(
                worker_id=worker_id,
                debug=self.debug,
                log_func=self.log
            )

            # Track initialization state to distinguish init errors from runtime errors
            first_message_received = False
            message_count = 0

            # Execute worker using ClaudeSDKClient (persistent session)
            # This properly supports MCP servers unlike query()
            try:
                if self.debug:
                    self.log(f"[SDKWorkerManager] Initializing ClaudeSDKClient for worker-{worker_id}...")

                async with ClaudeSDKClient(options=options) as client:
                    # Send the prompt to the client
                    await client.query(prompt)

                    # Receive responses
                    async for message in client.receive_response():
                        message_count += 1

                        # Mark initialization as successful after first message
                        if not first_message_received:
                            first_message_received = True
                            self.log(f"[SDKWorkerManager] Worker-{worker_id} initialized successfully (first message received)")

                        # Handle message display (parse, format, log)
                        message_handler.handle_generic_message(message)

                        # Parse message for orchestrator consumption
                        parsed = parse_agent_message(message)

                        # Yield parsed message for orchestrator
                        yield {
                            'worker_id': worker_id,
                            'type': parsed.message_type.value,
                            'content': parsed.content,
                            'tool_name': parsed.tool_name,
                            'tool_input': parsed.tool_input,
                            'tool_output': parsed.tool_output
                        }

            except Exception as sdk_error:
                # Distinguish between initialization and runtime errors
                if not first_message_received:
                    # Initialization error - SDK failed before first message
                    error_phase = "initialization"
                    self.log(f"[SDKWorkerManager] Worker-{worker_id} INITIALIZATION ERROR")
                    self.log(f"[SDKWorkerManager]   SDK failed before receiving first message")
                    self.log(f"[SDKWorkerManager]   This usually indicates:")
                    self.log(f"[SDKWorkerManager]     - Working directory issues (doesn't exist, not accessible)")
                    self.log(f"[SDKWorkerManager]     - Git repository issues (invalid worktree)")
                    self.log(f"[SDKWorkerManager]     - Claude CLI configuration issues")
                    self.log(f"[SDKWorkerManager]     - Permission or path problems")
                    self.log(f"[SDKWorkerManager]     - MCP server initialization failures")
                else:
                    # Runtime error - SDK failed after receiving messages
                    error_phase = "runtime"
                    self.log(f"[SDKWorkerManager] Worker-{worker_id} RUNTIME ERROR")
                    self.log(f"[SDKWorkerManager]   Worker was running successfully ({message_count} messages processed)")
                    self.log(f"[SDKWorkerManager]   Error occurred during execution")

                # Re-raise to be handled by main exception handler
                raise sdk_error

            # Query completed naturally - mark worker as complete
            if worker_id in self.active_workers:
                elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
                self.log(f"[SDKWorkerManager] Worker-{worker_id} completed task {task_branch}")

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
            self.log(f"[SDKWorkerManager] ===== WORKER ERROR DIAGNOSTIC =====")
            for line in diagnostic_info:
                self.log(f"[SDKWorkerManager] {line}")
            self.log(f"[SDKWorkerManager] ===== TRACEBACK =====")
            self.log(f"{error_traceback}")
            self.log(f"[SDKWorkerManager] ===== END DIAGNOSTIC =====")

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

        finally:
            # Clean up (safe deletion)
            if worker_id in self.active_workers:
                del self.active_workers[worker_id]

    async def _inject_completion_event(self, worker_id: str, task_branch: str,
                                      exit_code: int, elapsed_time: float,
                                      error_message: Optional[str] = None):
        """Inject worker completion event into control queue.

        Args:
            worker_id: Worker identifier
            task_branch: Task branch name
            exit_code: 0 for success, non-zero for error
            elapsed_time: Time taken in seconds
            error_message: Optional error message (for failures)
        """
        if not self.control_queue:
            self.log(f"[SDKWorkerManager] WARNING: No control_queue available - cannot inject completion event for worker-{worker_id}")
            return

        event = {
            "type": "worker_completion",
            "data": {
                "worker_id": worker_id,
                "task_branch": task_branch,
                "exit_code": exit_code,
                "elapsed_time": elapsed_time
            }
        }

        # Add error message if provided
        if error_message:
            event["data"]["error_message"] = error_message

        try:
            await self.control_queue.put(event)
            self.log(f"[SDKWorkerManager] Successfully injected completion event for worker-{worker_id} into control_queue")
            if self.debug:
                self.log(f"[SDKWorkerManager]   Task: {task_branch}, Exit code: {exit_code}, Time: {elapsed_time:.1f}s")
        except Exception as e:
            self.log(f"[SDKWorkerManager] Error injecting event: {e}")

    def update_max_parallel(self, new_max: int):
        """Update max parallel workers dynamically (can be called mid-session).

        Args:
            new_max: New maximum number of concurrent workers
        """
        old_max = self.max_parallel
        self.max_parallel = new_max
        if self.debug:
            self.log(f"[SDKWorkerManager] Updated max_parallel from {old_max} to {new_max}")
            self.log(f"[SDKWorkerManager] Currently {len(self.active_workers)} workers active")

    async def stop_all_workers(self) -> int:
        """Stop all currently active workers (hardcoded interrupt handler).

        This is called when user interrupts (ESC key), NOT exposed as MCP tool.
        Cancels all worker tasks, injects completion events, and cleans up.

        Returns:
            Number of workers stopped
        """
        if not self.active_workers:
            self.log(f"[SDKWorkerManager] No active workers to stop")
            return 0

        worker_count = len(self.active_workers)
        self.log(f"[SDKWorkerManager] Stopping all {worker_count} active workers...")

        stopped_count = 0

        # Process workers one at a time with popitem() to avoid race conditions
        # If a worker completes naturally during this loop, it won't be in the dict
        while self.active_workers:
            try:
                worker_id, worker_info = self.active_workers.popitem()
            except KeyError:
                # Dict became empty (race with natural completion)
                break

            task_branch = worker_info.get('task_branch', 'unknown')
            worker_task = worker_info.get('task')

            # Cancel the worker task if it exists and is running
            if worker_task:
                if not worker_task.done():
                    worker_task.cancel()
                    self.log(f"[SDKWorkerManager] Cancelled worker-{worker_id} task for {task_branch}")
                else:
                    self.log(f"[SDKWorkerManager] Worker-{worker_id} task already completed for {task_branch}")
            else:
                self.log(f"[SDKWorkerManager] WARNING: Worker-{worker_id} has no task reference (task_branch: {task_branch})")

            # Calculate elapsed time
            elapsed = asyncio.get_event_loop().time() - worker_info.get('start_time', 0)

            # Inject completion event with exit_code=2 (stopped)
            if self.control_queue:
                await self._inject_completion_event(
                    worker_id, task_branch, exit_code=2,
                    elapsed_time=elapsed,
                    error_message="Worker stopped by user interrupt (stop all)"
                )

            stopped_count += 1

        self.log(f"[SDKWorkerManager] Stopped {stopped_count} workers")

        return stopped_count

    def get_active_workers(self) -> Dict[str, Any]:
        """Get information about currently active workers.

        Returns:
            Dict mapping worker_id to worker info
        """
        return dict(self.active_workers)


# Global instance (singleton pattern)
_sdk_worker_manager: Optional[SDKWorkerManager] = None


def get_sdk_worker_manager(control_queue: Optional[asyncio.Queue] = None,
                          debug: bool = False,
                          log_func: Optional[callable] = None,
                          max_parallel: Optional[int] = None) -> SDKWorkerManager:
    """Get or create the global SDKWorkerManager instance.

    Args:
        control_queue: Async queue for completion events
        debug: Enable debug output
        log_func: Logging function
        max_parallel: Maximum number of concurrent workers (default: 3 on creation, unchanged on retrieval)

    Returns:
        SDKWorkerManager singleton instance
    """
    global _sdk_worker_manager

    if _sdk_worker_manager is None:
        # First time creation - use default if not provided
        _sdk_worker_manager = SDKWorkerManager(control_queue, debug, log_func, max_parallel or 3)
    else:
        # Update parameters if provided
        # Always update control_queue if provided (not just when current is None)
        if control_queue:
            _sdk_worker_manager.control_queue = control_queue
        if log_func:
            _sdk_worker_manager.log = log_func
        # Only update max_parallel if explicitly provided (don't overwrite with None)
        if max_parallel is not None:
            _sdk_worker_manager.max_parallel = max_parallel

    return _sdk_worker_manager


async def stop_all_workers_async() -> int:
    """Stop all active workers asynchronously (for async UI interrupt handler).

    This is an async wrapper for the stop_all_workers() method.
    Can be awaited from async code (like Textual async action handlers).

    Returns:
        Number of workers stopped

    Usage:
        # From async UI interrupt handler
        stopped_count = await stop_all_workers_async()
        print(f"Stopped {stopped_count} workers")
    """
    manager = get_sdk_worker_manager()
    return await manager.stop_all_workers()


@tool(
    "launch_worker_async",
    "Launch worker in background using SDK query() for async execution",
    {
        "worker_id": {"type": "string", "description": "Worker ID (e.g., '1', '2', '3')"},
        "task_branch": {"type": "string", "description": "Task branch name (e.g., 'task/001-user-model')"},
        "cwd": {"type": "string", "description": "Path to worker's worktree directory - relative (e.g., '.worktrees/worker-1') or absolute"},
        "session_id": {"type": "string", "description": "Session ID (e.g., 'session-20250115-120000')"},
        "plan_branch": {"type": "string", "description": "Plan branch name (e.g., 'plan/session-20250115-120000')"},
        "model": {"type": "string", "description": "Model to use (sonnet/opus/haiku)", "default": "sonnet"},
        "instructions": {"type": "string", "description": "Task-specific instructions for the worker written by the orchestrator"},
        "allowed_tools": {"type": "array", "description": "Optional list of additional MCP tool names to allow (worker loads servers from .mcp.json)", "optional": True}
    }
)
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
        manager = get_sdk_worker_manager()

        # Create async task for worker
        import asyncio
        import logging

        # Create a wrapped task that handles exceptions properly
        async def safe_worker_wrapper():
            """Wrapper to ensure exceptions don't cause unhandled errors."""
            try:
                await _run_sdk_worker_task(
                    manager,
                    args["worker_id"],
                    args["task_branch"],
                    {
                        'session_id': args["session_id"],
                        'plan_branch': args["plan_branch"],
                        'model': args.get("model", "sonnet")
                    },
                    args["cwd"],  # cwd IS the worktree path
                    args["instructions"],  # Pass required instructions
                    args.get("allowed_tools")  # Optional additional tools to allow
                )
            except Exception as e:
                # Log but don't raise - prevents unhandled exception in TaskGroup
                logger = logging.getLogger("flow_claude.orchestrator")
                logger.error(f"Worker-{args['worker_id']} wrapper caught exception: {e}")

        # Start worker with safe wrapper
        worker_task = asyncio.create_task(safe_worker_wrapper())

        # Store the task reference in manager for stop_worker functionality
        worker_id = args['worker_id']
        if worker_id in manager.active_workers:
            manager.active_workers[worker_id]['task'] = worker_task

        logger = logging.getLogger("flow_claude.orchestrator")
        logger.debug(f"Created async task for worker-{worker_id}: {worker_task}")

        # Return a simple, clean message without JSON 
        return {
            "content": [{
                "type": "text",
                "text": f"Worker-{args['worker_id']} has been launched in the background for task branch {args['task_branch']}. The worker is now executing the task autonomously."
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


@tool(
    "get_worker_status",
    "Check status of all worker slots (shows active, available, and total capacity)",
    {
        "worker_id": {"type": "string", "description": "Optional specific worker ID to check", "optional": True}
    }
)
async def get_worker_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get comprehensive status of all worker slots.

    Shows all worker slots (1 to max_parallel), indicating which are active,
    available, or idle. This helps orchestrator understand total capacity
    and available resources.

    Args:
        args: Dict with optional worker_id

    Returns:
        Dict with comprehensive worker status:
        - max_parallel: Maximum worker slots
        - active_count: Number of active workers
        - available_count: Number of available slots
        - workers: Status of each slot (active/available)
    """
    try:
        import asyncio

        # Get SDK worker manager
        manager = get_sdk_worker_manager()

        # Get active workers and max_parallel
        active_workers = manager.get_active_workers()
        max_parallel = getattr(manager, 'max_parallel', 3)  # Default to 3 if not set

        # Build comprehensive status for all worker slots
        workers_status = {}

        for i in range(1, max_parallel + 1):
            worker_id_str = str(i)

            if worker_id_str in active_workers:
                # Active worker - include task info and elapsed time
                worker_info = active_workers[worker_id_str]
                elapsed = asyncio.get_event_loop().time() - worker_info.get('start_time', 0)
                workers_status[worker_id_str] = {
                    "status": "active",
                    "task_branch": worker_info.get('task_branch', 'unknown'),
                    "cwd": worker_info.get('cwd', 'unknown'),
                    "elapsed_seconds": round(elapsed, 1)
                }
            else:
                # Available slot
                workers_status[worker_id_str] = {
                    "status": "available"
                }

        # Build comprehensive result
        result = {
            "max_parallel": max_parallel,
            "active_count": len(active_workers),
            "available_count": max_parallel - len(active_workers),
            "workers": workers_status
        }

        # If specific worker requested, filter to just that worker
        requested_worker_id = args.get("worker_id")
        if requested_worker_id:
            if requested_worker_id in workers_status:
                result = {
                    "max_parallel": max_parallel,
                    "worker": {requested_worker_id: workers_status[requested_worker_id]}
                }
            else:
                result = {
                    "error": f"Worker {requested_worker_id} not found (max_parallel={max_parallel}, valid IDs: 1-{max_parallel})"
                }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }],
            "isError": False
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to get worker status: {str(e)}"
                }, indent=2)
            }],
            "isError": True
        }


async def _run_sdk_worker_task(manager, worker_id: str, task_branch: str,
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
        async for message in manager.run_worker(worker_id, task_branch,
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


@tool(
    "stop_worker",
    "Stop a running worker by worker ID (forcefully cancels the worker task)",
    {
        "worker_id": {"type": "string", "description": "Worker ID to stop (e.g., '1', '2', '3')"}
    }
)
async def stop_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stop a running worker by cancelling its task.

    This forcefully stops a worker that is currently executing a task.
    The worker will be cancelled, cleaned up, and a completion event will
    be injected to the control queue with exit_code=2 (stopped).

    Args:
        args: Dict with worker_id

    Returns:
        Dict with success/error status

    Example:
        >>> stop_worker({"worker_id": "1"})
        {"status": "stopped", "worker_id": "1", "task_branch": "task/001-description"}
    """
    try:
        import asyncio

        worker_id = args.get("worker_id")

        # Get SDK worker manager
        manager = get_sdk_worker_manager()

        if not worker_id:
            error_msg = "worker_id is required"
            # Send error to control queue
            if manager.control_queue:
                await manager.control_queue.put({
                    "type": "stop_worker_result",
                    "data": {
                        "success": False,
                        "error": error_msg
                    }
                })
            return {
                "content": [{
                    "type": "text",
                    "text": error_msg
                }],
                "isError": True
            }

        # Check if worker exists and is active
        active_workers = manager.get_active_workers()
        if worker_id not in active_workers:
            error_msg = f"Worker-{worker_id} is not currently running"
            # Send error to control queue
            if manager.control_queue:
                await manager.control_queue.put({
                    "type": "stop_worker_result",
                    "data": {
                        "success": False,
                        "worker_id": worker_id,
                        "error": error_msg,
                        "active_workers": list(active_workers.keys())
                    }
                })
            return {
                "content": [{
                    "type": "text",
                    "text": f"{error_msg}. Active workers: {list(active_workers.keys())}"
                }],
                "isError": True
            }

        worker_info = active_workers[worker_id]
        task_branch = worker_info.get('task_branch', 'unknown')
        worker_task = worker_info.get('task')

        # Cancel the worker task if it exists
        if worker_task and not worker_task.done():
            worker_task.cancel()
            manager.log(f"[SDKWorkerManager] Cancelled worker-{worker_id} task for {task_branch}")

            # Calculate elapsed time
            elapsed = asyncio.get_event_loop().time() - worker_info.get('start_time', 0)

            # Inject completion event with exit_code=2 (stopped)
            if manager.control_queue:
                await manager._inject_completion_event(
                    worker_id, task_branch, exit_code=2,
                    elapsed_time=elapsed,
                    error_message="Worker stopped by orchestrator request"
                )

            # Clean up worker from active_workers
            if worker_id in manager.active_workers:
                del manager.active_workers[worker_id]

            # Send stop result to control queue for orchestrator
            result_message = f"Worker-{worker_id} has been stopped successfully (task: {task_branch}, elapsed: {round(elapsed, 1)}s)"
            if manager.control_queue:
                await manager.control_queue.put({
                    "type": "stop_worker_result",
                    "data": {
                        "success": True,
                        "worker_id": worker_id,
                        "task_branch": task_branch,
                        "elapsed_seconds": round(elapsed, 1),
                        "message": result_message
                    }
                })
                manager.log(f"[SDKWorkerManager] Sent stop_worker result to control queue")

            # Return simple acknowledgment (orchestrator will get details via control queue)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Stop command issued for worker-{worker_id}. Worker is being cancelled..."
                }],
                "isError": False
            }
        else:
            # Task already completed or doesn't exist
            error_message = f"Worker-{worker_id} task is not running (already completed or no task reference)"

            # Send error result to control queue
            if manager.control_queue:
                await manager.control_queue.put({
                    "type": "stop_worker_result",
                    "data": {
                        "success": False,
                        "worker_id": worker_id,
                        "task_branch": task_branch,
                        "error": error_message
                    }
                })

            return {
                "content": [{
                    "type": "text",
                    "text": error_message
                }],
                "isError": True
            }

    except Exception as e:
        # Get manager for control queue access
        try:
            manager = get_sdk_worker_manager()
            error_msg = f"Failed to stop worker: {str(e)}"

            # Send error to control queue
            if manager.control_queue:
                await manager.control_queue.put({
                    "type": "stop_worker_result",
                    "data": {
                        "success": False,
                        "worker_id": args.get("worker_id"),
                        "error": error_msg
                    }
                })
        except:
            pass  # If we can't even get manager, just return error

        return {
            "content": [{
                "type": "text",
                "text": f"Failed to stop worker: {str(e)}"
            }],
            "isError": True
        }


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