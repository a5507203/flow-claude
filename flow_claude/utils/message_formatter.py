"""Unified message formatting and parsing for agent/worker output.

This module provides common utilities for parsing and formatting messages
from both the main orchestrator agent and SDK worker agents.
"""

import json
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List

# Import Claude SDK types for proper message handling
try:
    from claude_agent_sdk import AssistantMessage
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    AssistantMessage = None

# Import block formatters for natural language display
from flow_claude.utils.block_formatter import (
    format_text_block,
    format_tool_use_block,
    format_tool_result_block,
    format_block_natural
)


class MessageType(Enum):
    """Types of messages from agents."""
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    SUCCESS = "success"
    SECTION = "section"
    TASK = "task"


class ParsedMessage:
    """Container for parsed message data."""

    def __init__(self, message_type: MessageType, content: str = "",
                 tool_name: Optional[str] = None,
                 tool_input: Optional[Any] = None,
                 tool_output: Optional[Any] = None):
        self.message_type = message_type
        self.content = content
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_output = tool_output


def parse_agent_message(msg: Any) -> ParsedMessage:
    """Parse agent message into structured format.

    Handles different message structures from Claude SDK:
    - AssistantMessage with blocks (SDK format)
    - Object with attributes (hasattr check)
    - Dictionary
    - Raw string

    Args:
        msg: Message from agent (object, dict, or string)

    Returns:
        ParsedMessage with extracted information
    """
    message_content = ""
    message_type = MessageType.TEXT
    tool_name = None
    tool_input = None
    tool_output = None

    # Handle AssistantMessage with blocks (SDK format)
    if SDK_AVAILABLE and isinstance(msg, AssistantMessage):
        if hasattr(msg, 'content') and isinstance(msg.content, list):
            # Format each block naturally
            formatted_blocks = []
            for block in msg.content:
                formatted = format_block_natural(block, max_result_length=200)
                if formatted:
                    formatted_blocks.append(formatted)

            message_content = "\n".join(formatted_blocks) if formatted_blocks else ""
        elif hasattr(msg, 'content'):
            message_content = str(msg.content)

        return ParsedMessage(
            message_type=MessageType.TEXT,
            content=message_content
        )

    # Handle different message structures
    elif hasattr(msg, '__dict__'):
        # Message object with attributes
        if hasattr(msg, 'content'):
            message_content = str(msg.content)
        if hasattr(msg, 'type'):
            type_str = str(msg.type)
            if type_str == 'tool_use':
                message_type = MessageType.TOOL_USE
            elif type_str == 'tool_result':
                message_type = MessageType.TOOL_RESULT

        if hasattr(msg, 'tool_use'):
            # Tool use message
            message_type = MessageType.TOOL_USE
            if hasattr(msg.tool_use, 'name'):
                tool_name = msg.tool_use.name
            if hasattr(msg.tool_use, 'input'):
                tool_input = msg.tool_use.input

        if hasattr(msg, 'tool_result'):
            # Tool result message
            message_type = MessageType.TOOL_RESULT
            if hasattr(msg.tool_result, 'output'):
                tool_output = msg.tool_result.output

    elif isinstance(msg, dict):
        # Dictionary message
        message_content = msg.get('content', '')
        type_str = msg.get('type', 'text')

        if type_str == 'tool_use' or 'tool_use' in msg:
            message_type = MessageType.TOOL_USE
            tool_use = msg.get('tool_use', {})
            tool_name = tool_use.get('name')
            tool_input = tool_use.get('input')

        elif type_str == 'tool_result' or 'tool_result' in msg:
            message_type = MessageType.TOOL_RESULT
            tool_result = msg.get('tool_result', {})
            tool_output = tool_result.get('output')
    else:
        # String or other type
        message_content = str(msg)

    return ParsedMessage(
        message_type=message_type,
        content=message_content,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output
    )


def categorize_text_message(text: str) -> MessageType:
    """Categorize text message based on content keywords.

    Args:
        text: Text content to categorize

    Returns:
        MessageType indicating the category
    """
    text_lower = text.lower()

    # Check for errors
    if any(keyword in text_lower for keyword in ['error:', 'failed:', '[error]', 'exception']):
        return MessageType.ERROR

    # Check for success indicators
    if any(keyword in text_lower for keyword in ['successfully', 'completed', 'created', '✓', 'done']):
        return MessageType.SUCCESS

    # Check for tool usage
    if any(keyword in text for keyword in ['Using tool:', 'Calling tool:', '[TOOL]']):
        return MessageType.TOOL_USE

    # Check for markdown section headers
    if text.strip().startswith('##'):
        return MessageType.SECTION

    if text.strip().startswith('#'):
        return MessageType.TASK

    return MessageType.TEXT


