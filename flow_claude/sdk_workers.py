"""SDK-based worker management for flow-claude.

This module provides worker management using Claude SDK's query() function
for parallel task execution.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List, AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, query, tool, create_sdk_mcp_server


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
                        cwd: str, instructions: str) -> AsyncGenerator:
        """Run a single worker using SDK query() function.

        Args:
            worker_id: Worker identifier (e.g., "1", "2")
            task_branch: Git branch for the task
            session_info: Session metadata (session_id, plan_branch, model)
            cwd: Working directory - the worktree path where worker operates (REQUIRED - absolute path)
            instructions: Task-specific instructions written by the orchestrator LLM

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

        # Convert relative path to absolute if needed
        # Also handle Unix-style paths on Windows (e.g., /c/Users/... -> C:\Users\...)
        if cwd.startswith('/c/') or cwd.startswith('/d/') or cwd.startswith('/e/'):
            # Unix-style path from Git Bash or similar - convert to Windows
            drive = cwd[1].upper()
            rest = cwd[3:].replace('/', '\\')
            cwd = f"{drive}:\\{rest}"

        if not os.path.isabs(cwd):
            working_dir = Path(os.getcwd()) / cwd
        else:
            working_dir = Path(cwd)

        # Ensure the path uses proper separators for the OS
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

        try:

            worker_prompt = {
                "type": "preset",
                "preset": "claude_code",
                "append": "**Instructions:** See .flow-claude/WORKER_INSTRUCTIONS.md for your full workflow."
            }
            # Create worker-specific options WITHOUT MCP servers to avoid circular dependency
            options = ClaudeAgentOptions(
                system_prompt=worker_prompt,  # Load from file
                agents={},  # Workers don't need subagents
                allowed_tools=[
                    'Bash', 'Read', 'Write', 'Edit', 'Grep', 'Glob'
                    # No MCP tools - workers use standard tools only
                ],
                # No mcp_servers - this prevents circular dependency!
                cwd=str(working_dir),  # Use the working_dir which can be overridden
                permission_mode='acceptEdits',
                setting_sources=["user", "project", "local"]  # Explicitly set Claude CLI path
            )

            # Use the instructions provided by the orchestrator
            prompt = instructions

            if self.debug:
                self.log(f"[SDKWorkerManager] Launching worker-{worker_id} for {task_branch}")
                self.log(f"[SDKWorkerManager]   Using SDK query() function")
                self.log(f"[SDKWorkerManager]   Working directory: {str(working_dir)}")
                self.log(f"[SDKWorkerManager]   Model: {session_info.get('model', 'sonnet')}")

            # Execute worker using SDK query()
            async for message in query(prompt=prompt, options=options):
                # Parse different message types
                message_content = ""
                message_type = "text"
                tool_name = None
                tool_input = None
                tool_output = None

                # Handle different message structures
                if hasattr(message, '__dict__'):
                    # Message object with attributes
                    if hasattr(message, 'content'):
                        message_content = str(message.content)
                    if hasattr(message, 'type'):
                        message_type = str(message.type)
                    if hasattr(message, 'tool_use'):
                        # Tool use message
                        message_type = "tool_use"
                        if hasattr(message.tool_use, 'name'):
                            tool_name = message.tool_use.name
                        if hasattr(message.tool_use, 'input'):
                            tool_input = message.tool_use.input
                    if hasattr(message, 'tool_result'):
                        # Tool result message
                        message_type = "tool_result"
                        if hasattr(message.tool_result, 'output'):
                            tool_output = message.tool_result.output
                elif isinstance(message, dict):
                    # Dictionary message
                    message_content = message.get('content', '')
                    message_type = message.get('type', 'text')
                    if 'tool_use' in message:
                        message_type = "tool_use"
                        tool_name = message['tool_use'].get('name')
                        tool_input = message['tool_use'].get('input')
                    if 'tool_result' in message:
                        message_type = "tool_result"
                        tool_output = message['tool_result'].get('output')
                else:
                    # String or other type
                    message_content = str(message)

                # Enhanced logging based on message type
                if message_type == "tool_use":
                    self.log(f"[Worker-{worker_id}] [TOOL USE] {tool_name}")
                    if self.debug and tool_input:
                        self.log(f"[Worker-{worker_id}]   Input: {json.dumps(tool_input, indent=2) if isinstance(tool_input, dict) else tool_input}")
                elif message_type == "tool_result":
                    self.log(f"[Worker-{worker_id}] [TOOL RESULT]")
                    if self.debug and tool_output:
                        # Truncate long outputs
                        output_str = str(tool_output)
                        if len(output_str) > 500:
                            output_str = output_str[:500] + "... (truncated)"
                        self.log(f"[Worker-{worker_id}]   Output: {output_str}")
                elif message_content:
                    # Text content - categorize by keywords
                    lines = message_content.split('\n')
                    for line in lines:
                        if not line.strip():
                            continue

                        # Categorize output
                        if 'Using tool:' in line or 'Calling tool:' in line:
                            self.log(f"[Worker-{worker_id}] [TOOL] {line}")
                        elif 'Error:' in line or 'Failed:' in line or '[ERROR]' in line:
                            self.log(f"[Worker-{worker_id}] [ERROR] {line}")
                        elif 'Successfully' in line or 'Completed' in line or 'Created' in line:
                            self.log(f"[Worker-{worker_id}] [SUCCESS] {line}")
                        elif line.startswith('##'):
                            # Markdown headers (important sections)
                            self.log(f"[Worker-{worker_id}] [SECTION] {line}")
                        elif line.startswith('#'):
                            # Task progress headers
                            self.log(f"[Worker-{worker_id}] [TASK] {line}")
                        else:
                            # Other output (only show first 100 chars in non-debug)
                            if self.debug or len(line) <= 100:
                                self.log(f"[Worker-{worker_id}] {line}")
                            else:
                                self.log(f"[Worker-{worker_id}] {line[:100]}...")

                # Yield the parsed message
                yield {
                    'worker_id': worker_id,
                    'type': message_type,
                    'content': message_content,
                    'tool_name': tool_name,
                    'tool_input': tool_input,
                    'tool_output': tool_output
                }

            # Query completed naturally - mark worker as complete
            if worker_id in self.active_workers:
                elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
                self.log(f"[SDKWorkerManager] Worker-{worker_id} completed task {task_branch}")

                yield {
                    'worker_id': worker_id,
                    'type': 'completed',
                    'elapsed_time': elapsed,
                    'task_branch': task_branch
                }

                if self.control_queue:
                    await self._inject_completion_event(worker_id, task_branch, 0, elapsed)

        except Exception as e:
            # Handle errors
            self.log(f"[SDKWorkerManager] Worker-{worker_id} error: {str(e)}")

            yield {
                'worker_id': worker_id,
                'type': 'error',
                'error': str(e)
            }

            # Inject error event (with safe elapsed time calculation)
            if self.control_queue:
                if worker_id in self.active_workers:
                    elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
                else:
                    elapsed = 0  # Worker never started properly
                await self._inject_completion_event(worker_id, task_branch, 1, elapsed)

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

    async def run_parallel_workers(self, workers: List[Dict[str, Any]]) -> List:
        """Run multiple workers in parallel using asyncio.gather().

        Args:
            workers: List of worker configurations, each with:
                - worker_id: Worker identifier
                - task_branch: Task branch to work on
                - session_info: Session metadata
                - cwd: Working directory for the worker

        Returns:
            List of results from each worker
        """
        tasks = []

        for worker_config in workers:
            # Create async generator for each worker
            worker_gen = self.run_worker(
                worker_config['worker_id'],
                worker_config['task_branch'],
                worker_config['session_info'],
                worker_config.get('cwd', f".worktrees/worker-{worker_config['worker_id']}"),
                worker_config.get('instructions', f"Execute task on branch {worker_config['task_branch']}")
            )

            # Collect all output from the generator
            tasks.append(self._collect_worker_output(worker_gen))

        # Run all workers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def _collect_worker_output(self, worker_generator: AsyncGenerator) -> List:
        """Collect all output from a worker generator.

        Args:
            worker_generator: Async generator from run_worker

        Returns:
            List of all messages from the worker
        """
        messages = []
        async for message in worker_generator:
            messages.append(message)
        return messages

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
                          max_parallel: int = 3) -> SDKWorkerManager:
    """Get or create the global SDKWorkerManager instance.

    Args:
        control_queue: Async queue for completion events
        debug: Enable debug output
        log_func: Logging function
        max_parallel: Maximum number of concurrent workers

    Returns:
        SDKWorkerManager singleton instance
    """
    global _sdk_worker_manager

    if _sdk_worker_manager is None:
        _sdk_worker_manager = SDKWorkerManager(control_queue, debug, log_func, max_parallel)
    else:
        # Update parameters if provided
        # Always update control_queue if provided (not just when current is None)
        if control_queue:
            _sdk_worker_manager.control_queue = control_queue
        if log_func:
            _sdk_worker_manager.log = log_func
        # Always update max_parallel to ensure it's current
        _sdk_worker_manager.max_parallel = max_parallel

    return _sdk_worker_manager


