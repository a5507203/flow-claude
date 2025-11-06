"""
Logging Configuration for Flow-Claude Interactive CLI

Provides structured logging to both console and file for debugging.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class FlowClaudeLogger:
    """Centralized logger for Flow-Claude sessions"""

    def __init__(self, session_id: Optional[str] = None, log_dir: str = ".flow-claude/logs"):
        self.session_id = session_id or datetime.now().strftime("session-%Y%m%d-%H%M%S")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file path
        self.log_file = self.log_dir / f"{self.session_id}.log"

        # Create logger first
        self.logger = logging.getLogger(f"flow_claude.{self.session_id}")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers = []

        # File handler (detailed logs)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)8s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (only warnings and errors)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Ensure .flow-claude is in .gitignore (after logger is set up)
        self._ensure_gitignore()

        # Log session start
        self.logger.info("=" * 80)
        self.logger.info(f"Flow-Claude Interactive Session Started")
        self.logger.info(f"Session ID: {self.session_id}")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("=" * 80)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, extra=kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, extra=kwargs)

    def log_control_message(self, msg_type: str, data: dict):
        """Log control message"""
        self.logger.debug(f"Control message: {msg_type} - {data}")

    def log_orchestrator_message(self, msg_type: str, data: dict):
        """Log orchestrator message"""
        self.logger.debug(f"Orchestrator message: {msg_type} - {data}")

    def log_subprocess_output(self, stream: str, line: str):
        """Log subprocess output"""
        self.logger.debug(f"Subprocess [{stream}]: {line}")

    def log_keyboard_event(self, key: str):
        """Log keyboard event"""
        self.logger.debug(f"Keyboard event: {key}")

    def log_process_state(self, state: str, details: str = ""):
        """Log process state change"""
        self.logger.info(f"Process state: {state} {details}")

    def _ensure_gitignore(self):
        """Ensure .flow-claude is in .gitignore"""
        try:
            gitignore_path = Path.cwd() / ".gitignore"
            flow_claude_entry = ".flow-claude/"

            # Read existing .gitignore if it exists
            existing_lines = []
            if gitignore_path.exists():
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.read().splitlines()

            # Check if .flow-claude is already in .gitignore
            if flow_claude_entry in existing_lines or ".flow-claude" in existing_lines:
                return  # Already ignored

            # Add .flow-claude to .gitignore
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                # Add newline if file doesn't end with one
                if existing_lines and existing_lines[-1].strip():
                    f.write('\n')
                f.write(f'\n# Flow-Claude session logs\n')
                f.write(f'{flow_claude_entry}\n')

            self.logger.info(f"Added .flow-claude/ to .gitignore")

        except Exception as e:
            # Don't fail if we can't update .gitignore
            self.logger.warning(f"Could not update .gitignore: {e}")

    def close(self):
        """Close logger and handlers"""
        self.logger.info("=" * 80)
        self.logger.info("Flow-Claude Interactive Session Ended")
        self.logger.info("=" * 80)

        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)


def get_logger(session_id: Optional[str] = None) -> FlowClaudeLogger:
    """Get or create logger for session"""
    return FlowClaudeLogger(session_id=session_id)


def cleanup_old_logs(log_dir: str = ".flow-claude/logs", keep_days: int = 7):
    """Remove log files older than specified days"""
    import time

    log_path = Path(log_dir)
    if not log_path.exists():
        return

    cutoff_time = time.time() - (keep_days * 24 * 60 * 60)

    for log_file in log_path.glob("session-*.log"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
            except Exception:
                pass  # Ignore errors during cleanup
