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

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition
except ImportError:
    print("ERROR: claude-agent-sdk is not installed.", file=sys.stderr)
    print("Install it with: pip install claude-agent-sdk", file=sys.stderr)
    print("\nNote: You also need Claude Code CLI installed:", file=sys.stderr)
    print("  npm install -g @anthropic-ai/claude-code", file=sys.stderr)
    sys.exit(1)

from .agents import create_planning_agent, create_worker_agent
from .git_tools import create_git_tools_server


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


@click.group()
@click.version_option(version="0.1.0-v6.2")
def cli():
    """Flow-Claude: Git-driven autonomous development using Claude agent SDK.

    Flow-Claude V6.2: Test-Driven + Documentation-First + Continuous Monitoring

    Decomposes development requests into fine-grained tasks (5-10 minutes each),
    executes them autonomously via planning and worker agents, and stores
    all metadata in git commits (no external files).

    Example:
        flow-claude develop "add user authentication with email and password"
    """
    pass


@cli.command()
@click.argument('request', type=str, required=True)
@click.option(
    '--model',
    default='sonnet',
    type=click.Choice(['sonnet', 'opus', 'haiku'], case_sensitive=False),
    help='Claude model to use for agents'
)
@click.option(
    '--max-turns',
    default=100,
    type=int,
    help='Maximum conversation turns per agent'
)
@click.option(
    '--permission-mode',
    default='acceptEdits',
    type=click.Choice(['acceptEdits', 'ask', 'deny'], case_sensitive=False),
    help='Permission mode for tool usage'
)
@click.option(
    '--max-parallel',
    default=3,
    type=int,
    help='Maximum number of parallel workers (default: 3). Set to 1 for sequential execution.'
)
@click.option(
    '--verbose',
    is_flag=True,
    default=False,
    help='Enable verbose logging (show tool inputs/outputs, agent activity)'
)
@click.option(
    '--debug',
    is_flag=True,
    default=False,
    help='Enable debug mode (show all messages, connection details)'
)
def develop(
    request: str,
    model: str,
    max_turns: int,
    permission_mode: str,
    max_parallel: int,
    verbose: bool,
    debug: bool
):
    """Execute development request using planning and worker agents.

    This command starts a Flow-Claude development session:
    1. Planning agent analyzes request and creates execution plan
    2. Planning agent spawns worker agents for individual tasks
    3. Workers implement tasks, test, and signal completion
    4. Planning agent validates and merges completed tasks
    5. Planning agent handles dynamic replanning if needed

    Args:
        REQUEST: Natural language description of what to implement

    Examples:
        flow-claude develop "add user authentication"
        flow-claude develop "refactor database layer to use async"
        flow-claude develop "fix bug in payment processing" --model opus
    """
    # Check if Claude Code CLI is available
    is_available, message = check_claude_code_available()
    if not is_available:
        click.echo(f"ERROR: {message}", err=True)
        click.echo("\nClaude Code CLI is required for Flow-Claude to work.", err=True)
        click.echo("After installing, authenticate with: claude auth login", err=True)
        sys.exit(1)

    # Determine execution mode based on max_parallel
    # Parallel mode enabled automatically when max_parallel > 1
    enable_parallel = max_parallel > 1

    # Auto-initialize git repository if needed
    if not os.path.exists('.git'):
        click.echo("WARNING: Not a git repository. Initializing git repository...\n")
        import subprocess
        try:
            # Initialize git
            subprocess.run(['git', 'init'], check=True, capture_output=True)
            click.echo("SUCCESS: Initialized git repository")

            # Create initial empty commit
            result = subprocess.run(
                ['git', 'commit', '--allow-empty', '-m', 'Initial commit'],
                check=True,
                capture_output=True,
                text=True
            )
            click.echo("SUCCESS: Created initial commit\n")

        except subprocess.CalledProcessError as e:
            click.echo(f"ERROR: Failed to initialize git repository: {e}", err=True)
            sys.exit(1)
        except FileNotFoundError:
            click.echo("ERROR: git command not found. Install git first.", err=True)
            sys.exit(1)

    # V6.3: Load prompts from files using @filepath syntax
    # Orchestrator is main agent, planner and workers are subagents
    # The SDK loads the full file content at runtime
    # V6.7: Check for instruction files in working directory first (user's git repo)
    # This allows users to customize agent behavior per-project
    working_dir = os.getcwd()
    prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

    def get_prompt_file(local_name, fallback_name):
        """Get prompt file from working dir, copying default if it doesn't exist."""
        local_path = os.path.join(working_dir, local_name)
        default_path = os.path.abspath(os.path.join(prompts_dir, fallback_name))

        # If local prompt doesn't exist, copy the default template
        if not os.path.exists(local_path):
            try:
                import shutil
                shutil.copy2(default_path, local_path)
                if debug:
                    click.echo(f"DEBUG: Copied default prompt {fallback_name} -> {local_name}")
            except Exception as e:
                # If copy fails, fall back to using default directly
                if debug:
                    click.echo(f"DEBUG: Failed to copy prompt, using default: {e}")
                return default_path

        return local_path

    # Get absolute paths for prompts (use working dir, auto-copy if missing)
    orchestrator_prompt_file = get_prompt_file('ORCHESTRATOR_INSTRUCTIONS.md', 'orchestrator.md')
    planner_prompt_file = get_prompt_file('PLANNER_INSTRUCTIONS.md', 'planner.md')
    worker_prompt_file = get_prompt_file('WORKER_INSTRUCTIONS.md', 'worker.md')
    user_proxy_prompt_file = get_prompt_file('USER_PROXY_INSTRUCTIONS.md', 'user.md')

    # Use @filepath syntax for all agents
    orchestrator_prompt = f"@{orchestrator_prompt_file}"
    planner_prompt = f"@{planner_prompt_file}"
    worker_prompt = f"@{worker_prompt_file}"
    user_proxy_prompt = f"@{user_proxy_prompt_file}"

    # Determine number of workers
    num_workers = max_parallel if enable_parallel else 1

    if debug or verbose:
        click.echo(f"DEBUG: Loading agent prompts:")
        click.echo(f"  Orchestrator: {orchestrator_prompt_file}")
        click.echo(f"  Planner: {planner_prompt_file}")
        click.echo(f"  Worker: {worker_prompt_file}")
        click.echo(f"  User Proxy: {user_proxy_prompt_file}")
        click.echo(f"DEBUG: - orchestrator-minimal.md: {orchestrator_prompt}")
        click.echo(f"DEBUG: - planner.md: {planner_prompt}")
        click.echo(f"DEBUG: - worker.md: {worker_prompt}")
        click.echo(f"DEBUG: - user.md: {user_proxy_prompt}")
        click.echo(f"DEBUG: Registering 1 planner + 1 user + {num_workers} worker subagents")
        click.echo()

    # Run async session
    try:
        asyncio.run(run_development_session(
            request=request,
            model=model,
            max_turns=max_turns,
            permission_mode=permission_mode,
            enable_parallel=enable_parallel,
            max_parallel=max_parallel,
            verbose=verbose,
            debug=debug,
            orchestrator_prompt=orchestrator_prompt,
            planner_prompt=planner_prompt,
            worker_prompt=worker_prompt,
            user_proxy_prompt=user_proxy_prompt,
            num_workers=num_workers
        ))
    except KeyboardInterrupt:
        click.echo("\n\nWARNING: Development session interrupted by user.", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"\n\nERROR: Development session failed: {e}", err=True)
        raise


