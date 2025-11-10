"""
Test script for fixed footer functionality
"""

import time
from flow_claude.cli_rich_ui import RichUI

def test_fixed_footer():
    """Test fixed footer that stays at the bottom"""

    ui = RichUI(verbose=True, debug=False)

    print("Testing fixed footer - the prompt should stay at the bottom\n")

    # Enable fixed footer
    ui.enable_fixed_footer("Press ESC to interrupt | Type for follow-up | \\q to quit")

    # Simulate multiple messages being printed
    for i in range(10):
        time.sleep(0.5)
        ui.print_agent_message("orchestrator", f"Processing step {i+1}...")

        if i == 3:
            ui.print_success("Checkpoint 1 reached")

        if i == 6:
            ui.print_warning("Checkpoint 2 - halfway there")

    # Print highlighted message
    ui.print_agent_message("planner", "Creating plan with 5 tasks across 3 waves")
    time.sleep(0.5)

    # Print more messages
    ui.print_info("All tasks created successfully")
    time.sleep(0.5)

    ui.print_success("Process complete!")
    time.sleep(0.5)

    # Disable footer
    ui.disable_fixed_footer()

    print("\n[OK] Fixed footer test complete!")
    print("The 'Press ESC to interrupt' line should have stayed at the bottom throughout")

if __name__ == "__main__":
    test_fixed_footer()
