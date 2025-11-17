"""Flow-Claude CLI - Git-driven autonomous development system.

This module provides the command-line interface for Flow-Claude,
which uses Claude agent SDK to orchestrate autonomous development
with git as the single source of truth.
"""

import asyncio
import os
import sys
from typing import Optional
from datetime import datetime

import click

# Global logging flags
_verbose_logging = False
_debug_logging = False
_session_logger = None  # Optional logger for file logging

# Track subagent identification (tool_use_id -> agent_name)
_tool_id_to_agent = {}

# SDK session ID for resume capability
_current_session_id = None

# Hook for Textual UI integration (ui package)
_message_handler = None


def safe_echo(text: str, nl: bool = True, **kwargs):
    """Safely print text handling Unicode/emoji on Windows.

    Windows console uses cp1252 by default which can't handle emojis.
    This function handles encoding errors gracefully.
    """
    try:
        # Try normal echo first
        click.echo(text, nl=nl, **kwargs)
    except UnicodeEncodeError:
        # Fallback: encode with error handling
        # Replace problematic chars with '?'
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        click.echo(safe_text, nl=nl, **kwargs)


def setup_instruction_files(debug: bool = False) -> list:
    """Setup instruction files in .flow-claude/ directory.

    This function:
    1. Creates .flow-claude/ directory if needed
    2. Copies default instruction files if they don't exist
    3. Commits them to flow branch if on flow and files are new

    Returns:
        list: List of created file paths

    This should be called after flow branch is created/checked out.
    """
    import shutil
    import subprocess
    from pathlib import Path

    working_dir = os.getcwd()
    prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

    # Create .flow-claude directory
    flow_claude_dir = os.path.join(working_dir, '.flow-claude')
    os.makedirs(flow_claude_dir, exist_ok=True)

    created_files = []

    # Instruction files to copy (V7: no planner, merged into orchestrator)
    instruction_files = [
        ('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md'),
        ('WORKER_INSTRUCTIONS.md', 'worker.md'),
        ('USER_PROXY_INSTRUCTIONS.md', 'user.md'),
    ]

    for local_name, fallback_name in instruction_files:
        local_path = os.path.join(flow_claude_dir, local_name)
        default_path = os.path.join(prompts_dir, fallback_name)

        # Copy if doesn't exist
        if not os.path.exists(local_path):
            try:
                shutil.copy2(default_path, local_path)
                created_files.append(f".flow-claude/{local_name}")
                if debug:
                    click.echo(f"DEBUG: Copied {fallback_name} -> .flow-claude/{local_name}")
            except Exception as e:
                if debug:
                    click.echo(f"DEBUG: Failed to copy {fallback_name}: {e}")

    # Auto-commit if files were created and we're on flow branch
    if created_files:
        try:
            # Check if git repo exists
            if not Path('.git').exists():
                if debug:
                    click.echo("DEBUG: No git repository - skipping auto-commit")
                return created_files

            # Check current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                timeout=5
            )
            current_branch = result.stdout.strip()

            if current_branch != 'flow':
                if debug:
                    click.echo(f"DEBUG: Not on flow branch ({current_branch}) - skipping auto-commit")
                return created_files

            # Stage files
            subprocess.run(
                ['git', 'add'] + created_files,
                check=True,
                timeout=10
            )

            # Commit
            commit_message = "Initialize Flow-Claude instruction files\n\nAdded agent instruction files for Flow-Claude v6.7\n\n🤖 Auto-committed by Flow-Claude"
            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                check=True,
                capture_output=True,
                timeout=10
            )

            if debug:
                click.echo(f"DEBUG: ✓ Committed instruction files to flow branch")

        except Exception as e:
            if debug:
                click.echo(f"DEBUG: Could not auto-commit instruction files: {e}")

    return created_files

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition
except ImportError:
    print("ERROR: claude-agent-sdk is not installed.", file=sys.stderr)
    print("Install it with: pip install claude-agent-sdk", file=sys.stderr)
    print("\nNote: You also need Claude Code CLI installed:", file=sys.stderr)
    print("  npm install -g @anthropic-ai/claude-code", file=sys.stderr)
    sys.exit(1)


from .git_tools import create_git_tools_server
from .sdk_workers import create_worker_tools_server
from .utils.text_formatter import format_tool_input, format_tool_result


def check_claude_code_available() -> tuple[bool, str]:
    """Check if Claude Code CLI is installed and available.

    Returns:
        Tuple of (is_available, message)
    """
    import subprocess
    import platform

    # On Windows, try claude.cmd; on Unix, try claude
    commands_to_try = []
    if platform.system() == 'Windows':
        commands_to_try = ['claude.cmd', 'claude']
    else:
        commands_to_try = ['claude']

    # Try each command variant
    for cmd in commands_to_try:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True if platform.system() == 'Windows' else False
            )

            if result.returncode == 0:
                return True, f"Claude Code CLI found: {result.stdout.strip()}"

        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            return False, "Claude Code CLI check timed out"
        except Exception:
            continue

    # If we get here, no command worked
    return False, ("Claude Code CLI not found. Install it with:\n"
                  "  npm install -g @anthropic-ai/claude-code")


