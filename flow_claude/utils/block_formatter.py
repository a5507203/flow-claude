"""Block formatters for Claude SDK message content blocks.

Provides natural language formatting for TextBlock, ToolUseBlock, and ToolResultBlock
without showing internal IDs or technical details.
"""

import json
from typing import Any, Optional


def format_text_block(block: Any) -> str:
    """Format TextBlock content.

    Args:
        block: TextBlock with .text attribute

    Returns:
        Formatted text content (just the text itself)
    """
    if not hasattr(block, 'text'):
        return str(block)

    return block.text.strip() if block.text else ""


def format_tool_use_block(block: Any) -> str:
    """Format ToolUseBlock in natural language (no IDs).

    Args:
        block: ToolUseBlock with .name and .input attributes

    Returns:
        Natural language description of tool usage

    Example:
        Input: ToolUseBlock(name='Bash', input={'command': 'git status'})
        Output: "Running: git status"
    """
    if not hasattr(block, 'name'):
        return str(block)

    tool_name = block.name
    tool_input = block.input if hasattr(block, 'input') else {}

    # Format based on tool type
    if tool_name == 'Bash':
        command = tool_input.get('command', '')
        if command:
            return f"Running: {command}"
        return f"Running shell command"

    elif tool_name == 'Read':
        file_path = tool_input.get('file_path', '')
        if file_path:
            return f"Reading: {file_path}"
        return "Reading file"

    elif tool_name == 'Write':
        file_path = tool_input.get('file_path', '')
        if file_path:
            return f"Writing: {file_path}"
        return "Writing file"

    elif tool_name == 'Edit':
        file_path = tool_input.get('file_path', '')
        if file_path:
            return f"Editing: {file_path}"
        return "Editing file"

    elif tool_name == 'Grep':
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '')
        if pattern and path:
            return f"Searching '{pattern}' in {path}"
        elif pattern:
            return f"Searching: {pattern}"
        return "Searching files"

    elif tool_name == 'Glob':
        pattern = tool_input.get('pattern', '')
        if pattern:
            return f"Finding files: {pattern}"
        return "Finding files"

    elif tool_name.startswith('mcp__git__'):
        # Git MCP tools
        git_tool = tool_name.replace('mcp__git__', '')
        if git_tool == 'parse_task':
            return "Reading task metadata"
        elif git_tool == 'parse_plan':
            return "Reading execution plan"
        elif git_tool == 'parse_worker_commit':
            return "Checking worker commit"
        elif git_tool == 'get_provides':
            return "Getting completed task capabilities"
        elif git_tool == 'create_task_branch':
            return "Creating task branch"
        elif git_tool == 'update_plan_branch':
            return "Updating execution plan"
        else:
            return f"Git: {git_tool}"

    elif tool_name.startswith('mcp__'):
        # Other MCP tools - extract server and tool name
        parts = tool_name.split('__')
        if len(parts) >= 3:
            server_name = parts[1]
            tool = parts[2]
            return f"{server_name.title()}: {tool}"
        return f"Using: {tool_name}"

    else:
        # Generic tool - just show the name
        return f"Using: {tool_name}"


def format_tool_result_block(block: Any, max_length: int = 200) -> Optional[str]:
    """Format ToolResultBlock content (no IDs, clean output).

    Args:
        block: ToolResultBlock with .content and .is_error attributes
        max_length: Maximum length for result display (0 = no limit)

    Returns:
        Formatted result content, or None if empty/error

    Example:
        Input: ToolResultBlock(content="On branch main\\nnothing to commit")
        Output: "On branch main"
    """
    if not hasattr(block, 'content'):
        return None

    content = block.content
    is_error = getattr(block, 'is_error', False)

    # Skip error results - they'll be shown in error handling
    if is_error:
        return None

    # Handle None/empty content
    if content is None or content == "":
        return None

    # Convert content to string
    if isinstance(content, list):
        # List of content items (e.g., from MCP tools)
        content_str = json.dumps(content, indent=2)
    elif isinstance(content, dict):
        content_str = json.dumps(content, indent=2)
    else:
        content_str = str(content)

    # Clean up the content
    content_str = content_str.strip()

    # Skip if empty after stripping
    if not content_str:
        return None

    # Truncate if too long (unless max_length=0)
    if max_length > 0 and len(content_str) > max_length:
        lines = content_str.split('\n')
        if len(lines) > 3:
            # Show first 3 lines
            content_str = '\n'.join(lines[:3]) + f"\n... ({len(lines)-3} more lines)"
        else:
            # Truncate single long line
            content_str = content_str[:max_length] + "..."

    return content_str


def format_block_natural(block: Any, max_result_length: int = 200) -> Optional[str]:
    """Format any content block in natural language.

    Determines block type and calls appropriate formatter.

    Args:
        block: Content block (TextBlock, ToolUseBlock, or ToolResultBlock)
        max_result_length: Maximum length for tool result display

    Returns:
        Formatted string, or None if block should be skipped
    """
    block_type = type(block).__name__

    if block_type == 'TextBlock':
        return format_text_block(block)

    elif block_type == 'ToolUseBlock':
        return format_tool_use_block(block)

    elif block_type == 'ToolResultBlock':
        return format_tool_result_block(block, max_result_length)

    else:
        # Unknown block type - return string representation
        return str(block)
