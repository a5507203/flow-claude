"""
Test the new architecture with a simple request
"""
import asyncio
from flow_claude.cli import run_development_session

async def test_single_request():
    """Test processing a single request"""
    print("Testing single request processing...")

    # Create control queue with one request
    control_queue = asyncio.Queue()
    await control_queue.put({
        "type": "intervention",
        "data": {"requirement": "Say hello"}
    })

    # Run development session
    await run_development_session(
        initial_request="unused",  # Will be ignored, gets from queue
        session_id="test-session",
        model="sonnet",
        max_turns=10,
        permission_mode="bypassPermissions",
        enable_parallel=False,
        max_parallel=1,
        verbose=True,
        debug=True,
        orchestrator_prompt="@ORCHESTRATOR_INSTRUCTIONS.md",
        planner_prompt="@PLANNER_INSTRUCTIONS.md",
        worker_prompt="@WORKER_INSTRUCTIONS.md",
        user_proxy_prompt="@USER_PROXY_INSTRUCTIONS.md",
        num_workers=1,
        control_queue=control_queue,
        logger=None,
        auto_mode=False,
        resume_session_id=None
    )

    print("\n✓ First request completed!")

    # Test follow-up with resume
    from flow_claude import cli
    session_id = getattr(cli, '_current_session_id', None)
    print(f"Session ID: {session_id}")

    # Add follow-up request
    await control_queue.put({
        "type": "intervention",
        "data": {"requirement": "Now say goodbye"}
    })

    # Process follow-up with same session
    await run_development_session(
        initial_request="unused",
        session_id="test-session",
        model="sonnet",
        max_turns=10,
        permission_mode="bypassPermissions",
        enable_parallel=False,
        max_parallel=1,
        verbose=True,
        debug=True,
        orchestrator_prompt="@ORCHESTRATOR_INSTRUCTIONS.md",
        planner_prompt="@PLANNER_INSTRUCTIONS.md",
        worker_prompt="@WORKER_INSTRUCTIONS.md",
        user_proxy_prompt="@USER_PROXY_INSTRUCTIONS.md",
        num_workers=1,
        control_queue=control_queue,
        logger=None,
        auto_mode=False,
        resume_session_id=session_id  # Resume!
    )

    print("\n✓ Follow-up request completed with same session!")

if __name__ == "__main__":
    asyncio.run(test_single_request())
