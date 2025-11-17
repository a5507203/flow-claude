"""Custom Textual widgets for Flow-Claude UI."""

import sys

from textual import events
from textual.widgets import TextArea, RichLog


class SubmittingTextArea(TextArea):
    """Custom SubmittingTextArea that submits on Enter (unless Ctrl is pressed)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pre_key = ""


    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses which correspond to document inserts."""

        self._restart_blink()

        if self.read_only:
            return

        key = event.key
        insert_values = {
            "backslash":"\n",
        }

        if self.pre_key!="backslash" and event.key=="enter":
            event.prevent_default()
            event.stop()
            # Call app's submit logic
            self.app.action_submit_request()
            self.pre_key=key
            return

        if self.tab_behavior == "indent":
            if key == "escape":
                event.stop()
                event.prevent_default()
                self.screen.focus_next()
                self.pre_key = key
                return
            if self.indent_type == "tabs":
                insert_values["tab"] = "\t"
            else:
                insert_values["tab"] = " " * self._find_columns_to_next_tab_stop()

        if event.is_printable or key in insert_values:
            event.stop()
            event.prevent_default()
            insert = insert_values.get(key, event.character)
            # `insert` is not None because event.character cannot be
            # None because we've checked that it's printable.
            assert insert is not None
            start, end = self.selection
            self._replace_via_keyboard(insert, start, end)


        self.pre_key = key


class TextualStdout:
    """Stdout replacement for Textual - captures all print/click.echo output."""

    def __init__(self, app):
        self.app = app
        self.original_stdout = sys.stdout
        self._buffer = ""

    def write(self, text):
        """Write text to log widget."""
        if not text:
            return 0

        # Convert bytes to string if needed
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')

        # Convert to string if it's another type
        if not isinstance(text, str):
            text = str(text)

        # Buffer partial lines
        self._buffer += text

        # Process complete lines
        if '\n' in self._buffer:
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]  # Keep incomplete line

            for line in lines[:-1]:
                if line.strip():  # Skip empty lines
                    try:
                        self.app.call_from_thread(self._write_to_log, line)
                    except Exception:
                        # Fallback if app not ready
                        try:
                            self.original_stdout.write(line + '\n')
                        except Exception:
                            # Silently fail if both methods don't work
                            pass

        return len(text)

    def _write_to_log(self, text):
        """Internal method to write to log (runs in main thread)."""
        try:
            log = self.app.query_one(RichLog)
            log.write(text)
            log.scroll_end(animate=False)
        except Exception:
            # Silently fail if log widget not available
            pass

    def flush(self):
        """Flush buffered content."""
        if self._buffer.strip():
            try:
                self.app.call_from_thread(self._write_to_log, self._buffer)
                self._buffer = ""
            except Exception:
                # Silently fail if app not available
                pass

    def fileno(self):
        """Return invalid file descriptor to prevent real file operations."""
        raise OSError("Textual stdout has no file descriptor")

    def isatty(self):
        """Not a TTY."""
        return False


class TextualStderr(TextualStdout):
    """Stderr replacement for Textual - displays errors in red."""

    def __init__(self, app):
        super().__init__(app)
        self.original_stderr = sys.stderr

    def _write_to_log(self, text):
        """Write error text with error styling."""
        try:
            log = self.app.query_one(RichLog)
            log.write(f"[red]{text}[/red]")
            log.scroll_end(animate=False)
        except Exception:
            # Silently fail if log widget not available
            pass
