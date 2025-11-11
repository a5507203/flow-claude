"""Agent definitions for Flow-Claude planning and worker agents.

This module creates AgentDefinition instances for the planning agent
and worker agent, loading their system prompts from markdown files.
"""

from pathlib import Path
from typing import Optional

try:
    from claude_agent_sdk import AgentDefinition
except ImportError:
    # Fallback for development/testing
    class AgentDefinition:
        """Fallback AgentDefinition for when SDK is not installed."""
        def __init__(self, description: str, prompt: str, tools: list, model: str = "sonnet"):
            self.description = description
            self.prompt = prompt
            self.tools = tools
            self.model = model


def load_prompt(filename: str) -> str:
    """Load prompt from prompts/ directory.

    Args:
        filename: Name of prompt file (e.g., "planner.md")

    Returns:
        Prompt text as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    # Get path relative to this file's parent directory
    prompt_file = Path(__file__).parent.parent / "prompts" / filename

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_file}\n"
            f"Make sure prompts/{filename} exists in the project root."
        )

    return prompt_file.read_text(encoding='utf-8')


def create_planning_agent(model: str = "sonnet") -> AgentDefinition:
    """Create planning agent definition.

    The planning agent is responsible for:
    - Analyzing user requests and codebase
    - Creating execution plans (git-first)
    - Spawning worker agents for tasks
    - Monitoring task completions
    - Validating and merging completed tasks
    - Dynamic replanning when needed

    Args:
        model: Claude model to use (sonnet, opus, haiku)

    Returns:
        AgentDefinition configured with planner.md prompt

    Tools Available:
        - Bash: For git operations
        - Read: For reading codebase files
        - Grep: For searching code
        - Glob: For finding files by pattern
        - mcp__git__parse_task: Parse task metadata from commits
        - mcp__git__parse_plan: Parse plan from plan branch
        - mcp__git__get_provides: Get available preconditions
        - mcp__git__create_plan_branch: Create plan branch with metadata
        - mcp__git__create_task_branch: Create task branch with metadata
        - mcp__git__update_plan_branch: Update plan with completed tasks
    """
    try:
        prompt = load_prompt("planner.md")
    except FileNotFoundError as e:
        # Provide a minimal fallback prompt
        prompt = f"""# Flow-Claude Planning Agent

ERROR: Could not load planner.md prompt file.

{str(e)}

Please create prompts/planner.md with the complete planning agent workflow.
"""

    return AgentDefinition(
        description="Decomposes user requests into fine-grained tasks and orchestrates execution",
        prompt=prompt,
        tools=[
            "Bash",
            "Read",
            "Grep",
            "Glob",
            "mcp__git__parse_task",
            "mcp__git__parse_plan",
            "mcp__git__get_provides",
            "mcp__git__create_plan_branch",
            "mcp__git__create_task_branch",
            "mcp__git__update_plan_branch",
        ],
        model=model,
    )


def create_worker_agent(model: str = "sonnet") -> AgentDefinition:
    """Create worker agent definition.

    The worker agent is responsible for:
    - Reading task metadata from git commits
    - Understanding task context and session goals
    - Reading preconditions from flow branch
    - Implementing the task using Read/Write/Edit/Bash
    - Testing the implementation
    - Signaling completion/blocked/failed status

    Args:
        model: Claude model to use (sonnet, opus, haiku)

    Returns:
        AgentDefinition configured with worker.md prompt

    Tools Available:
        - Bash: For git operations and testing
        - Read: For reading files
        - Write: For creating new files
        - Edit: For modifying existing files
        - Grep: For searching code
        - mcp__git__parse_task: Parse task metadata from commits
    """
    try:
        prompt = load_prompt("worker.md")
    except FileNotFoundError as e:
        # Provide a minimal fallback prompt
        prompt = f"""# Flow-Claude Worker Agent

ERROR: Could not load worker.md prompt file.

{str(e)}

Please create prompts/worker.md with the complete worker agent workflow.
"""

    return AgentDefinition(
        description="Executes individual development tasks with context awareness",
        prompt=prompt,
        tools=[
            "Bash",
            "Read",
            "Write",
            "Edit",
            "Grep",
            "mcp__git__parse_task",
        ],
        model=model,
    )