async def run_development_session(
    initial_request: str,
    session_id: str,
    model: str,
    max_turns: int,
    permission_mode: str,
    enable_parallel: bool,
    max_parallel: int,
    verbose: bool,
    debug: bool,
    num_workers: int,
    control_queue: Optional[asyncio.Queue] = None,
    logger: Optional[object] = None,  # FlowClaudeLogger instance
    auto_mode: bool = True,  # Enable user agent for autonomous decisions
    resume_session_id: Optional[str] = None  # Resume from previous session
) -> bool:
    """Run persistent development session handling all follow-ups internally.

    This function runs a continuous session that processes the initial request
    and all subsequent follow-up requests from control_queue. It only returns
    when the user explicitly quits via /quit command.

    Args:
        initial_request: User's initial development request
        session_id: Session ID for logging (persistent across requests)
        model: Claude model to use (sonnet/opus/haiku)
        max_turns: Maximum conversation turns per request
        permission_mode: Permission mode for tools
        enable_parallel: Enable parallel task execution
        max_parallel: Maximum number of parallel workers
        verbose: Enable verbose logging
        debug: Enable debug mode
        num_workers: Number of worker agents to create
        control_queue: Queue for receiving follow-up requests
        logger: Logger instance for session logging
        auto_mode: Enable autonomous mode with user proxy agent
        resume_session_id: Resume from previous session ID

    Returns:
        True if user requested quit, False if session ended naturally

    Note:
        All prompts use @filepath syntax.
        The SDK loads the full file content at runtime.
        V7 merges planner into orchestrator for simplified architecture.
    """
    # Store logging flags and logger globally for use in handle_agent_message
    global _verbose_logging, _debug_logging, _session_logger, _tool_id_to_agent
    _verbose_logging = verbose
    _debug_logging = debug
    _session_logger = logger
    _tool_id_to_agent = {}  # Clear agent tracking for new session

    # Note: SDKWorkerManager is initialized in ui/orchestrator.py before calling this function
    # The singleton pattern ensures the same instance (with proper worker_log) is used throughout
    # Initializing again here would overwrite the UI log function with click.echo, breaking output

    # Print banner
    click.echo("=" * 60)
    click.echo("Flow-Claude V7 Development Session Starting...")
    click.echo("=" * 60)
    click.echo(f"\nInitial Request: {initial_request}")
    click.echo(f"Session ID: {session_id}")
    click.echo(f"Model: {model}")
    click.echo(f"Architecture: V7 (Unified Orchestrator + Workers)")
    click.echo(f"Working Directory: {os.getcwd()}")
    click.echo(f"Execution Mode: {'Parallel' if enable_parallel else 'Sequential'}")
    if enable_parallel:
        click.echo(f"Max Parallel Workers: {max_parallel}")

    # Show logging modes
    logging_modes = []
    if verbose:
        logging_modes.append("Verbose")
    if debug:
        logging_modes.append("Debug")
    if logging_modes:
        click.echo(f"Logging: {', '.join(logging_modes)}")

    click.echo()

    # Use passed session_id instead of generating new one
    plan_branch = f"plan/{session_id}"

    if debug:
        safe_echo(f"DEBUG: Using session ID: {session_id}")
        safe_echo(f"DEBUG: Plan branch: {plan_branch}")

    # Set git config for current plan branch (required for mcp__git__read_plan_file tool)
    import subprocess
    import platform
    import shutil

    try:
        # Set the current plan branch name that MCP tool will use
        subprocess.run(
            ["git", "config", "--local", "flow-claude.current-plan", plan_branch],
            capture_output=True,
            check=True
        )
        if debug:
            safe_echo(f"DEBUG: Set git config flow-claude.current-plan='{plan_branch}'")
    except subprocess.CalledProcessError as e:
        if debug:
            safe_echo(f"DEBUG: Warning: Could not set git config: {e}")

    # Find Claude CLI path

    claude_path = None
    if platform.system() == 'Windows':
        # Try shutil.which first (Python's cross-platform way)
        claude_path = shutil.which('claude.cmd') or shutil.which('claude')

        # If not found, try common Windows locations
        if not claude_path:
            common_locations = [
                os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude.cmd'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming', 'npm', 'claude.cmd'),
                'C:\\Program Files\\nodejs\\claude.cmd',
                os.path.join(os.environ.get('ProgramFiles', ''), 'nodejs', 'claude.cmd'),
            ]

            for location in common_locations:
                if location and os.path.exists(location):
                    claude_path = location
                    break

        # If still not found, try npm config
        if not claude_path:
            try:
                npm_prefix = subprocess.run(
                    'npm config get prefix',
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=5
                ).stdout.strip()
                if npm_prefix:
                    potential_path = os.path.join(npm_prefix, 'claude.cmd')
                    if os.path.exists(potential_path):
                        claude_path = potential_path
            except Exception:
                pass
    else:
        # On Unix, use shutil.which
        claude_path = shutil.which('claude')

    # Show Claude CLI path in debug mode
    if debug:
        if claude_path:
            click.echo(f"DEBUG: Found Claude CLI at: {claude_path}")
        else:
            click.echo("DEBUG: Claude CLI path not found, SDK will use default detection")

    # V7: Simplified architecture - orchestrator plans and coordinates, workers execute
    # Orchestrator (orchestrator.md) creates plans and spawns workers
    # User Proxy (user.md) handles user confirmations (auto-mode only)
    # Workers (worker.md) execute individual tasks in parallel
    # SDK v0.1.6+ automatically handles Windows cmd.exe 8191-char limit via temp files (PR #245)
    agent_definitions = {}

    # V7: Planner merged into orchestrator - no separate planner agent needed

    # Define user subagent (V6.6: New - handles user confirmations)
    # Only register if auto_mode is enabled
    if auto_mode:
        agent_definitions['user'] = AgentDefinition(
            description='User agent that represents the user for confirmation dialogs',
            prompt='''You help user to make decision

## Core Responsibilities

When invoked, you analyze proposals, plans, and options, then make decisions based on software engineering best practices. You provide clear technical justification and return decisions immediately without waiting for human input.

## Decision-Making Framework

### Plan Review Criteria
When evaluating implementation plans, assess:
1. **Completeness**: Does it cover all stated requirements?
2. **Feasibility**: Are time estimates and task breakdowns realistic?
3. **Technology Appropriateness**: Are chosen technologies suitable for the use case?
4. **Architecture Soundness**: Is the proposed structure logical and maintainable?

### Technology/Design Decision Criteria
When choosing between options, prioritize:
1. **Requirements Fit**: Which option best serves the stated needs?
2. **Simplicity**: When equivalent, prefer simpler over complex solutions
3. **Standard Practice**: Favor widely-adopted patterns and technologies
4. **Maintainability**: Choose options that are easier to understand and modify


## Operational Principles

### DO:
- Carefully read and understand all context before deciding
- Apply established software engineering best practices
- Choose simplicity for straightforward requirements
- Provide specific, actionable technical reasoning
- Make decisions quickly and confidently
- Trust your technical judgment

## Your Mission

You are a proxy for an experienced software engineer making real-time technical decisions. The orchestrator and other agents trust you to catch flawed plans, make smart architectural choices, resolve ambiguities sensibly, and keep projects moving efficiently.

Every decision you make should reflect what a skilled engineer would choose when reviewing proposals during active development. Be thoughtful, be decisive, and always explain your technical reasoning clearly.

**Trust your judgment. Analyze. Decide. Justify. Execute.**
''',
            tools=[
                'Bash', 'Read', 'Edit', 'Grep', 'Glob',
                'mcp__git__parse_task',  # Read task metadata from branch
                'mcp__git__parse_plan',  # Read plan context
                'mcp__git__parse_worker_commit',  # Read own progress (commit-only architecture)
                'mcp__git__get_provides'  # Query available capabilities from completed tasks
            ],  # User proxy doesn't need tools - just facilitates user interaction
            model=model  # Use haiku for fast, cheap confirmation dialogs
        )


    if debug:
        user_count = 1 if auto_mode else 0
        click.echo(f"DEBUG: Created {len(agent_definitions)} agent definitions ({user_count} user proxy + {num_workers} workers):")
        for agent_name, agent_def in agent_definitions.items():
            click.echo(f"DEBUG:   - {agent_name}: {agent_def.description}")
            click.echo(f"DEBUG:     tools: {agent_def.tools}")
            click.echo(f"DEBUG:     model: {agent_def.model}")
            click.echo(f"DEBUG:     prompt length: {len(agent_def.prompt)} chars")
        click.echo()


    orchestrator_prompt = {
        "type": "preset",
        "preset": "claude_code",
    }

    # Configure agent options with programmatic agents
    options_kwargs = {
        "system_prompt": orchestrator_prompt,  # Main orchestrator system prompt (@filepath syntax)
        "agents": agent_definitions,  # V7: Worker subagent definitions (planner merged into orchestrator)
        "allowed_tools": [
            # Standard tools
            "Bash",
            "Read",
            "Write",
            "Edit",
            "Grep",
            "Glob",
            # MCP git tools (commit-only architecture)
            "mcp__git__parse_task",  # Parse task metadata from branch commits
            "mcp__git__parse_plan",  # Parse plan from plan branch commits
            "mcp__git__get_provides",  # Query completed task capabilities
            "mcp__git__parse_worker_commit",  # Parse worker progress from commits
            # V7: Orchestrator now creates branches directly (planner merged in)
            "mcp__git__create_plan_branch",  # Create plan branch with all tasks
            "mcp__git__create_task_branch",  # Create task branch with metadata
            "mcp__git__update_plan_branch",  # Update plan after each task completion
            "mcp__git__create_worktree",  # Create isolated worktree for worker
            "mcp__git__remove_worktree",  # Clean up worktree after task completes
            # Async worker management (NEW)
            "mcp__workers__launch_worker_async",  # Launch worker in background (non-blocking)
            "mcp__workers__get_worker_status",  # Check status of background workers
        ],
        "mcp_servers": {
            "git": create_git_tools_server(),
            "workers": create_worker_tools_server(),
            "playwright": {
                "type": "stdio",
                "command": "cmd",
                "args": [
                "/c",
                "npx",
            "@playwright/mcp@latest"
            ],
      "env": {}
    }
        },
        "permission_mode": permission_mode,
        "max_turns": max_turns,
        "cwd": os.getcwd(),
        "cli_path": claude_path,
        "setting_sources":["user", "project", "local"]  # Explicitly set Claude CLI path
    }

    # Add resume parameter if provided (session resumption)
    if resume_session_id:
        options_kwargs["resume"] = resume_session_id
        if debug:
            click.echo(f"DEBUG: Resuming session: {resume_session_id}")

    options = ClaudeAgentOptions(**options_kwargs)

    if debug:
        click.echo(f"DEBUG: ClaudeAgentOptions created")
        click.echo(f"DEBUG: system_prompt: {orchestrator_prompt}")
        if options.agents:
            click.echo(f"DEBUG: Agent names in options: {list(options.agents.keys())}")
        else:
            click.echo(f"DEBUG: WARNING: options.agents is None or empty!")
        click.echo()

    # V6.3: Create session configuration for orchestrator
    # The orchestrator-minimal.md system prompt is loaded via @filepath in ClaudeAgentOptions
    # This initial query provides session-specific configuration
    parallel_config = ""
    if enable_parallel:
        parallel_config = f"""
**Parallel Execution:** ENABLED
- Max parallel workers: {max_parallel}
- Workers available: {', '.join([f'worker-{i}' for i in range(1, num_workers + 1)])}
- Execute tasks immediately when dependencies are met
- Process each task completion immediately
- Respect max parallel limit
"""
    else:
        parallel_config = f"""
**Parallel Execution:** DISABLED
- Worker available: worker-1
- Execute tasks sequentially (one at a time)
"""

    # Helper function to create query prompt for a request
    def create_query_prompt(user_request: str) -> str:
        user_agent_guide = ""
        if auto_mode:
            user_agent_guide = """


**IMPORTANT: DO NOT ask questions directly - always invoke user subagent. **
"""

        return f"""# Development Session Configuration 

**User Request:** {user_request}

**Session Info:**
- Session ID: {session_id}
- Plan Branch: {plan_branch}
- Working Directory: {os.getcwd()}
- Max Workers: {max_parallel}

**Instructions:** See .flow-claude/ORCHESTRATOR_INSTRUCTIONS.md for your full workflow.

{parallel_config}

**Available Subagents:**
{f'- **user** - Get confirmations/decisions (call with Task tool){chr(10)}' if auto_mode else ''}{chr(10).join([f'- **worker-{i}** - Execute tasks' for i in range(1, num_workers + 1)])}
{user_agent_guide}
---

**Quick Start:**
1. Analyze request → plan tasks
{f'2. Call user agent for confirmation{chr(10)}3. ' if auto_mode else '2. '}Use MCP tools: create plan/task branches
{f'4.' if auto_mode else '3.'} Create worktrees, spawn workers with `mcp__workers__launch_worker_async`
{f'5.' if auto_mode else '4.'} **STOP** - Your job is complete after launching workers. User will notify you when workers finish.
{f'6.' if auto_mode else '5.'} When notified of worker completion: process completion, update plan, launch next tasks
{f'7.' if auto_mode else '6.'} Report when all tasks done

Begin. **Remember: Complete immediately after launching all initial workers.**"""

    # Persistent session - processes ALL requests in a continuous loop
    # Only exits when user sends shutdown signal
    try:
        if not control_queue:
            click.echo("ERROR: control_queue is required", err=True)
            return

        # Create SDK client ONCE - session persists across all requests
        options = ClaudeAgentOptions(**options_kwargs)

        if debug:
            click.echo(f"DEBUG: Creating persistent ClaudeSDKClient session...")

        async with ClaudeSDKClient(options=options) as client:
            if debug:
                click.echo(f"DEBUG: SDK client session started")

            # Continuous loop - processes requests until shutdown
            while True:
                if debug:
                    click.echo(f"\nDEBUG: Waiting for next request from control_queue...")

                # Wait for next request (blocks here)
                control = await control_queue.get()

                # Handle shutdown
                if control.get("type") == "shutdown":
                    click.echo("\n[SHUTDOWN] User requested exit\n")
                    break

                # Handle worker completion events from async workers
                if control.get("type") == "worker_completion":
                    worker_data = control.get("data", {})
                    worker_id = worker_data.get("worker_id")
                    task_branch = worker_data.get("task_branch")
                    exit_code = worker_data.get("exit_code")
                    elapsed_time = worker_data.get("elapsed_time", 0)
                    error_message = worker_data.get("error_message")  # May be None

                    # Format elapsed time
                    elapsed_min = int(elapsed_time / 60)
                    elapsed_sec = int(elapsed_time % 60)

                    # Log the completion event to console
                    click.echo("\n" + "=" * 60)
                    click.echo(f"[WORKER COMPLETION EVENT]")
                    click.echo(f"  Worker ID: {worker_id}")
                    click.echo(f"  Task: {task_branch}")
                    click.echo(f"  Exit code: {exit_code} {'(success)' if exit_code == 0 else '(failed)'}")
                    click.echo(f"  Duration: {elapsed_min}m {elapsed_sec}s")
                    if error_message:
                        click.echo(f"  Error: {error_message}")
                    click.echo("=" * 60 + "\n")

                    # Also log to file for tracking
                    if logger:
                        logger.info(f"[WORKER COMPLETION] Worker-{worker_id} completed {task_branch}")
                        logger.info(f"  Exit code: {exit_code} {'(success)' if exit_code == 0 else '(failed)'}, Duration: {elapsed_min}m {elapsed_sec}s")
                        if error_message:
                            logger.error(f"  Error: {error_message}")

                    if debug:
                        click.echo(f"DEBUG: Worker completion event details:")
                        click.echo(f"DEBUG:   Worker-{worker_id}")
                        click.echo(f"DEBUG:   Branch: {task_branch}")
                        click.echo(f"DEBUG:   Exit code: {exit_code}")
                        click.echo(f"DEBUG:   Elapsed: {elapsed_time:.2f}s")
                        click.echo(f"DEBUG: Injecting completion notification to orchestrator\n")
                        if logger:
                            logger.debug(f"Worker-{worker_id} completion: branch={task_branch}, exit={exit_code}, elapsed={elapsed_time:.2f}s")

                    # Create notification message for orchestrator
                    if exit_code == 0:
                        # Success case - normal completion flow
                        completion_msg = f"""Worker-{worker_id} has completed task {task_branch}
- Exit code: {exit_code} (success)
- Elapsed time: {elapsed_min}m {elapsed_sec}s

Please process this single completion immediately (don't wait for other workers):
1. Parse worker commit status: mcp__git__parse_worker_commit("{task_branch}")
2. Verify implementation by reading actual code from flow branch (merged code)
3. Remove worktree: mcp__git__remove_worktree("{worker_id}")
4. Update plan to mark this task complete: mcp__git__update_plan_branch()
5. Check for newly-ready tasks: mcp__git__get_provides()
6. If worker-{worker_id} is now idle and another task is ready, launch it immediately
7. Continue working while other workers complete their tasks independently"""
                    else:
                        # Error case - include error details and suggest retry/alternative
                        error_details = f"\n- Error: {error_message}" if error_message else ""
                        completion_msg = f"""Worker-{worker_id} FAILED task {task_branch}
- Exit code: {exit_code} (error)
- Elapsed time: {elapsed_min}m {elapsed_sec}s{error_details}

The worker encountered an error and could not complete the task. Please:
1. Read the error message above to understand what went wrong
2. Remove the failed worktree: mcp__git__remove_worktree("{worker_id}")
3. Decide on next steps:
   - If validation error (e.g., missing branch, bad parameters): Fix the issue and retry
   - If initialization error (e.g., git/MCP setup): Check worktree setup, then retry
   - If runtime error: Review task complexity, consider breaking into smaller tasks
   - If repeated failures: Try alternative approach or skip for now
4. Update plan if needed: mcp__git__update_plan_branch()
5. If retrying or launching alternative task, use worker-{worker_id} (now idle)
6. Continue with other workers' tasks independently"""

                    # Process as a regular query
                    await client.query(completion_msg)

                    # Process the response
                    async for msg in client.receive_response():
                        handle_agent_message(msg)

                        # Check for interruptions during response
                        if control_queue and not control_queue.empty():
                            try:
                                peek_control = control_queue.get_nowait()

                                if peek_control.get("type") == "stop":
                                    click.echo("\n[STOP] Interrupting worker completion handling...\n")
                                    await client.interrupt()
                                    break
                                else:
                                    # Put back for next iteration
                                    await control_queue.put(peek_control)
                            except asyncio.QueueEmpty:
                                pass

                    click.echo("\n" + "=" * 60)
                    click.echo("Worker completion processed. Waiting for next event...")
                    click.echo("=" * 60)
                    continue

                # Handle intervention (normal request)
                elif control.get("type") == "intervention":
                    user_request = control.get("data", {}).get("requirement", "")
                    if not user_request:
                        click.echo("WARNING: Empty request received", err=True)
                        continue

                    click.echo(f"\n[REQUEST] Processing: {user_request}\n")
                    if debug:
                        click.echo(f"DEBUG: Sending query to SDK...")

                    # Send query
                    prompt = create_query_prompt(user_request)
                    await client.query(prompt)

                    # Process response with interruption support
                    interrupted = False
                    async for msg in client.receive_response():
                        handle_agent_message(msg)

                        # Check for interruptions during response processing
                        if control_queue and not control_queue.empty():
                            try:
                                peek_control = control_queue.get_nowait()

                                if peek_control.get("type") == "stop":
                                    # User requested stop - interrupt current task
                                    click.echo("\n[STOP] Interrupting current task...\n")
                                    await client.interrupt()
                                    interrupted = True
                                

                                elif peek_control.get("type") == "intervention":
                                    # Follow-up request - put back in queue for next iteration
                                    await control_queue.put(peek_control)
                                    if debug:
                                        click.echo(f"DEBUG: Follow-up request queued")

                                elif peek_control.get("type") == "shutdown":
                                    # Shutdown request - put back and break
                                    await control_queue.put(peek_control)
                                    break

                            except asyncio.QueueEmpty:
                                pass

                    if interrupted:
                        click.echo("[STOP] Task interrupted. Waiting for next request...")
                    else:
                        click.echo("\n" + "=" * 60)
                        click.echo("Request complete. Waiting for next request...")
                        click.echo("=" * 60)

                    # Loop back to wait for next request (same SDK session!)
                    continue

                # Unknown control type
                else:
                    click.echo(f"WARNING: Unknown control type: {control.get('type')}", err=True)
                    continue

            # Session ended
            click.echo("\nSDK session ended")

    except Exception as e:
        click.echo(f"\nERROR: Error during development session: {e}", err=True)
        raise


