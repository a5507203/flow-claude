"""
Test that the footer appears after input, not before
"""

import time
from flow_claude.cli_rich_ui import RichUI

def test_footer_after_input():
    """Test that footer appears after input is received"""

    ui = RichUI(verbose=True, debug=False)

    print("Simulating user workflow:\n")

    # Step 1: User types input (footer not yet shown)
    print("1. User types: 'hi'")
    print("   > hi")
    time.sleep(1)

    # Step 2: Enable footer AFTER input (simulating what happens in CLI)
    print("\n2. Processing starts, footer appears:")
    ui.enable_fixed_footer("Press ESC to interrupt | Type for follow-up | \\q to quit")
    time.sleep(0.5)

    # Step 3: Show agent messages (footer stays at bottom)
    print("\n3. Agent messages scroll (footer stays at bottom):\n")
    ui.print_user_message("hi", is_followup=False)
    time.sleep(0.5)

    ui.print_agent_message("orchestrator", "Processing your request...")
    time.sleep(0.5)

    ui.print_agent_message("planner", "Creating execution plan...")
    time.sleep(0.5)

    ui.print_agent_message("planner", "Created plan with 3 tasks")
    time.sleep(0.5)

    ui.print_agent_message("worker", "Executing task 001...")
    time.sleep(0.5)

    ui.print_success("Task 001 completed")
    time.sleep(0.5)

    ui.print_agent_message("worker", "Executing task 002...")
    time.sleep(0.5)

    # Step 4: Disable footer
    ui.disable_fixed_footer()

    print("\n[OK] Test complete!")
    print("\nExpected behavior:")
    print("- Footer NOT shown before input")
    print("- Footer appears AFTER input is received")
    print("- Footer stays at bottom while messages scroll")

if __name__ == "__main__":
    test_footer_after_input()