async def run_development_session(
    request: str,
    model: str,
    max_turns: int,
    permission_mode: str,
    enable_parallel: bool,
    max_parallel: int,
    verbose: bool,
    debug: bool,
    orchestrator_prompt: str,
    planner_prompt: str,
    worker_prompt: str,
    user_proxy_prompt: str,
    num_workers: int,
    control_queue: Optional[asyncio.Queue] = None,
    logger: Optional[object] = None  # FlowClaudeLogger instance
):
    """Run development session with orchestrator, planner, user, and worker agents.

    Args:
        request: User's development request
        model: Claude model to use (sonnet/opus/haiku)
        max_turns: Maximum conversation turns
        permission_mode: Permission mode for tools
        enable_parallel: Enable parallel task execution
        max_parallel: Maximum number of parallel workers
        verbose: Enable verbose logging
        debug: Enable debug mode
        orchestrator_prompt: Orchestrator agent system prompt (@filepath syntax)
        planner_prompt: Planner subagent prompt (@filepath syntax)
        worker_prompt: Worker subagent prompt template (@filepath syntax)
        user_proxy_prompt: User proxy subagent prompt (@filepath syntax)
        num_workers: Number of worker agents to create

    Note:
        All prompts use @filepath syntax.
        The SDK loads the full file content at runtime.
        V6.6 adds user agent for user confirmations and decision points.
    """
    # Store logging flags and logger globally for use in handle_agent_message
    global _verbose_logging, _debug_logging, _session_logger, _tool_id_to_agent
    _verbose_logging = verbose
    _debug_logging = debug
    _session_logger = logger
    _tool_id_to_agent = {}  # Clear agent tracking for new session
    # Print banner
    click.echo("=" * 60)
    click.echo("Flow-Claude V6.6 Development Session Starting...")
    click.echo("=" * 60)
    click.echo(f"\nRequest: {request}")
    click.echo(f"Model: {model}")
    click.echo(f"Architecture: V6.6 (Orchestrator + Planner + User Proxy + Workers)")
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

    # V6.5: Generate unique session ID for timestamped plan branch
    # Format: session-YYYYMMDD-HHMMSS (e.g., session-20250115-143000)
    session_id = datetime.now().strftime("session-%Y%m%d-%H%M%S")
    plan_branch = f"plan/{session_id}"

    if debug:
        safe_echo(f"DEBUG: Generated session ID: {session_id}")
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

    # V6.6: Four-tier architecture - orchestrator is main agent, planner, user, and workers are subagents
    # Orchestrator (orchestrator-minimal.md) coordinates everything
    # Planner (planner.md) creates execution plans
    # User Proxy (user.md) handles user confirmations
    # Workers (worker.md) execute individual tasks
    # SDK v0.1.6+ automatically handles Windows cmd.exe 8191-char limit via temp files (PR #245)
    agent_definitions = {}

    # Define planner subagent (V6.7: Commit-only architecture - NO Write/Edit tools!)
    agent_definitions['planner'] = AgentDefinition(
        description='Planning agent that creates execution plans and breaks down requests',
        prompt=planner_prompt,
        tools=[
            'Task', 'Bash', 'Read', 'Grep', 'Glob',
            # Commit-only architecture - planner uses git commits, NOT files
            'mcp__git__parse_plan',  # Read plan from commits
            'mcp__git__parse_task',  # Read task metadata from commits
            'mcp__git__parse_worker_commit',  # Monitor worker progress
            'mcp__git__get_provides'  # Query completed task capabilities
        ],
        model=model
    )

    # Define user subagent (V6.6: New - handles user confirmations)
    agent_definitions['user'] = AgentDefinition(
        description='User proxy agent that represents the user for confirmation dialogs',
        prompt=user_proxy_prompt,
        tools=[],  # User proxy doesn't need tools - just facilitates user interaction
        model='haiku'  # Use haiku for fast, cheap confirmation dialogs
    )

    # Define worker subagents
    for i in range(1, num_workers + 1):
        agent_definitions[f'worker-{i}'] = AgentDefinition(
            description=f'Worker agent {i} that executes individual development tasks',
            prompt=worker_prompt,
            tools=[
                'Bash', 'Read', 'Write', 'Edit', 'Grep', 'Glob',
                'mcp__git__parse_task',  # Read task metadata from branch
                'mcp__git__parse_plan',  # Read plan context
                'mcp__git__parse_worker_commit'  # Read own progress (commit-only architecture)
            ],
            model=model
        )

    if debug:
        click.echo(f"DEBUG: Created {len(agent_definitions)} agent definitions (1 planner + 1 user + {num_workers} workers):")
        for agent_name, agent_def in agent_definitions.items():
            click.echo(f"DEBUG:   - {agent_name}: {agent_def.description}")
            click.echo(f"DEBUG:     tools: {agent_def.tools}")
            click.echo(f"DEBUG:     model: {agent_def.model}")
            click.echo(f"DEBUG:     prompt length: {len(agent_def.prompt)} chars")
        click.echo()

    # Configure agent options with programmatic agents
    options = ClaudeAgentOptions(
        system_prompt=orchestrator_prompt,  # Main orchestrator system prompt (@filepath syntax)
        agents=agent_definitions,  # Planner + worker subagent definitions
        allowed_tools=[
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
        ],
        mcp_servers={
            "git": create_git_tools_server()
        },
        permission_mode=permission_mode,
        max_turns=max_turns,
        cwd=os.getcwd(),
        cli_path=claude_path  # Explicitly set Claude CLI path
    )

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
- Execute tasks in dependency-ordered waves
- Respect max parallel limit
"""
    else:
        parallel_config = f"""
