#!/usr/bin/env python3
"""Stop a running worker."""
import argparse
import asyncio
import json
import sys


async def stop_worker(worker_id: str) -> dict:
    """Stop a running worker.

    Args:
        worker_id: Worker ID to stop

    Returns:
        Dict with success status
    """
    try:
        # Placeholder - would send stop signal to worker
        return {
            "success": True,
            "worker_id": worker_id,
            "message": f"Worker-{worker_id} stop signal sent (placeholder)"
        }

    except Exception as e:
        return {
            "error": f"Failed to stop worker: {str(e)}",
            "success": False
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Stop worker')
    parser.add_argument('--worker-id', required=True)

    args = parser.parse_args()

    result = asyncio.run(stop_worker(args.worker_id))
    print(json.dumps(result, indent=2))

    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
