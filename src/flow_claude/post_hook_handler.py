"""Monitor launch_worker processes and wait for completion."""
import json
import sys
import psutil
import time
import os

try:
    input_data = json.load(sys.stdin)
    # Debug: write input_data to file
    with open('post_input_data.json', 'w') as f:
        json.dump(input_data, f, indent=2)
except Exception:
    sys.exit(0)

# Extract cwd and command from input_data
target_cwd = input_data.get('cwd', '')
tool_input = input_data.get('tool_input', {})
target_command = tool_input.get('command', '')

# Normalize paths for comparison (handle different path separators)
def normalize_path(path):
    return os.path.normpath(path).lower() if path else ''

target_cwd_normalized = normalize_path(target_cwd)

# Extract worker ID from command line
def extract_worker_id(cmdline):
    """Extract worker ID from command line (last argument)"""
    # cmdline is a list from psutil
    if isinstance(cmdline, list) and len(cmdline) > 0:
        # Last element should be the worker ID
        return cmdline[-1]
    elif isinstance(cmdline, str):
        parts = cmdline.split()
        if parts:
            return parts[-1]
    return "unknown"

# Get all Python processes matching the cwd and command
def get_workers(cwd, command):
    workers = {}
    for proc in psutil.process_iter(['pid', 'cmdline', 'cwd']):
        try:
            proc_cwd = normalize_path(proc.info.get('cwd', ''))
            cmdline = proc.info.get('cmdline', [])
            cmdline_str = ' '.join(cmdline) if cmdline else ''

            # Match processes with the same cwd and command pattern
            if proc_cwd == cwd and command in cmdline_str:
                worker_id = extract_worker_id(cmdline)
                workers[proc.info['pid']] = worker_id
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return workers

# Get initial workers
initial = get_workers(target_cwd_normalized, target_command)

if not initial:
    # No workers running, continue
    print(json.dumps({"continue": True, "decision": "approve"}))
    sys.exit(0)

# Wait for at least one to complete
while True:
    current = get_workers(target_cwd_normalized, target_command)
    completed_pids = set(initial.keys()) - set(current.keys())
    if completed_pids:
        break
    time.sleep(0.5)

# Build detailed reason message
completed_count = len(completed_pids)
still_running = len(current)

# Build worker details for completed workers
completed_workers = []
for pid in sorted(completed_pids):
    worker_id = initial.get(pid, "unknown")
    completed_workers.append(f"{worker_id} (PID {pid})")

reason_parts = [f"{completed_count} worker(s) completed: {', '.join(completed_workers)}"]

# Add info about remaining workers
if still_running > 0:
    reason_parts.append(f"{still_running} still running")

reason = " | ".join(reason_parts)

# Report completion
print(json.dumps({
    "continue": True,
    "decision": "block",
    "reason": reason
}))
sys.exit(2)