def handle_agent_message(msg):
    """Handle and display agent messages with enhanced logging.

    Uses unified message formatter from flow_claude.utils.message_formatter
    for consistent formatting across orchestrator and worker messages.

    Args:
        msg: Message object from SDK (SystemMessage, AssistantMessage, etc.) or dict

    Message types:
        - SystemMessage: System messages
        - AssistantMessage: Agent text output (contains TextBlock and ToolUseBlock)
        - ResultMessage: Tool results
        - UserMessage: User input
        - dict with "type": Legacy format
    """
    global _verbose_logging, _debug_logging, _session_logger, _tool_id_to_agent, _current_session_id, _message_handler

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Handle SDK message objects
    from claude_agent_sdk import SystemMessage, AssistantMessage, ResultMessage, UserMessage

    # Determine agent name from parent_tool_use_id
    agent_name = "orchestrator"  # Default to orchestrator
    if isinstance(msg, AssistantMessage):
        parent_id = getattr(msg, 'parent_tool_use_id', None)
        if parent_id:
            agent_name = _tool_id_to_agent.get(parent_id, f"agent-{parent_id[:8]}")

    if isinstance(msg, SystemMessage):
        # Capture session ID from init message
        if hasattr(msg, 'subtype') and msg.subtype == 'init':
            if hasattr(msg, 'session_id'):
                _current_session_id = msg.session_id
                if _debug_logging:
                    click.echo(f"[{timestamp}] [SESSION] Captured session ID: {_current_session_id}")

        # System message - show in debug mode
        if _debug_logging:
            click.echo(f"[{timestamp}] [SYSTEM] {msg.content if hasattr(msg, 'content') else str(msg)}")
            import sys
            sys.stdout.flush()
        return

    elif isinstance(msg, AssistantMessage):
        # Assistant message contains content blocks (TextBlock, ToolUseBlock)
        content = msg.content if hasattr(msg, 'content') else str(msg)

        # Content can be a string or a list of content blocks
        if isinstance(content, str):
            # Simple string content
            if content:
                if _debug_logging:
                    safe_echo(f"[{timestamp}] {content}")
                else:
                    safe_echo(content)
                import sys
                sys.stdout.flush()
        elif isinstance(content, list):
            # List of content blocks (TextBlock, ToolUseBlock, etc.)
            for block in content:
                block_type = type(block).__name__

                if block_type == 'TextBlock':
                    # Text output from agent
                    text = block.text if hasattr(block, 'text') else str(block)
                    if text:
                        # Log to file if logger available
                        if _session_logger:
                            _session_logger.info(f"[{agent_name.upper()}] {text}")

                        # Send to Textual UI if available, otherwise print to terminal
                        if _message_handler:
                            # Textual UI mode - delegate to message handler
                            _message_handler.write_message(
                                message=text,
                                agent=agent_name,
                                timestamp=timestamp if _debug_logging else None
                            )
                        else:
                            # Terminal mode - print with agent identification
                            if _debug_logging:
                                safe_echo(f"[{timestamp}] [{agent_name.upper()}] {text}")
                            else:
                                # Show agent name for subagents, hide for orchestrator to reduce noise
                                if agent_name != "orchestrator":
                                    safe_echo(f"[{agent_name.upper()}] {text}")
                                else:
                                    safe_echo(text)
                            import sys
                            sys.stdout.flush()

                elif block_type == 'ToolUseBlock':
                    # Tool call from agent
                    tool_name = block.name if hasattr(block, 'name') else 'unknown'
                    tool_id = block.id if hasattr(block, 'id') else ''
                    tool_input = block.input if hasattr(block, 'input') else {}

                    # Track Task tool invocations to identify subagents
                    if tool_name == 'Task' and tool_id:
                        subagent_type = tool_input.get('subagent_type', 'unknown')
                        _tool_id_to_agent[tool_id] = subagent_type

                    # Extract key parameter for display
                    tool_detail = None
                    if tool_name == 'Read':
                        tool_detail = tool_input.get('file_path', '')
                    elif tool_name == 'Write':
                        tool_detail = tool_input.get('file_path', '')
                    elif tool_name == 'Edit':
                        tool_detail = tool_input.get('file_path', '')
                    elif tool_name == 'Bash':
                        command = tool_input.get('command', '')
                        # Truncate long commands
                        tool_detail = command[:80] + '...' if len(command) > 80 else command
                    elif tool_name == 'Grep':
                        pattern = tool_input.get('pattern', '')
                        tool_detail = f"pattern: {pattern}"
                    elif tool_name == 'Glob':
                        pattern = tool_input.get('pattern', '')
                        tool_detail = f"pattern: {pattern}"
                    elif tool_name == 'Task':
                        subagent = tool_input.get('subagent_type', 'unknown')
                        tool_detail = f"-> {subagent}"

                    # Log to file if logger available (with details)
                    if _session_logger:
                        if tool_detail:
                            _session_logger.debug(f"[{agent_name.upper()}] TOOL: {tool_name} | {tool_detail}")
                        else:
                            _session_logger.debug(f"[{agent_name.upper()}] TOOL: {tool_name}")

                    # Build tool message
                    tool_msg = f"[TOOL] {tool_name}"
                    if tool_detail and tool_name != 'Task':
                        tool_msg += f" | {tool_detail}"
                    if _debug_logging and tool_id:
                        tool_msg += f" (id: {tool_id[:12]})"

                    # Send to Textual UI if available, otherwise print to terminal
                    if _message_handler:
                        # Textual UI mode - delegate to message handler
                        _message_handler.write_message(
                            message=tool_msg,
                            agent=agent_name,
                            timestamp=timestamp if _debug_logging else None
                        )

                        # Show subagent invocation for Task tool
                        if tool_name == 'Task':
                            subagent_type = tool_input.get('subagent_type', 'unknown')
                            description = tool_input.get('description', '')
                            _message_handler.write_message(
                                message=f"  -> Invoking {subagent_type}: {description}",
                                agent=agent_name,
                                timestamp=None
                            )

                        # Show tool input in verbose/debug mode
                        if (_verbose_logging or _debug_logging) and tool_input:
                            # Format tool input as readable text instead of JSON
                            formatted_input = format_tool_input(tool_name, tool_input)
                            # Extract just the parameters part (skip the "Tool: X" line)
                            input_lines = formatted_input.split('\n')[1:]  # Skip first line
                            _message_handler.write_message(
                                message='\n'.join(input_lines),
                                agent=agent_name,
                                timestamp=None
                            )
                    else:
                        # Terminal mode - print with agent identification
                        click.echo(f"[{timestamp}] [{agent_name.upper()}] {tool_msg}")
                        import sys
                        sys.stdout.flush()

                        # Show subagent invocation for Task tool
                        if tool_name == 'Task':
                            subagent_type = tool_input.get('subagent_type', 'unknown')
                            description = tool_input.get('description', '')
                            click.echo(f"  -> Invoking {subagent_type}: {description}")
                            sys.stdout.flush()

                        # Show tool input in verbose/debug mode
                        if (_verbose_logging or _debug_logging) and tool_input:
                            # Format tool input as readable text instead of JSON
                            formatted_input = format_tool_input(tool_name, tool_input)
                            # Extract just the parameters part (skip the "Tool: X" line)
                            input_lines = formatted_input.split('\n')[1:]  # Skip first line
                            for line in input_lines:
                                click.echo(f"  {line}")
                            sys.stdout.flush()

                elif _debug_logging:
                    # Unknown block type
                    click.echo(f"[{timestamp}] [BLOCK:{block_type}] {str(block)[:200]}")
        else:
            # Unknown content type
            if _debug_logging:
                click.echo(f"[{timestamp}] [CONTENT] {str(content)[:500]}")

        return

    elif isinstance(msg, ResultMessage):
        # Tool result - show in verbose mode - FULL, NO TRUNCATION
        if _verbose_logging or _debug_logging:
            result_msg = "[RESULT] Tool execution completed"
            
            # Send to Textual UI if available, otherwise print to terminal
            if _message_handler:
                # Textual UI mode - delegate to message handler
                _message_handler.write_message(
                    message=result_msg,
                    agent=agent_name,
                    timestamp=timestamp if _debug_logging else None
                )
                
                # Show result output in debug mode
                if _debug_logging and hasattr(msg, 'content'):
                    # Format result as readable text
                    formatted_result = format_tool_result(msg.content, is_error=False)
                    # Extract just the content part (skip the "Result: SUCCESS" line)
                    result_lines = formatted_result.split('\n')[1:]  # Skip first line
                    _message_handler.write_message(
                        message='\n'.join(result_lines),
                        agent=agent_name,
                        timestamp=None
                    )
            else:
                # Terminal mode - print to console
                click.echo(f"[{timestamp}] {result_msg}")
                import sys
                sys.stdout.flush()
                
                if _debug_logging and hasattr(msg, 'content'):
                    # Format result as readable text
                    formatted_result = format_tool_result(msg.content, is_error=False)
                    # Extract just the content part (skip the "Result: SUCCESS" line)
                    result_lines = formatted_result.split('\n')[1:]  # Skip first line
                    for line in result_lines:
                        click.echo(f"  {line}")
                    sys.stdout.flush()
        return

    elif isinstance(msg, UserMessage):
        # User message - show in debug mode
        if _debug_logging:
            safe_echo(f"[{timestamp}] [USER] {msg.content if hasattr(msg, 'content') else str(msg)}")
            import sys
            sys.stdout.flush()
        return

    # Handle dict format (fallback for backward compatibility)
    if isinstance(msg, dict):
        msg_type = msg.get("type", "unknown")
    else:
        # Unknown object type
        if _debug_logging:
            click.echo(f"[{timestamp}] [UNKNOWN] {type(msg).__name__}: {str(msg)[:200]}")
        return

    # Legacy dict handling below
    timestamp = datetime.now().strftime("%H:%M:%S")

    if msg_type == "text":
        # Regular text output
        content = msg.get("content", "")
        if content:
            if _debug_logging:
                click.echo(f"[{timestamp}] {content}")
            else:
                click.echo(content)

    elif msg_type == "tool_use":
        # Tool execution
        tool_name = msg.get("name", "unknown")
        tool_id = msg.get("id", "")
        tool_input = msg.get("input", {})

        # Always show tool name with timestamp
        click.echo(f"[{timestamp}] [TOOL] {tool_name}", nl=False)

        # Show tool ID in debug mode
        if _debug_logging and tool_id:
            click.echo(f" (id: {tool_id[:8]}...)", nl=False)

        click.echo()  # Newline

        # Show tool input in verbose mode
        if _verbose_logging and tool_input:
            # Format tool input as readable text instead of JSON
            formatted_input = format_tool_input(tool_name, tool_input)
            # Extract just the parameters part (skip the "Tool: X" line)
            input_lines = formatted_input.split('\n')[1:]  # Skip first line
            for line in input_lines:
                click.echo(f"  {line}")

    elif msg_type == "tool_result":
        # Tool result
        if _verbose_logging:
            tool_id = msg.get("tool_use_id", "")
            content = msg.get("content", "")
            is_error = msg.get("is_error", False)

            status = "ERROR" if is_error else "SUCCESS"
            click.echo(f"[{timestamp}] [RESULT] {status}", nl=False)

            if _debug_logging and tool_id:
                click.echo(f" (id: {tool_id[:8]}...)", nl=False)

            click.echo()

            # Show result content as readable text
            if content:
                # Format result as readable text instead of JSON
                formatted_result = format_tool_result(content, is_error=is_error)
                # Extract just the content part (skip the "Result: SUCCESS/ERROR" line)
                result_lines = formatted_result.split('\n')[1:]  # Skip first line
                for line in result_lines:
                    click.echo(f"  {line}")

    elif msg_type == "error":
        # Error message
        error = msg.get("error", "Unknown error")
        click.echo(f"[{timestamp}] [ERROR] {error}", err=True)

        # Show full error details in debug mode
        if _debug_logging:
            import json
            click.echo(f"  Full error: {json.dumps(msg, indent=2)}", err=True)

    elif msg_type == "agent_start":
        # Agent session started
        agent_name = msg.get("agent", "unknown")
        click.echo(f"[{timestamp}] [AGENT] Starting: {agent_name}")

        if _verbose_logging:
            config = msg.get("config", {})
            if config:
                import json
                click.echo(f"  Config: {json.dumps(config, indent=2)}")

    elif msg_type == "agent_end":
        # Agent session ended
        agent_name = msg.get("agent", "unknown")
        status = msg.get("status", "unknown")
        click.echo(f"[{timestamp}] [AGENT] Ended: {agent_name} (status: {status})")

    else:
        # Unknown message type
        if _debug_logging:
            import json
            click.echo(f"[{timestamp}] [UNKNOWN:{msg_type}] {json.dumps(msg, indent=2)}", err=True)


def main():
    """Main entry point for flow-claude CLI.

    NOTE: As of v6.7+, this redirects to TextualCLI for unified interactive experience.
    Both 'flow' and 'flow-claude' commands use the same interactive session manager.
    """
    # Redirect to TextualCLI instead of the deprecated click-based CLI
    from flow_claude.commands.flow_cli import main as flow_main
    print("\n" + "=" * 70)
    print("NOTE: 'flow-claude' now uses the interactive session manager.")
    print("      For the same experience, you can also use: flow")
    print("=" * 70 + "\n")
    flow_main()


if __name__ == '__main__':
    main()
