"""
Orchestrator with Async Event Queue Communication

Provides real-time bidirectional communication between CLI and orchestrator
using async queues for message passing.
"""

import asyncio
import os
import sys
import subprocess
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class OrchestratorSession:
    """Orchestrator with event queue communication for interactive CLI"""

    def __init__(self,
                 request: str,
                 message_queue: asyncio.Queue,
                 control_queue: asyncio.Queue,
                 model: str = 'sonnet',
                 max_parallel: int = 3,
                 verbose: bool = False,
                 debug: bool = False):
        self.request = request
        self.message_queue = message_queue
        self.control_queue = control_queue
        self.model = model
        self.max_parallel = max_parallel
        self.verbose = verbose
        self.debug = debug

        # State
        self.shutdown_event = asyncio.Event()
        self.paused = False
        self.workers = []
        self.current_wave = 0
        self.total_tasks = 0
        self.completed_tasks = 0

    async def run(self):
        """Main orchestrator loop with queue communication"""
        try:
            await self.send_message("status", {"message": "Initializing Flow-Claude session..."})

            # Check git repository
            if not os.path.exists('.git'):
                await self.send_message("status", {"message": "Initializing git repository..."})
                await self.init_git_repo()

            # Build command for existing CLI
            cmd = self.build_cli_command()

            await self.send_message("status", {"message": f"Starting orchestrator with {self.max_parallel} workers"})
            await self.send_message("agent_start", {
                "agent": "orchestrator",
                "message": f"Model: {self.model}, Max parallel: {self.max_parallel}"
            })

            # Run the existing CLI and capture output
            await self.run_cli_process(cmd)

        except asyncio.CancelledError:
            await self.send_message("status", {"message": "Session cancelled by user"})
            await self.cleanup()
            raise

        except Exception as e:
            await self.send_message("error", {"message": f"Orchestrator error: {str(e)}"})
            if self.debug:
                import traceback
                await self.send_message("error", {"message": traceback.format_exc()})
            await self.cleanup()

    def build_cli_command(self) -> List[str]:
        """Build command to run existing CLI"""
        cmd = [
            sys.executable, "-m", "flow_claude.cli", "develop",
            self.request,
            "--model", self.model,
            "--max-parallel", str(self.max_parallel),
        ]

        if self.verbose:
            cmd.append("--verbose")
        if self.debug:
            cmd.append("--debug")

        return cmd

    async def run_cli_process(self, cmd: List[str]):
        """Run CLI process and stream output"""
        await self.send_message("status", {"message": "Starting development session..."})

        # Start process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd()
        )

        self.workers.append(process)

        # Create tasks for reading output
        stdout_task = asyncio.create_task(self.stream_output(process.stdout, "stdout"))
        stderr_task = asyncio.create_task(self.stream_output(process.stderr, "stderr"))
        control_task = asyncio.create_task(self.monitor_control_queue(process))

        # Wait for process to complete or shutdown
        try:
            await asyncio.gather(stdout_task, stderr_task, control_task)
            returncode = await process.wait()

            if returncode == 0:
                await self.send_message("complete", {"status": "success"})
            else:
                await self.send_message("error", {"message": f"Process exited with code {returncode}"})

        except asyncio.CancelledError:
            # Kill process on cancellation
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            raise

    async def stream_output(self, stream, stream_type: str):
        """Stream output from subprocess to message queue"""
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break

                line_str = line.decode('utf-8', errors='ignore').rstrip()
                if line_str:
                    # Determine message type based on content
                    msg_type = self.classify_message(line_str)

                    await self.send_message(msg_type, {
                        "message": line_str,
                        "stream": stream_type
                    })

        except asyncio.CancelledError:
            pass

    def classify_message(self, line: str) -> str:
        """Classify message type based on content"""
        line_lower = line.lower()

        if "error" in line_lower or "failed" in line_lower:
            return "error"
        elif "warning" in line_lower or "warn" in line_lower:
            return "warning"
        elif "agent" in line_lower or "worker" in line_lower or "planner" in line_lower:
            return "agent_output"
        elif "complete" in line_lower or "done" in line_lower or "finished" in line_lower:
            return "task_progress"
        else:
            return "status"

    async def monitor_control_queue(self, process):
        """Monitor control queue for shutdown/intervention signals"""
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Check for control messages (non-blocking with timeout)
                    control = await asyncio.wait_for(
                        self.control_queue.get(),
                        timeout=0.5
                    )

                    await self.handle_control_message(control, process)

                except asyncio.TimeoutError:
                    continue  # No messages, keep checking

        except asyncio.CancelledError:
            pass

    async def handle_control_message(self, control: dict, process):
        """Handle control message from CLI"""
        control_type = control.get("type")

        if control_type == "shutdown":
            await self.send_message("status", {"message": "Shutdown requested, cleaning up..."})
            self.shutdown_event.set()

            # Terminate process
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

            await self.cleanup()

        elif control_type == "intervention":
            requirement = control.get("data", {}).get("requirement", "")
            await self.send_message("status", {
                "message": f"Intervention: Adding requirement: {requirement}"
            })
            # TODO: Implement intervention handling
            # For now, just log it

    async def init_git_repo(self):
        """Initialize git repository"""
        try:
            # Init git
            proc = await asyncio.create_subprocess_exec(
                'git', 'init',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()

            await self.send_message("status", {"message": "Git repository initialized"})

            # Create initial commit
            proc = await asyncio.create_subprocess_exec(
                'git', 'commit', '--allow-empty', '-m', 'Initial commit',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()

            await self.send_message("status", {"message": "Initial commit created"})

        except Exception as e:
            await self.send_message("error", {"message": f"Failed to init git: {str(e)}"})

    async def cleanup(self):
        """Clean up resources"""
        await self.send_message("status", {"message": "Cleaning up resources..."})

        # Terminate all workers
        for worker in self.workers:
            if worker.returncode is None:
                worker.terminate()
                try:
                    await asyncio.wait_for(worker.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    worker.kill()
                    await worker.wait()

        await self.send_message("status", {"message": "Cleanup complete"})

    async def send_message(self, msg_type: str, data: dict):
        """Send message to CLI via queue"""
        message = {
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        await self.message_queue.put(message)