**Parallel Execution:** DISABLED
- Worker available: worker-1
- Execute tasks sequentially (one at a time)
"""

    # Create initial query with session configuration
    # The system prompt (orchestrator-minimal.md) is already loaded via @filepath in ClaudeAgentOptions
    initial_prompt = f"""# Development Session Configuration (V6.6)

**User Request:** {request}

**Session Information (CRITICAL):**
- Session ID: {session_id}
- Plan Branch: {plan_branch}

**Model:** {model}
**Working Directory:** {os.getcwd()}

{parallel_config}

**Available Subagents:**
- **planner** - Planning subagent (invoke FIRST to create execution plan)
- **user** - User proxy subagent (invoke for user confirmations and decisions)
{chr(10).join([f'- worker-{i} - Worker subagent (invoke for task execution)' for i in range(1, num_workers + 1)])}

---

**CRITICAL - Wave-Based Ping-Pong Execution:**

You are the Orchestrator. You coordinate a PING-PONG pattern between planner and workers:
1. Invoke planner → planner creates branches → returns to you
2. Spawn workers → workers execute and merge → return to you
3. Invoke planner again → planner updates docs and creates next wave → returns to you
4. Repeat until done

**WHY:** The planner CANNOT spawn workers (SDK constraint). Only you can spawn subagents.

