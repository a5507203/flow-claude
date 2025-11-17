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

    Loads MCP configuration from .flow-claude/.mcp.json in the working directory
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
    """
    # Lazy import to avoid circular dependency
    from flow_claude.git_tools import create_git_tools_server

    # Start with core git MCP server (always available to workers)
    worker_mcp_servers = {
        "git": create_git_tools_server()
    }

    # Load project MCP config from .flow-claude/.mcp.json in worker's directory
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
        self.active_workers = {}  # worker_id -> task info
        self.max_parallel = max_parallel

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

        # Log that we're starting
        self.log(f"[SDKWorkerManager] run_worker called for worker-{worker_id}")
        self.log(f"[SDKWorkerManager]   Task branch: {task_branch}")
        self.log(f"[SDKWorkerManager]   CWD: {cwd}")
        self.log(f"[SDKWorkerManager]   Active workers: {len(self.active_workers)}/{self.max_parallel}")

        # Track active worker
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

        # First check for worker prompt in parent directory (shared prompts)
        parent_dir = Path(os.getcwd())
        worker_prompt_file = parent_dir / ".flow-claude" / "WORKER_INSTRUCTIONS.md"

        # Fallback to worktree if not found in parent
        if not worker_prompt_file.exists():
            flow_claude_dir = working_dir / ".flow-claude"
            worker_prompt_file = flow_claude_dir / "WORKER_INSTRUCTIONS.md"


        # Ensure worker instructions exist
        if not worker_prompt_file.exists():
            self.log(f"[SDKWorkerManager] ERROR: Worker instructions not found at {worker_prompt_file}")
            yield {
                'worker_id': worker_id,
                'type': 'error',
                'message': f"Worker instructions not found: {worker_prompt_file}"
            }
            return

        # PRE-FLIGHT CHECKS: Verify environment before launching worker
        try:
            # Check 1: Working directory exists
            if not working_dir.exists():
                error_msg = f"Working directory does not exist: {working_dir}"
                self.log(f"[SDKWorkerManager] ERROR: {error_msg}")
                yield {
                    'worker_id': worker_id,
                    'type': 'error',
                    'message': error_msg
                }
                return

            # Check 2: Working directory is accessible
            if not os.access(working_dir, os.R_OK | os.X_OK):
                error_msg = f"Working directory not accessible: {working_dir}"
                self.log(f"[SDKWorkerManager] ERROR: {error_msg}")
                yield {
                    'worker_id': worker_id,
                    'type': 'error',
                    'message': error_msg
                }
                return

            # Check 3: Is a git repository
            git_dir = working_dir / ".git"
            is_git_repo = git_dir.exists() or (working_dir / ".." / ".git").exists()
            if not is_git_repo:
                # Check if it's a worktree (has .git file pointing to main repo)
                git_file = working_dir / ".git"
                is_git_repo = git_file.is_file() if git_file.exists() else False

            if not is_git_repo:
                self.log(f"[SDKWorkerManager] WARNING: Working directory is not a git repository: {working_dir}")

            # Check 4: Worker instructions are readable
            if not os.access(worker_prompt_file, os.R_OK):
                error_msg = f"Worker instructions not readable: {worker_prompt_file}"
                self.log(f"[SDKWorkerManager] ERROR: {error_msg}")
                yield {
                    'worker_id': worker_id,
                    'type': 'error',
                    'message': error_msg
                }
                return

            # Log diagnostic information in debug mode
            if self.debug:
                self.log(f"[SDKWorkerManager] Pre-flight checks passed for worker-{worker_id}")
                self.log(f"[SDKWorkerManager]   Working dir exists: {working_dir.exists()}")
                self.log(f"[SDKWorkerManager]   Working dir accessible: {os.access(working_dir, os.R_OK | os.X_OK)}")
                self.log(f"[SDKWorkerManager]   Is git repository: {is_git_repo}")
                self.log(f"[SDKWorkerManager]   Instruction file: {worker_prompt_file}")

                # Try to get current git branch
                try:
                    import subprocess
                    result = subprocess.run(
                        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                        cwd=working_dir,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        current_branch = result.stdout.strip()
                        self.log(f"[SDKWorkerManager]   Current branch: {current_branch}")
                except Exception as git_error:
                    self.log(f"[SDKWorkerManager]   Could not determine git branch: {git_error}")

        except Exception as preflight_error:
            error_msg = f"Pre-flight check failed: {str(preflight_error)}"
            self.log(f"[SDKWorkerManager] ERROR: {error_msg}")
            self.log(f"[SDKWorkerManager] Traceback: {traceback.format_exc()}")
            yield {
                'worker_id': worker_id,
                'type': 'error',
                'message': error_msg
            }
            return

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

            if self.debug:
                self.log(f"[SDKWorkerManager] Launching worker-{worker_id} for {task_branch}")
                self.log(f"[SDKWorkerManager]   Using SDK query() function")
                self.log(f"[SDKWorkerManager]   Working directory: {str(working_dir)}")
                self.log(f"[SDKWorkerManager]   Model: {session_info.get('model', 'sonnet')}")

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
            # Wrap with better error context
            try:
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
                await self._inject_completion_event(worker_id, task_branch, 1, elapsed)

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
                                      exit_code: int, elapsed_time: float):
        """Inject worker completion event into control queue.

        Args:
            worker_id: Worker identifier
            task_branch: Task branch name
            exit_code: 0 for success, non-zero for error
            elapsed_time: Time taken in seconds
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

        # Store the task reference (optional, for debugging)
        logger = logging.getLogger("flow_claude.orchestrator")
        logger.debug(f"Created async task for worker-{args['worker_id']}: {worker_task}")

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
    """
    return create_sdk_mcp_server(
        name="workers",
        version="1.0.0",
        tools=[
            launch_worker_async,
            get_worker_status
        ]
    )