"""MCP configuration loader for Flow-Claude.

Loads MCP server configurations from project's .mcp.json file.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def load_project_mcp_config(project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load MCP server configurations from project's .mcp.json.

    Args:
        project_dir: Project root directory. Defaults to current working directory.

    Returns:
        Dict of MCP server configurations from the "mcpServers" field.
        Returns empty dict if file doesn't exist or on error.

    Example .mcp.json format:
        {
          "mcpServers": {
            "playwright": {
              "type": "stdio",
              "command": "cmd",
              "args": ["/c", "npx", "@playwright/mcp@latest"],
              "env": {}
            }
          }
        }

    Example usage:
        >>> mcp_config = load_project_mcp_config()
        >>> print(mcp_config.keys())
        dict_keys(['playwright'])

    File location:
        - Main project: <project_root>/.mcp.json
        - Worker worktrees: <worktree_root>/.mcp.json
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    mcp_json_path = project_dir / ".mcp.json"

    # Return empty dict if file doesn't exist
    if not mcp_json_path.exists():
        return {}

    try:
        with open(mcp_json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Extract mcpServers field
        mcp_servers = config.get("mcpServers", {})

        if not isinstance(mcp_servers, dict):
            return {}

        return mcp_servers

    except (json.JSONDecodeError, IOError, OSError):
        # Return empty dict on any error (invalid JSON, read error, etc.)
        return {}
