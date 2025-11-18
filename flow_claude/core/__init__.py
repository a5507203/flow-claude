"""Core functionality for Flow-Claude.

This module contains the essential logic for git-based autonomous development,
including git tools, parsers, worker management, and MCP configuration.
"""

from .git_tools import create_git_tools_server
from .parsers import (
    parse_task_metadata,
    parse_plan_commit,
    parse_worker_commit,
    parse_commit_message
)
from .sdk_workers import (
    SDKWorkerManager,
    get_sdk_worker_manager,
    create_worker_tools_server,
    build_worker_mcp_servers
)
from .mcp_loader import load_project_mcp_config

__all__ = [
    # Git tools
    'create_git_tools_server',

    # Parsers
    'parse_task_metadata',
    'parse_plan_commit',
    'parse_worker_commit',
    'parse_commit_message',

    # Worker management
    'SDKWorkerManager',
    'get_sdk_worker_manager',
    'create_worker_tools_server',
    'build_worker_mcp_servers',

    # MCP
    'load_project_mcp_config',
]
