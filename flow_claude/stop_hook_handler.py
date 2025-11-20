"""Monitor launch_worker processes and wait for completion."""
import json
import sys
import psutil
import time
from pathlib import Path

def log_debug(step, data):
    """Log debug information to stderr and file."""
    debug_msg = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "step": step,
        "data": data
    }
    print(json.dumps(debug_msg), file=sys.stderr)

    # Also write to debug file
    debug_file = Path("debug_stop_hook.jsonl")
    # with open(debug_file, 'a') as f:
    #     f.write(json.dumps(debug_msg) + '\n')

# Step 1: Read input
try:
    input_data = json.load(sys.stdin)
    log_debug("input_received", {
        "has_data": True,
        "input_keys": list(input_data.keys()) if isinstance(input_data, dict) else None,
        "cwd": input_data.get("cwd") if isinstance(input_data, dict) else None
    })

    # Write input_data to file for debugging
    # with open('debug_input_data.json', 'w') as f:
    #     json.dump(input_data, f, indent=2)
except Exception as e:
    log_debug("input_error", {"error": str(e)})
    sys.exit(0)

# Step 1.5: Check if this is a worker calling stop hook on itself
hook_cwd = input_data.get("cwd", "") if isinstance(input_data, dict) else ""
is_worker_context = ".worktrees" in hook_cwd or "worker-" in hook_cwd

if is_worker_context:
    # This is a worker trying to stop - allow it immediately
    result = {
        "continue": True,
        "decision": "approve",
        "reason": "Worker context detected - allow worker to stop"
    }
    log_debug("worker_self_stop", {
        "cwd": hook_cwd,
        "decision": "approve"
    })
    print(json.dumps(result))
    sys.exit(0)

# Get all Python processes with 'launch_worker' in command line
def get_workers():
    """Get worker processes with detailed info."""
    workers = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'create_time', 'status', 'name']):
        try:
            cmdline = proc.info.get('cmdline', [])
            cmdline_str = ' '.join(cmdline) if cmdline else ''
            proc_name = proc.info.get('name', '').lower()

            # Only match Python processes (not bash/sh wrappers)
            is_python = 'python' in proc_name
            has_launch_worker = 'launch_worker' in cmdline_str

            if is_python and has_launch_worker:
                # Extract worker ID from cmdline
                worker_id = None
                for i, arg in enumerate(cmdline):
                    if arg == '--worker-id' and i + 1 < len(cmdline):
                        worker_id = cmdline[i + 1]
                        break

                workers.append({
                    'pid': proc.info['pid'],
                    'worker_id': worker_id,
                    'name': proc_name,
                    'cmdline': cmdline_str,
                    'status': proc.info.get('status'),
                    'create_time': proc.info.get('create_time')
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return workers

# Step 2: Get initial workers
initial_workers = get_workers()
initial_pids = {w['pid'] for w in initial_workers}
# Map PID to worker info
pid_to_worker = {w['pid']: w for w in initial_workers}

log_debug("initial_scan", {
    "worker_count": len(initial_workers),
    "pids": list(initial_pids),
    "workers": initial_workers
})

if not initial_pids:
    # No workers running, continue
    result = {"continue": True, "decision": "approve", "reason": "No workers running"}
    log_debug("no_workers", result)
    print(json.dumps(result))
    sys.exit(0)

# Step 3: Extract worker info with IDs
running_worker_info = []
for worker in initial_workers:
    # Extract worker ID from cmdline
    cmdline = worker['cmdline']
    worker_id = "unknown"
    if '--worker-id' in cmdline or '--worker-id=' in cmdline:
        # Try to extract worker ID
        parts = cmdline.split()
        for i, part in enumerate(parts):
            if part.startswith('--worker-id='):
                worker_id = part.split('=')[1].strip('"\'')
                break
            elif part == '--worker-id' and i + 1 < len(parts):
                worker_id = parts[i + 1].strip('"\'')
                break

    running_worker_info.append({
        'pid': worker['pid'],
        'worker_id': worker_id,
        'name': worker['name'],
        'status': worker['status']
    })

# Step 4: Build result - block because workers are still running
worker_ids = [w['worker_id'] for w in running_worker_info]
worker_id_str = ", ".join(worker_ids)

result = {
    "continue": True,
    "decision": "block",
    "reason": f"{len(initial_pids)} background worker(s) still running (Worker IDs: {worker_id_str}). Wait for background tasks to finish.",
    "details": {
        "running_workers": running_worker_info,
        "total_running": len(initial_pids),
        "action_needed": "sleep 5 mins and Wait for workers to complete their tasks"
    }
}

log_debug("workers_running_block", result)
print(json.dumps(result))
sys.exit(2)