**Round 1 - Initial Invoke:**

```
Task tool:
{{
  "subagent_type": "planner",
  "description": "Create plan and Wave 1 branches",
  "prompt": "**FIRST:** Read your instructions at PLANNER_INSTRUCTIONS.md (if it exists in working directory).

Create execution plan and Wave 1 task branches for this request:

**User Request:** {request}

**Session Information:**
- Session ID: {session_id}
- Plan Branch: {plan_branch}
- Working Directory: {os.getcwd()}

Follow your Phase 1 workflow from PLANNER_INSTRUCTIONS.md."
}}
```

**After Planner Returns:**
1. Use mcp__git__parse_plan or run `git branch --list 'task/*'` to see what branches were created
2. **Create git worktrees for parallel execution** (CRITICAL for avoiding conflicts):
   ```bash
   # For each task branch in the current wave:
   git worktree add .worktrees/worker-1 task/001-description
   git worktree add .worktrees/worker-2 task/002-description
   # etc. One worktree per worker, linked to task branch
   ```
3. Spawn ALL wave workers IN ONE MESSAGE for parallelization
   - Include **Worktree Path** in each worker's prompt (e.g., `.worktrees/worker-1`)
   - Workers use worktrees instead of git checkout (no conflicts!)
4. Wait for workers to complete and merge
5. **Clean up worktrees after wave completes**:
   ```bash
   git worktree remove .worktrees/worker-1
   git worktree remove .worktrees/worker-2
   # etc.
   ```
