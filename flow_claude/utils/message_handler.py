"""Unified message handling for orchestrator and workers.

This module provides a centralized MessageHandler class that eliminates
duplicate message parsing and formatting logic across cli.py and sdk_workers.py.
"""

from datetime import datetime
from typing import Optional, Callable, Any

from .message_formatter import parse_agent_message, format_agent_message, MessageType


class MessageHandler:
    """Unified message handler for agents and workers.

    Handles message parsing, formatting, and output with support for:
    - Debug and verbose modes
    - UI integration (Textual)
    - File logging
    - Agent identification
    """

    def __init__(
        self,
        agent_name: str,
        debug: bool = False,
        verbose: bool = False,
        log_func: Optional[Callable[[str], None]] = None,
        ui_handler: Optional[Any] = None,
        file_logger: Optional[Any] = None,
        max_length: Optional[int] = 100
    ):
        """Initialize message handler.

        Args:
            agent_name: Name of the agent (e.g., "orchestrator", "worker-1")
            debug: Enable debug mode (show timestamps, full details)
            verbose: Enable verbose mode (show more information)
            log_func: Function to call for logging (default: print)
            ui_handler: Optional UI handler with write_message method
            file_logger: Optional file logger with info/error/warning methods
            max_length: Maximum length for truncation (None = no truncation)
        """
        self.agent_name = agent_name
        self.debug = debug
        self.verbose = verbose
        self.log = log_func or print
        self.ui_handler = ui_handler
        self.file_logger = file_logger
        self.max_length = max_length if not debug else None  # No truncation in debug mode

    def handle_generic_message(self, message: Any) -> Optional[str]:
        """Handle generic message (object/dict/string format).

        This is the main entry point for workers and simple message handling.
        Parses the message, formats it, and outputs via configured channels.

        Args:
            message: Message to handle (can be object, dict, or string)

        Returns:
            Formatted message string (or None if empty)
        """
        # Parse message using unified parser
        parsed = parse_agent_message(message)

        # Skip empty messages
        if not parsed.content and parsed.message_type == MessageType.TEXT:
            if not parsed.tool_name:  # No tool either
                return None

        # Get timestamp if in debug mode
        timestamp = self._get_timestamp() if self.debug else None

        # Format message using unified formatter
        formatted = format_agent_message(
            parsed,
            agent_name=self.agent_name,
            timestamp=timestamp,
            debug=self.debug,
            max_length=self.max_length
        )

        # Output via configured channels
        if formatted:
            self._output(formatted, parsed)

        return formatted

    def _get_timestamp(self) -> str:
        """Get current timestamp string.

        Returns:
            Timestamp in HH:MM:SS format
        """
        return datetime.now().strftime("%H:%M:%S")

    def _output(self, formatted: str, parsed):
        """Output formatted message to configured channels.

        Args:
            formatted: Formatted message string
            parsed: Parsed message object (for determining log level)
        """
        # Output to UI handler if available
        if self.ui_handler and hasattr(self.ui_handler, 'write_message'):
            try:
                timestamp = self._get_timestamp() if self.debug else None
                self.ui_handler.write_message(
                    message=formatted,
                    agent=self.agent_name,
                    timestamp=timestamp
                )
            except Exception:
                # Fallback to log function if UI fails
                self.log(formatted)
        else:
            # Output to log function (print or custom)
            self.log(formatted)

        # Output to file logger if available
        if self.file_logger:
            # Determine log level based on message type
            if parsed.message_type == MessageType.ERROR:
                self.file_logger.error(formatted)
            elif 'warning' in formatted.lower() or 'warn' in formatted.lower():
                self.file_logger.warning(formatted)
            else:
                self.file_logger.info(formatted)

    def update_config(self, **kwargs):
        """Update handler configuration dynamically.

        Args:
            **kwargs: Configuration options to update (debug, verbose, etc.)
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

                # Update max_length if debug mode changes
                if key == 'debug':
                    self.max_length = None if value else 100


def create_worker_message_handler(
    worker_id: str,
    debug: bool = False,
    log_func: Optional[Callable[[str], None]] = None
) -> MessageHandler:
    """Create a message handler configured for a worker.

    Args:
        worker_id: Worker ID (e.g., "1", "2", "3")
        debug: Enable debug mode
        log_func: Logging function

    Returns:
        Configured MessageHandler instance
    """
    return MessageHandler(
        agent_name=f"worker-{worker_id}",
        debug=debug,
        log_func=log_func,
        max_length=100 if not debug else None
    )


def create_orchestrator_message_handler(
    debug: bool = False,
    verbose: bool = False,
    log_func: Optional[Callable[[str], None]] = None,
    ui_handler: Optional[Any] = None,
    file_logger: Optional[Any] = None
) -> MessageHandler:
    """Create a message handler configured for the orchestrator.

    Args:
        debug: Enable debug mode
        verbose: Enable verbose mode
        log_func: Logging function
        ui_handler: UI handler for Textual integration
        file_logger: File logger for session logging

    Returns:
        Configured MessageHandler instance
    """
    return MessageHandler(
        agent_name="orchestrator",
        debug=debug,
        verbose=verbose,
        log_func=log_func,
        ui_handler=ui_handler,
        file_logger=file_logger,
        max_length=None  # No truncation for orchestrator
    )
