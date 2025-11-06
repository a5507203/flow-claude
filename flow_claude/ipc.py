"""
Inter-Process Communication (IPC) Layer

Provides state synchronization between executor and CLI processes via JSON files:
- state.json: Current session state
- messages.jsonl: Streaming log messages (append-only)
- control.json: Control commands (intervention, pause, stop)
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def get_session_dir(session_id: str) -> Path:
    """Get session directory path for IPC files"""
    return Path.home() / ".flow-claude" / "sessions" / session_id


class StateWriter:
    """Write session state and messages from executor process"""

    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.session_dir / "state.json"
        self.messages_file = self.session_dir / "messages.jsonl"
        self.control_file = self.session_dir / "control.json"

        # Initialize state file
        if not self.state_file.exists():
            self.write_state({
                'status': 'initializing',
                'session_id': self.session_dir.name,
                'started_at': datetime.now().isoformat(),
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
            })

    def write_state(self, state: Dict[str, Any]):
        """Write current session state (overwrites)"""
        state['updated_at'] = datetime.now().isoformat()

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def append_message(self, message: str, msg_type: str = 'info', metadata: Optional[Dict] = None):
        """Append a log message to messages.jsonl"""
        msg = {
            'time': datetime.now().isoformat(),
            'type': msg_type,
            'message': message,
        }

        if metadata:
            msg['metadata'] = metadata

        with open(self.messages_file, 'a') as f:
            f.write(json.dumps(msg) + '\n')

    def read_control_command(self) -> Optional[Dict[str, Any]]:
        """Read control command from CLI (if any), then clear it"""
        if not self.control_file.exists():
            return None

        try:
            with open(self.control_file, 'r') as f:
                command = json.load(f)

            # Clear control file after reading
            self.control_file.unlink()
            return command

        except (json.JSONDecodeError, FileNotFoundError):
            return None


class StateReader:
    """Read session state and messages from CLI process"""

    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.state_file = self.session_dir / "state.json"
        self.messages_file = self.session_dir / "messages.jsonl"
        self.control_file = self.session_dir / "control.json"

        self._last_message_position = 0

    def get_state(self) -> Dict[str, Any]:
        """Read current session state"""
        if not self.state_file.exists():
            return {'status': 'unknown'}

        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {'status': 'error', 'error': 'Failed to read state'}

    def get_new_messages(self, since_position: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Read new messages since last call (or since given position).

        Returns list of message dicts with fields:
        - time: ISO timestamp
        - type: 'info', 'error', 'warning', 'agent'
        - message: Log message text
        - position: Line number (0-indexed)
        """
        if not self.messages_file.exists():
            return []

        if since_position is None:
            since_position = self._last_message_position

        messages = []

        try:
            with open(self.messages_file, 'r') as f:
                # Skip to last read position
                for _ in range(since_position):
                    f.readline()

                # Read new messages
                for line in f:
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            msg['position'] = since_position + len(messages)

                            # Parse ISO timestamp
                            if 'time' in msg:
                                msg['time'] = datetime.fromisoformat(msg['time'])

                            messages.append(msg)
                        except json.JSONDecodeError:
                            continue

            # Update position
            self._last_message_position = since_position + len(messages)

        except FileNotFoundError:
            pass

        return messages

    def write_control_command(self, command: str, params: Optional[Dict] = None):
        """Write control command for executor to read"""
        cmd = {
            'command': command,
            'timestamp': datetime.now().isoformat(),
        }

        if params:
            cmd['params'] = params

        with open(self.control_file, 'w') as f:
            json.dump(cmd, f, indent=2)