6. Check if more waves remain (use mcp__git__parse_plan for pending tasks)
7. If yes: Invoke planner again with "Wave N complete. Prepare Wave N+1." prompt (go back to step 2)
8. If no: Invoke planner with "All waves complete. Generate final report." prompt
9. Report final results to user

**YOUR ROLE:** Coordinate the loop. The planner creates branches and updates docs. Workers execute tasks. You orchestrate between them.

**User Proxy Usage:**
The user agent is available for key decision points:
- After planner creates plan (get user confirmation)
- When tasks are blocked (get user decision)
- At session completion (acknowledge results)
"""

    # Start session
    try:
        async with ClaudeSDKClient(options=options) as client:
            # Send initial query to orchestrator
            await client.query(initial_prompt)

            # Multi-turn conversation loop
            # The orchestrator needs to be able to send follow-up queries
            # after processing responses (e.g., checking if planner created branches)
            turn_number = 0

            while turn_number < max_turns:
                turn_number += 1

                if debug:
                    click.echo(f"\nDEBUG: Turn {turn_number}/{max_turns}")

                # Receive and process all messages for this turn
                response_complete = False
                pending_intervention = None
                intervention_requested = False
                shutdown_requested = False

                async for msg in client.receive_response():
                    handle_agent_message(msg)

                    # Check for interventions after each message for more responsive handling
                    if control_queue and not pending_intervention and not intervention_requested:
                        try:
                            control = control_queue.get_nowait()
                            control_type = control.get("type")

                            if control_type == "intervention_pending":
                                # User pressed ESC - wait for turn to complete before prompting
                                intervention_requested = True

                            elif control_type == "intervention":
                                # Direct intervention with requirement already provided
                                requirement = control.get("data", {}).get("requirement", "")
                                if requirement:
                                    pending_intervention = requirement
                                    click.echo(f"\n[INTERVENTION QUEUED] Requirement will be injected after current operation: {requirement[:80]}...\n")

                            elif control_type == "shutdown":
                                # User pressed 'q' to quit
                                shutdown_requested = True
                                click.echo("\n[SHUTDOWN QUEUED] Will stop after current operation...\n")

                        except asyncio.QueueEmpty:
                            pass  # No intervention

                    # Check if this is the last message in the response
                    # (The SDK will stop yielding when response is complete)
                    response_complete = True

                if not response_complete:
                    # No more messages, conversation ended naturally
                    break

                # Handle shutdown immediately
                if shutdown_requested:
                    click.echo("\n[SHUTDOWN] Stopping execution\n")
                    break

                # Handle intervention request - prompt user now that output has settled
                if intervention_requested:
                    click.echo()
                    click.echo("  " + "=" * 76)
                    click.echo("  INTERVENTION MODE")
                    click.echo("  " + "=" * 76)
                    click.echo()
                    click.echo("  You can add additional requirements to the current task.")
                    click.echo("  (Press Enter with empty input to resume without changes)")
                    click.echo()

                    # Get requirement from user
                    import sys
                    try:
                        requirement = input("  > Additional requirement: ").strip()
                        sys.stdout.flush()

                        if requirement:
                            pending_intervention = requirement
                            click.echo()
                            click.echo("  ✓ Requirement will be sent to orchestrator")
                        else:
                            click.echo()
                            click.echo("  No requirement added. Continuing...")

                        click.echo("  " + "=" * 76)
                        click.echo()
                    except (EOFError, KeyboardInterrupt):
                        click.echo()
                        click.echo("  Intervention cancelled")
                        click.echo("  " + "=" * 76)
                        click.echo()

                # Inject pending intervention immediately after turn completes
                if pending_intervention:
                    click.echo(f"\n[INTERVENTION] Injecting requirement: {pending_intervention}\n")
                    # Inject as new query into conversation
                    await client.query(f"IMPORTANT - User Intervention: The user has added a new requirement mid-execution: {pending_intervention}\n\nPlease incorporate this requirement into your current work.")
                    # Clear the intervention
                    pending_intervention = None

                # Note: The orchestrator system prompt should handle continuation
                # It will use tools and self-direct its own next steps
                # We just need to keep the conversation open for follow-ups
                # The orchestrator will signal completion by not using any more tools

            if turn_number >= max_turns:
                click.echo(f"\nWARNING: Reached maximum turns ({max_turns})", err=True)

        # Session complete
        click.echo("\n" + "=" * 60)
        click.echo("SUCCESS: Development session complete!")
        click.echo("=" * 60)

    except Exception as e:
        click.echo(f"\nERROR: Error during development session: {e}", err=True)
        raise


def handle_agent_message(msg):
    """Handle and display agent messages with enhanced logging.

    Args:
        msg: Message object from SDK (SystemMessage, AssistantMessage, etc.) or dict

    Message types:
        - SystemMessage: System messages
        - AssistantMessage: Agent text output (contains TextBlock and ToolUseBlock)
        - ResultMessage: Tool results
        - UserMessage: User input
        - dict with "type": Legacy format
    """
    global _verbose_logging, _debug_logging, _session_logger, _tool_id_to_agent

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

                        # Print to terminal with agent identification
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
                        tool_detail = f"→ {subagent}"

                    # Log to file if logger available (with details)
                    if _session_logger:
                        if tool_detail:
                            _session_logger.debug(f"[{agent_name.upper()}] TOOL: {tool_name} | {tool_detail}")
                        else:
                            _session_logger.debug(f"[{agent_name.upper()}] TOOL: {tool_name}")

                    # Always show tool name with agent identification
                    click.echo(f"[{timestamp}] [{agent_name.upper()}] [TOOL] {tool_name}", nl=False)

                    # Show tool detail on same line if available
                    if tool_detail and tool_name != 'Task':  # Task has special display below
                        click.echo(f" | {tool_detail}", nl=False)

                    import sys
                    sys.stdout.flush()

                    if _debug_logging and tool_id:
                        click.echo(f" (id: {tool_id[:12]})", nl=False)
                        sys.stdout.flush()

                    click.echo()  # Newline
                    sys.stdout.flush()

                    # Show subagent invocation for Task tool
                    if tool_name == 'Task':
                        subagent_type = tool_input.get('subagent_type', 'unknown')
                        description = tool_input.get('description', '')
                        click.echo(f"  → Invoking {subagent_type}: {description}")
                        sys.stdout.flush()

                    # Show tool input in verbose/debug mode - FULL, NO TRUNCATION
                    if (_verbose_logging or _debug_logging) and tool_input:
                        import json
                        input_str = json.dumps(tool_input, indent=2)
                        click.echo(f"  Input: {input_str}")
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
            click.echo(f"[{timestamp}] [RESULT] Tool execution completed")
            import sys
            sys.stdout.flush()
            if _debug_logging and hasattr(msg, 'content'):
                result_str = str(msg.content)
                click.echo(f"  Output: {result_str}")
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
            import json
            # Truncate long inputs
            input_str = json.dumps(tool_input, indent=2)
            if len(input_str) > 500:
                input_str = input_str[:500] + "..."
            click.echo(f"  Input: {input_str}")

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

            # Show result content (truncated)
            if content:
                import json
                if isinstance(content, str):
                    result_str = content
                else:
                    result_str = json.dumps(content, indent=2)

                if len(result_str) > 300:
                    result_str = result_str[:300] + "..."

                click.echo(f"  Output: {result_str}")

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
    """Main entry point for flow-claude CLI."""
    cli()


if __name__ == '__main__':
    main()