def format_agent_message(parsed_msg: ParsedMessage, agent_name: str,
                        timestamp: Optional[str] = None,
                        debug: bool = False,
                        max_length: Optional[int] = None) -> str:
    """Format parsed message for display.

    Args:
        parsed_msg: Parsed message object
        agent_name: Name of the agent/worker (e.g., "orchestrator", "worker-1")
        timestamp: Optional timestamp string
        debug: Whether to show debug details (full tool inputs/outputs)
        max_length: Maximum length for truncation (None = no truncation)

    Returns:
        Formatted string ready for display
    """
    prefix_parts = []

    # Add timestamp if provided
    if timestamp:
        prefix_parts.append(f"[{timestamp}]")

    # Add agent name
    prefix_parts.append(f"[{agent_name.upper()}]")

    prefix = " ".join(prefix_parts)

    # Format based on message type
    if parsed_msg.message_type == MessageType.TOOL_USE:
        result = f"{prefix} [TOOL USE] {parsed_msg.tool_name or 'unknown'}"

        # Add tool input in debug mode
        if debug and parsed_msg.tool_input:
            input_str = json.dumps(parsed_msg.tool_input, indent=2) if isinstance(parsed_msg.tool_input, dict) else str(parsed_msg.tool_input)
            if max_length and len(input_str) > max_length:
                input_str = input_str[:max_length] + "... (truncated)"
            result += f"\n{prefix}   Input: {input_str}"

    elif parsed_msg.message_type == MessageType.TOOL_RESULT:
        result = f"{prefix} [TOOL RESULT]"

        # Add tool output in debug mode
        if debug and parsed_msg.tool_output:
            output_str = str(parsed_msg.tool_output)
            if max_length and len(output_str) > max_length:
                output_str = output_str[:max_length] + "... (truncated)"
            result += f"\n{prefix}   Output: {output_str}"

    else:
        # Text message - categorize and format
        if not parsed_msg.content:
            return ""

        lines = parsed_msg.content.split('\n')
        formatted_lines = []

        for line in lines:
            if not line.strip():
                continue

            # Categorize each line
            category = categorize_text_message(line)

            # Format based on category
            if category == MessageType.ERROR:
                formatted_line = f"{prefix} [ERROR] {line}"
            elif category == MessageType.SUCCESS:
                formatted_line = f"{prefix} [SUCCESS] {line}"
            elif category == MessageType.TOOL_USE:
                formatted_line = f"{prefix} [TOOL] {line}"
            elif category == MessageType.SECTION:
                formatted_line = f"{prefix} [SECTION] {line}"
            elif category == MessageType.TASK:
                formatted_line = f"{prefix} [TASK] {line}"
            else:
                # Regular text - apply max_length if specified and not in debug mode
                if max_length and not debug and len(line) > max_length:
                    line = line[:max_length] + "..."
                formatted_line = f"{prefix} {line}"

            formatted_lines.append(formatted_line)

        result = "\n".join(formatted_lines)

    return result


def format_tool_message(tool_name: str, agent_name: str,
                       timestamp: Optional[str] = None,
                       tool_input: Optional[Any] = None,
                       debug: bool = False) -> str:
    """Format tool usage message (simplified wrapper).

    Args:
        tool_name: Name of the tool being used
        agent_name: Name of the agent
        timestamp: Optional timestamp
        tool_input: Optional tool input (shown in debug mode)
        debug: Whether to show debug details

    Returns:
        Formatted tool message
    """
    parsed = ParsedMessage(
        message_type=MessageType.TOOL_USE,
        tool_name=tool_name,
        tool_input=tool_input
    )
    return format_agent_message(parsed, agent_name, timestamp, debug)


def format_tool_result(agent_name: str,
                      timestamp: Optional[str] = None,
                      tool_output: Optional[Any] = None,
                      debug: bool = False,
                      max_output_length: int = 500) -> str:
    """Format tool result message (simplified wrapper).

    Args:
        agent_name: Name of the agent
        timestamp: Optional timestamp
        tool_output: Tool output (shown in debug mode)
        debug: Whether to show debug details
        max_output_length: Maximum length for output truncation

    Returns:
        Formatted tool result message
    """
    parsed = ParsedMessage(
        message_type=MessageType.TOOL_RESULT,
        tool_output=tool_output
    )
    return format_agent_message(parsed, agent_name, timestamp, debug, max_output_length)
