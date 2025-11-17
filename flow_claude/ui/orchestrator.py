"""Orchestrator session management for Flow-Claude UI."""

import asyncio

from textual.widgets import RichLog


class OrchestratorRunner:
    """Manages orchestrator session execution."""

    def __init__(self, app):
        """Initialize orchestrator runner.

        Args:
            app: The FlowCLI app instance
        """
        self.app = app

    async def run_orchestrator(self, request: str):
        """Run the orchestrator session (runs in background).

        Args:
            request: The initial development request
        """
        from flow_claude.cli import run_development_session
        from flow_claude.sdk_workers import get_sdk_worker_manager

        # Initialize SDK-based worker manager
        sdk_worker_manager = get_sdk_worker_manager(
            control_queue=self.app.control_queue,
            debug=self.app.debug_mode,
            log_func=self._create_worker_log_func(),
            max_parallel=self.app.max_parallel
        )

        # Determine execution mode
        enable_parallel = self.app.max_parallel > 1
        num_workers = self.app.max_parallel if enable_parallel else 1

        try:
            await run_development_session(
                initial_request=request,
                session_id=self.app.session_id,
                model=self.app.model,
                max_turns=1000,  # Reduced from 100 - orchestrator should complete after launching workers
                permission_mode="bypassPermissions",
                enable_parallel=enable_parallel,
                max_parallel=self.app.max_parallel,
                verbose=self.app.verbose_mode,
                debug=self.app.debug_mode,
                num_workers=num_workers,
                control_queue=self.app.control_queue,
                logger=self.app.logger,
                auto_mode=self.app.auto_mode,
                resume_session_id=self.app.orchestrator_session_id
            )

            # Capture session ID after session completes
            from flow_claude import cli
            if hasattr(cli, '_current_session_id') and cli._current_session_id:
                self.app.orchestrator_session_id = cli._current_session_id

            # Session completed - ready for next request
            log = self.app.query_one(RichLog)
            self.app._log("\n[dim]Session ready for next request...[/dim]\n")

        except asyncio.CancelledError:
            log = self.app.query_one(RichLog)
            self.app._log("[yellow]Session cancelled[/yellow]")
        except Exception as e:
            self.app.logger.exception(f"Orchestrator error: {e}")
            log = self.app.query_one(RichLog)
            self.app._log(f"[.error]ERROR: {e}[/.error]")

    def _create_worker_log_func(self):
        """Create a logging function that writes to the UI log AND file log.

        Returns:
            Callable that logs worker messages
        """
        def worker_log(msg: str):
            log = self.app.query_one(RichLog)
            # Always show worker output (it's important for tracking progress)
            # Use different styling for different message types
            if "[WORKER-" in msg and "ERROR]" in msg:
                # Error messages from workers
                self.app._log(f"[red]{msg}[/red]")
            elif "[WORKER-" in msg and "]" in msg:
                # Normal output from workers
                self.app._log(f"[cyan]{msg}[/cyan]")
            elif "[WorkerManager]" in msg and self.app.debug_mode:
                # Manager debug messages only in debug mode
                self.app._log(f"[dim]{msg}[/dim]")
            elif "[SDKWorkerManager]" in msg and self.app.debug_mode:
                # SDK Manager debug messages only in debug mode
                self.app._log(f"[dim]{msg}[/dim]")
            elif "[WORKER" in msg:
                # Other worker-related messages
                self.app._log(f"[blue]{msg}[/blue]")

            # Also record to file log (important for debugging and tracking)
            if self.app.logger:
                # Remove color markup, record plain text to file
                clean_msg = msg  # Already plain text
                if "ERROR]" in msg:
                    self.app.logger.error(clean_msg)
                elif "WARNING]" in msg or "WARN]" in msg:
                    self.app.logger.warning(clean_msg)
                elif self.app.debug_mode or "[SDKWorkerManager]" not in msg:
                    # Record all worker messages; manager debug only in debug mode
                    self.app.logger.info(clean_msg)

        return worker_log
