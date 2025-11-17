"""Test the text formatter to see JSON-to-text conversion.

This script demonstrates how the formatter converts JSON messages
into readable text format.
"""

from flow_claude.utils.text_formatter import format_tool_input, format_tool_result, json_to_text
import json


def test_bash_tool():
    """Test formatting Bash tool."""
    print("=" * 60)
    print("BASH TOOL - Before (JSON):")
    print("=" * 60)

    tool_input = {
        "command": 'cd "C:/Users/Yu/Downloads/ziwei/.worktrees/worker-1/frontend" && mkdir -p tests/e2e tests/pages tests/fixtures',
        "description": "Create test directory structure"
    }

    print(json.dumps(tool_input, indent=2))

    print("\n" + "=" * 60)
    print("BASH TOOL - After (Readable Text with wrapping):")
    print("=" * 60)

    formatted = format_tool_input("Bash", tool_input)
    print(formatted)
    print()


def test_long_text_wrapping():
    """Test wrapping of very long text."""
    print("=" * 60)
    print("LONG TEXT WRAPPING - Before (very long line):")
    print("=" * 60)

    tool_input = {
        "command": 'cd "C:/Users/Yu/Downloads/ziwei/.worktrees/worker-1/frontend" && npm install && npm run build && npm run test && echo "All tests passed successfully!"',
        "description": "This is a very long description that should definitely be wrapped to multiple lines because it exceeds the maximum line width that we have configured for the text formatter utility module"
    }

    print(json.dumps(tool_input, indent=2))

    print("\n" + "=" * 60)
    print("LONG TEXT WRAPPING - After (wrapped to 100 chars):")
    print("=" * 60)

    formatted = format_tool_input("Bash", tool_input)
    print(formatted)
    # Show line lengths
    print("\nLine lengths:")
    for i, line in enumerate(formatted.split('\n'), 1):
        print(f"  Line {i}: {len(line)} chars")
    print()


def test_grep_tool():
    """Test formatting Grep tool."""
    print("=" * 60)
    print("GREP TOOL - Before (JSON):")
    print("=" * 60)

    tool_input = {
        "pattern": "test.*setup",
        "path": "./tests",
        "output_mode": "files_with_matches",
        "-i": True
    }

    print(json.dumps(tool_input, indent=2))

    print("\n" + "=" * 60)
    print("GREP TOOL - After (Readable Text):")
    print("=" * 60)

    formatted = format_tool_input("Grep", tool_input)
    print(formatted)
    print()


def test_task_tool():
    """Test formatting Task tool."""
    print("=" * 60)
    print("TASK TOOL - Before (JSON):")
    print("=" * 60)

    tool_input = {
        "subagent_type": "worker-1",
        "description": "Implement user authentication system",
        "prompt": "You need to implement JWT-based authentication..."
    }

    print(json.dumps(tool_input, indent=2))

    print("\n" + "=" * 60)
    print("TASK TOOL - After (Readable Text):")
    print("=" * 60)

    formatted = format_tool_input("Task", tool_input)
    print(formatted)
    print()


def test_tool_result():
    """Test formatting tool results."""
    print("=" * 60)
    print("TOOL RESULT - Before (JSON):")
    print("=" * 60)

    result = {
        "status": "success",
        "files_created": ["tests/e2e/example.spec.ts", "tests/pages/home.ts"],
        "total_lines": 156,
        "warnings": []
    }

    print(json.dumps(result, indent=2))

    print("\n" + "=" * 60)
    print("TOOL RESULT - After (Readable Text):")
    print("=" * 60)

    formatted = format_tool_result(result)
    print(formatted)
    print()


def test_nested_json():
    """Test formatting nested JSON structures."""
    print("=" * 60)
    print("NESTED JSON - Before (JSON):")
    print("=" * 60)

    data = {
        "session_info": {
            "session_id": "session-20250117-140000",
            "model": "sonnet",
            "max_parallel": 3
        },
        "tasks": [
            {
                "id": "001",
                "description": "Create User model",
                "status": "pending"
            },
            {
                "id": "002",
                "description": "Add authentication",
                "status": "in_progress"
            }
        ],
        "active_workers": 2
    }

    print(json.dumps(data, indent=2))

    print("\n" + "=" * 60)
    print("NESTED JSON - After (Readable Text):")
    print("=" * 60)

    formatted = json_to_text(data)
    print(formatted)
    print()


if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print(" " * 10 + "JSON to Readable Text Formatter Demo")
    print("=" * 60)
    print()

    test_bash_tool()
    test_long_text_wrapping()
    test_grep_tool()
    test_task_tool()
    test_tool_result()
    test_nested_json()

    print("=" * 60)
    print("Demo complete! The formatter converts JSON to readable text.")
    print("=" * 60)
