"""SDK-based worker management for Flow-Claude using query() function.

This module provides worker management using the Claude SDK's query() function
instead of spawning separate subprocess. Workers run as async query() calls.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, Any
import json
import uuid

try:
    from claude_agent_sdk import query, ClaudeAgentOptions
    SDK_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Claude SDK not available: {e}")
    SDK_AVAILABLE = False
    # Fallback for development
    async def query(*args, **kwargs):
        """Fallback query function."""
        yield {"content": "SDK not available", "type": "error", "error": "Claude SDK not imported"}

    class ClaudeAgentOptions:
        """Fallback options class."""
        def __init__(self, **kwargs):
            pass


class SDKWorkerManager:
    """Manages workers using SDK query() function for parallel execution."""

    def __init__(self, control_queue: Optional[asyncio.Queue] = None,
                 debug: bool = False,
                 log_func: Optional[callable] = None):
        """Initialize SDK worker manager.

        Args:
            control_queue: Queue for injecting completion events
            debug: Enable debug logging
            log_func: Function to call for logging
        """
        self.control_queue = control_queue
        self.debug = debug
        self.log = log_func or (lambda msg: print(msg))
        self.active_workers = {}  # worker_id -> task info

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
        # Log that we're starting
        self.log(f"[SDKWorkerManager] run_worker called for worker-{worker_id}")
        self.log(f"[SDKWorkerManager]   Task branch: {task_branch}")
        self.log(f"[SDKWorkerManager]   CWD: {cwd}")
        self.log(f"[SDKWorkerManager]   SDK Available: {SDK_AVAILABLE}")

        # Track active worker
        self.active_workers[worker_id] = {
            'task_branch': task_branch,
            'cwd': cwd,
            'start_time': asyncio.get_event_loop().time()
        }

        # Build paths
        working_dir = Path(cwd).absolute()  # cwd IS the worktree path

        # Look for worker instructions file - try parent directory first (main project)
        # since .flow-claude is typically in the main project, not in worktree
        parent_dir = working_dir.parent.parent  # Go up from .worktrees/worker-X to project root
        flow_claude_dir = parent_dir / ".flow-claude"
        worker_prompt_file = flow_claude_dir / "WORKER_INSTRUCTIONS.md"

        # Fallback to worktree if not found in parent
        if not worker_prompt_file.exists():
            flow_claude_dir = working_dir / ".flow-claude"
            worker_prompt_file = flow_claude_dir / "WORKER_INSTRUCTIONS.md"

        # Check if SDK is available
        if not SDK_AVAILABLE:
            self.log(f"[SDKWorkerManager] ERROR: Claude SDK not available!")
            yield {
                'worker_id': worker_id,
                'type': 'error',
                'message': "Claude SDK is not available - cannot run worker"
            }
            return

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
            # Import git_tools for MCP server
            from .git_tools import create_git_tools_server

            # Create worker-specific options
            options = ClaudeAgentOptions(
                system_prompt=f"@{worker_prompt_file}",  # Load from file
                agents={},  # Workers don't need subagents
                allowed_tools=[
                    'Bash', 'Read', 'Write', 'Edit', 'Grep', 'Glob',
                    'mcp__git__parse_task',
                    'mcp__git__parse_plan',
                    'mcp__git__parse_worker_commit',
                    'mcp__git__get_provides'
                ],
                mcp_servers={"git": create_git_tools_server()},
                cwd=str(working_dir),  # Use the working_dir which can be overridden
                permission_mode='acceptEdits'
            )

            # Use the instructions provided by the orchestrator
            prompt = instructions

            if self.debug:
                self.log(f"[SDKWorkerManager] Launching worker-{worker_id} for {task_branch}")
                self.log(f"[SDKWorkerManager]   Using SDK query() function")
                self.log(f"[SDKWorkerManager]   Working directory: {working_dir}")
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
                        elif self.debug:
                            # Only log all lines in debug mode
                            self.log(f"[Worker-{worker_id}] {line}")

                # Yield worker message for tracking
                yield {
                    'worker_id': worker_id,
                    'type': 'message',
                    'message_type': message_type,
                    'content': message_content,
                    'tool_name': tool_name,
                    'tool_input': tool_input,
                    'tool_output': tool_output
                }

                # Check for completion signal
                if "TASK_COMPLETED" in message_content.upper():
                    # Worker signaled completion
                    elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']

                    yield {
                        'worker_id': worker_id,
                        'type': 'completed',
                        'elapsed_time': elapsed,
                        'task_branch': task_branch
                    }

                    # Inject completion event if control_queue available
                    if self.control_queue:
                        await self._inject_completion_event(worker_id, task_branch, 0, elapsed)

                    break

        except Exception as e:
            # Handle errors
            self.log(f"[SDKWorkerManager] Worker-{worker_id} error: {str(e)}")

            yield {
                'worker_id': worker_id,
                'type': 'error',
                'error': str(e)
            }

            # Inject error event
            if self.control_queue:
                elapsed = asyncio.get_event_loop().time() - self.active_workers[worker_id]['start_time']
                await self._inject_completion_event(worker_id, task_branch, 1, elapsed)

        finally:
            # Clean up
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
            if self.debug:
                self.log(f"[SDKWorkerManager] Injected completion event for worker-{worker_id}")
        except Exception as e:
            self.log(f"[SDKWorkerManager] Error injecting event: {e}")

    async def run_parallel_workers(self, workers: List[Dict[str, Any]]) -> List:
        """Run multiple workers in parallel using asyncio.gather().

        Args:
            workers: List of worker configs, each with:
                - id: Worker identifier
                - task_branch: Task branch name
                - worktree_path: Worktree path
                - session_info: Session metadata

        Returns:
            List of worker results
        """
        if self.debug:
            self.log(f"[SDKWorkerManager] Starting {len(workers)} workers in parallel")

        # Create tasks for each worker
        tasks = []
        for worker in workers:
            task = self.run_worker(
                worker['id'],
                worker['task_branch'],
                worker['worktree_path'],
                worker['session_info']
            )
            # Convert async generator to list
            task = self._collect_worker_output(task)
            tasks.append(task)

        # Run all workers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        if self.debug:
            self.log(f"[SDKWorkerManager] All {len(workers)} workers completed")

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
                          log_func: Optional[callable] = None) -> SDKWorkerManager:
    """Get or create the global SDKWorkerManager instance.

    Args:
        control_queue: Async queue for completion events
        debug: Enable debug output
        log_func: Logging function

    Returns:
        SDKWorkerManager singleton instance
    """
    global _sdk_worker_manager

    if _sdk_worker_manager is None:
        _sdk_worker_manager = SDKWorkerManager(control_queue, debug, log_func)
    elif control_queue and _sdk_worker_manager.control_queue is None:
        # Update control queue if provided
        _sdk_worker_manager.control_queue = control_queue
        # Update log function if provided
        if log_func:
            _sdk_worker_manager.log = log_func

    return _sdk_worker_manager