# ============================================================================
# Worker Management MCP Tools (moved from git_tools.py)
# ============================================================================

@tool(
    "launch_worker_async",
    "Launch worker in background using SDK query() for async execution",
    {
        "properties": {
            "worker_id": {"type": "string", "description": "Worker ID (e.g., '1', '2', '3')"},
            "task_branch": {"type": "string", "description": "Task branch name (e.g., 'task/001-user-model')"},
            "cwd": {"type": "string", "description": "ABSOLUTE path to worker's worktree directory (e.g., '/absolute/path/.worktrees/worker-1')"},
            "session_id": {"type": "string", "description": "Session ID (e.g., 'session-20250115-120000')"},
            "plan_branch": {"type": "string", "description": "Plan branch name (e.g., 'plan/session-20250115-120000')"},
            "model": {"type": "string", "description": "Model to use (sonnet/opus/haiku)", "default": "sonnet"},
            "instructions": {"type": "string", "description": "Task-specific instructions for the worker written by the orchestrator"}
        },
        "required": ["worker_id", "task_branch", "cwd", "session_id", "plan_branch", "instructions"],
        "type": "object"
    }
)
async def launch_worker_async(args: Dict[str, Any]) -> Dict[str, Any]:
    """Launch worker in background using SDK query() function.

    This allows the orchestrator to continue immediately without blocking,
    while the worker executes in the background using the Claude SDK.

    IMPORTANT: cwd MUST be an absolute path to the worker's worktree directory!

    Args:
        args: Dict with worker_id, task_branch, cwd (ABSOLUTE path to worktree),
              session_id, plan_branch, model, and instructions

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
                    args["instructions"]  # Pass required instructions
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

        # Return a simple, clean message without JSON that won't confuse the orchestrator
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
        "properties": {
            "worker_id": {"type": "string", "description": "Optional specific worker ID to check"}
        },
        "type": "object"
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
                               cwd: str, instructions: str):
    """Helper to run SDK worker as async task.

    This collects all output from the worker and handles completion.
    """
    import logging
    logger = logging.getLogger(f"flow_claude.worker-{worker_id}")

    try:
        logger.info(f"Starting SDK worker-{worker_id} for {task_branch}")
        logger.debug(f"Working directory: {cwd}")

        # Collect all messages from the worker
        messages_received = 0
        async for message in manager.run_worker(worker_id, task_branch,
                                                session_info, cwd, instructions):
            messages_received += 1
            # Log the message for debugging
            if message.get('type') == 'error':
                logger.error(f"Worker-{worker_id} error: {message.get('error', message.get('message'))}")
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