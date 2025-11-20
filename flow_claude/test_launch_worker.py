"""Simple test script to verify hook system works."""
import time
import sys

def test_launch_worker(worker_id: str):
    """Test function that just sleeps for 5 seconds."""
    print(f"[Test-Worker-{worker_id}] Starting...")
    print(f"[Test-Worker-{worker_id}] Sleeping for 5 seconds...")
    time.sleep(40)
    print(f"[Test-Worker-{worker_id}] Completed!")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_launch_worker.py <worker_id>")
        sys.exit(1)

    worker_id = sys.argv[1]
    exit_code = test_launch_worker(worker_id)
    sys.exit(exit_code)
