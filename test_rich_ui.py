"""
Test script for Rich UI
"""

from flow_claude.cli_rich_ui import RichUI

def test_rich_ui():
    """Test Rich UI components"""

    # Create Rich UI instance
    ui = RichUI(verbose=True, debug=False)

    # Test banner
    print("Testing banner...")
    ui.show_banner()

    # Test session header
    print("\nTesting session header...")
    ui.show_session_header(
        session_id="session-20251111-120000",
        model="sonnet",
        num_workers=3,
        base_branch="flow"
    )

    # Test user message
    print("\nTesting user message...")
    ui.print_user_message("Create a new React component", is_followup=False)

    # Test agent messages
    print("\nTesting agent messages...")
    ui.print_agent_message("orchestrator", "Starting to process your request...")
    ui.print_agent_message("planner", "Creating execution plan with 3 tasks")
    ui.print_agent_message("worker", "Implementing task 001...")

    # Test tool usage
    print("\nTesting tool usage...")
    ui.print_tool_use("Read", {"file_path": "/path/to/file.py"}, "worker")
    ui.print_tool_result("Read", success=True, message="File read successfully")

    # Test messages
    print("\nTesting message types...")
    ui.print_success("Task completed successfully!")
    ui.print_error("An error occurred", "Error details here...")
    ui.print_warning("This is a warning message")
    ui.print_info("This is an informational message")

    # Test status
    print("\nTesting status update...")
    ui.update_status("Processing task 001: Create component")

    # Test input prompt
    print("\nTesting input prompts...")
    ui.show_input_prompt(is_initial=True)
    ui.show_input_prompt(is_initial=False)

    # Test separator
    print("\nTesting separator...")
    ui.show_separator()

    print("\n[OK] All Rich UI tests completed!")

if __name__ == "__main__":
    test_rich_ui()
