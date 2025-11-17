"""Convert JSON messages to readable text format.

This module provides utilities to parse JSON structures from tool outputs
and messages, then convert them into human-readable text format for better
terminal display.
"""

import json
import textwrap
from typing import Any, Dict, Union, List


class TextFormatter:
    """Convert JSON messages to readable text."""

    def __init__(self, indent: str = "  ", max_width: int = 100):
        """Initialize the text formatter.

        Args:
            indent: String to use for indentation (default: 2 spaces)
            max_width: Maximum line width before wrapping (default: 100)
        """
        self.indent = indent
        self.max_width = max_width

    def json_to_text(self, data: Union[Dict, str, List], level: int = 0) -> str:
        """Convert JSON data to readable text format.

        Args:
            data: JSON data (dict, list, or string)
            level: Indentation level for nested structures

        Returns:
            Human-readable text string
        """
        # Convert string to dict/list if it's JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                # Not JSON - return as-is
                return data

        # Handle different data types
        if isinstance(data, dict):
            return self._dict_to_text(data, level)
        elif isinstance(data, list):
            return self._list_to_text(data, level)
        else:
            return str(data)

    def _dict_to_text(self, data: Dict, level: int = 0) -> str:
        """Convert dictionary to readable text.

        Args:
            data: Dictionary data
            level: Indentation level

        Returns:
            Formatted text string
        """
        if not data:
            return "(empty)"

        lines = []
        prefix = self.indent * level

        for key, value in data.items():
            # Format the key nicely (capitalize, replace underscores)
            formatted_key = self._format_key(key)

            if isinstance(value, dict):
                # Nested dict
                lines.append(f"{prefix}{formatted_key}:")
                lines.append(self._dict_to_text(value, level + 1))
            elif isinstance(value, list):
                # List value
                lines.append(f"{prefix}{formatted_key}:")
                lines.append(self._list_to_text(value, level + 1))
            else:
                # Simple value with wrapping
                formatted_value = self._format_value(value)
                key_part = f"{prefix}{formatted_key}: "

                # Wrap long values
                if len(key_part) + len(formatted_value) > self.max_width:
                    # Value is too long - wrap it
                    wrapped_value = self._wrap_text(
                        formatted_value,
                        prefix=key_part,
                        subsequent_indent=prefix + self.indent
                    )
                    lines.append(f"{key_part}{wrapped_value.split(chr(10))[0]}")
                    # Add remaining wrapped lines
                    for wrapped_line in wrapped_value.split('\n')[1:]:
                        lines.append(wrapped_line)
                else:
                    lines.append(f"{key_part}{formatted_value}")

        return "\n".join(lines)

    def _list_to_text(self, data: List, level: int = 0) -> str:
        """Convert list to readable text.

        Args:
            data: List data
            level: Indentation level

        Returns:
            Formatted text string
        """
        if not data:
            return self.indent * level + "(none)"

        lines = []
        prefix = self.indent * level

        for i, item in enumerate(data, 1):
            if isinstance(item, dict):
                # Dict item - show as structured
                lines.append(f"{prefix}- Item {i}:")
                lines.append(self._dict_to_text(item, level + 1))
            elif isinstance(item, list):
                # Nested list
                lines.append(f"{prefix}- Item {i}:")
                lines.append(self._list_to_text(item, level + 1))
            else:
                # Simple item
                lines.append(f"{prefix}- {self._format_value(item)}")

        return "\n".join(lines)

    def _format_key(self, key: str) -> str:
        """Format a dictionary key for display.

        Args:
            key: Raw key string

        Returns:
            Formatted key string
        """
        # Replace underscores with spaces and capitalize
        formatted = key.replace('_', ' ').title()
        return formatted

    def _format_value(self, value: Any) -> str:
        """Format a value for display.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if isinstance(value, bool):
            return "Yes" if value else "No"
        elif value is None:
            return "(none)"
        elif isinstance(value, str):
            return value  # Don't truncate here, let wrapping handle it
        else:
            return str(value)

    def _wrap_text(self, text: str, prefix: str = "", subsequent_indent: str = "") -> str:
        """Wrap text to fit within max_width.

        Args:
            text: Text to wrap
            prefix: Prefix for first line (e.g., "  Command: ")
            subsequent_indent: Indent for wrapped lines (e.g., "    ")

        Returns:
            Wrapped text (without the prefix - caller adds it)
        """
        # Calculate available width for first line (after prefix)
        first_line_width = self.max_width - len(prefix)
        # Calculate available width for subsequent lines (after indent)
        subsequent_width = self.max_width - len(subsequent_indent)

        if len(text) <= first_line_width:
            # No wrapping needed
            return text

        # Manual wrapping to handle first line width differently from subsequent lines
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        target_width = first_line_width

        for word in words:
            # Check if adding this word would exceed the limit
            word_length = len(word) + (1 if current_line else 0)  # +1 for space

            if current_length + word_length <= target_width:
                # Word fits on current line
                current_line.append(word)
                current_length += word_length
            else:
                # Start a new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
                # After first line, use subsequent_width
                target_width = subsequent_width

        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))

        # Join with newline and subsequent indent
        if len(lines) > 1:
            return lines[0] + "\n" + "\n".join(subsequent_indent + line for line in lines[1:])
        else:
            return lines[0] if lines else text

    def format_tool_input(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Format tool input parameters as readable text.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Formatted text string
        """
        lines = [f"Tool: {tool_name}"]

        if not tool_input:
            lines.append("  (no parameters)")
        else:
            # Special formatting for common tools with wrapping
            if tool_name == "Bash":
                command = tool_input.get("command", "")
                description = tool_input.get("description", "")
                if description:
                    # Wrap description if needed
                    wrapped = self._wrap_text(description, "  Description: ", "    ")
                    first_line, *rest_lines = wrapped.split('\n')
                    lines.append(f"  Description: {first_line}")
                    lines.extend(rest_lines)

                # Wrap command if needed
                wrapped = self._wrap_text(command, "  Command: ", "    ")
                first_line, *rest_lines = wrapped.split('\n')
                lines.append(f"  Command: {first_line}")
                lines.extend(rest_lines)

            elif tool_name in ("Read", "Write", "Edit"):
                file_path = tool_input.get("file_path", "")
                # Wrap file path if needed
                wrapped = self._wrap_text(file_path, "  File: ", "    ")
                first_line, *rest_lines = wrapped.split('\n')
                lines.append(f"  File: {first_line}")
                lines.extend(rest_lines)

                if "content" in tool_input:
                    content_len = len(tool_input["content"])
                    lines.append(f"  Content: {content_len} characters")
                if "old_string" in tool_input:
                    old_len = len(tool_input["old_string"])
                    new_len = len(tool_input.get("new_string", ""))
                    lines.append(f"  Changes: {old_len} → {new_len} characters")

            elif tool_name == "Grep":
                pattern = tool_input.get("pattern", "")
                path = tool_input.get("path", ".")
                lines.append(f"  Pattern: {pattern}")
                lines.append(f"  Path: {path}")

            elif tool_name == "Glob":
                pattern = tool_input.get("pattern", "")
                lines.append(f"  Pattern: {pattern}")

            elif tool_name == "Task":
                subagent = tool_input.get("subagent_type", "")
                description = tool_input.get("description", "")
                lines.append(f"  Subagent: {subagent}")
                if description:
                    # Wrap task description if needed
                    wrapped = self._wrap_text(description, "  Task: ", "    ")
                    first_line, *rest_lines = wrapped.split('\n')
                    lines.append(f"  Task: {first_line}")
                    lines.extend(rest_lines)
            else:
                # Generic formatting for other tools
                lines.append(self.json_to_text(tool_input, level=1))

        return "\n".join(lines)

    def format_tool_result(self, result: Any, is_error: bool = False) -> str:
        """Format tool result as readable text.

        Args:
            result: Tool result (any type)
            is_error: Whether this is an error result

        Returns:
            Formatted text string
        """
        status = "ERROR" if is_error else "SUCCESS"
        lines = [f"Result: {status}"]

        # Try to parse as JSON
        try:
            if isinstance(result, str):
                data = json.loads(result)
            elif isinstance(result, dict):
                data = result
            else:
                data = None

            if data:
                lines.append(self.json_to_text(data, level=1))
                return "\n".join(lines)
        except (json.JSONDecodeError, TypeError):
            pass

        # Not JSON - just show as text
        result_str = str(result)
        # Truncate very long results
        if len(result_str) > 500:
            result_str = result_str[:500] + "\n  ... (truncated)"

        lines.append(f"  {result_str}")
        return "\n".join(lines)


# Global formatter instance
_formatter = None


def get_text_formatter(indent: str = "  ", max_width: int = 100) -> TextFormatter:
    """Get or create the global text formatter instance.

    Args:
        indent: Indentation string
        max_width: Maximum line width before wrapping

    Returns:
        TextFormatter instance
    """
    global _formatter
    if _formatter is None:
        _formatter = TextFormatter(indent=indent, max_width=max_width)
    return _formatter


def json_to_text(data: Union[Dict, str, List]) -> str:
    """Convenience function to convert JSON to text.

    Args:
        data: JSON data (dict, list, or string)

    Returns:
        Human-readable text string
    """
    formatter = get_text_formatter()
    return formatter.json_to_text(data)


def format_tool_input(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Convenience function to format tool input.

    Args:
        tool_name: Tool name
        tool_input: Tool input parameters

    Returns:
        Formatted text string
    """
    formatter = get_text_formatter()
    return formatter.format_tool_input(tool_name, tool_input)


def format_tool_result(result: Any, is_error: bool = False) -> str:
    """Convenience function to format tool result.

    Args:
        result: Tool result
        is_error: Whether this is an error

    Returns:
        Formatted text string
    """
    formatter = get_text_formatter()
    return formatter.format_tool_result(result, is_error)
