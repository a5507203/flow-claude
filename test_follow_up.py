"""Test script to verify follow-up functionality in Flow-Claude.

This script will help verify if the interactive follow-up prompt works correctly.
"""

import subprocess
import sys

def test_follow_up():
    """Test the follow-up functionality by simulating user input."""

    print("=" * 60)
    print("TEST: Follow-Up Functionality")
    print("=" * 60)
    print()
    print("This test will verify if the follow-up prompt works correctly.")
    print("We'll use a simple request that should complete quickly.")
    print()
    print("Expected behavior:")
    print("1. Session should complete")
    print("2. Should show 'SUCCESS: Development session complete!'")
    print("3. Should show 'INTERACTIVE MODE: Enter a follow-up request...'")
    print("4. We'll enter 'q' to quit")
    print()
    print("-" * 60)
    print()

    # Create a simple test request
    # Use echo command which should complete quickly
    test_request = "create a file called test_hello.txt with the text 'hello world'"

    print(f"Test Request: {test_request}")
    print()
    print("Starting Flow-Claude...")
    print("(This may take a moment as it initializes the agent system)")
    print()

    try:
        # Run flow-claude with the test request
        # We'll use --max-turns 5 to limit the session
        result = subprocess.run(
            [
                sys.executable, '-m', 'flow_claude.cli',
                'develop',
                test_request,
                '--max-turns', '5',
                '--model', 'haiku',  # Use haiku for faster/cheaper testing
            ],
            capture_output=False,  # Let output go to terminal so we can see it
            text=True,
            timeout=120  # 2 minute timeout
        )

        print()
        print("-" * 60)
        print(f"Process exit code: {result.returncode}")

        if result.returncode == 0:
            print("✓ Process completed successfully")
        else:
            print("✗ Process exited with error")

    except subprocess.TimeoutExpired:
        print()
        print("✗ TEST TIMEOUT: Process took too long (> 2 minutes)")
        print("This might indicate the session didn't complete properly")
    except KeyboardInterrupt:
        print()
        print("✗ TEST INTERRUPTED: User cancelled test")
    except Exception as e:
        print()
        print(f"✗ TEST ERROR: {e}")

if __name__ == '__main__':
    test_follow_up()
