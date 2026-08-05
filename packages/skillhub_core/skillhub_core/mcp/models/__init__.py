"""MCP context models — re-exported so callers import from ``skillhub_core.mcp.models``.
Importing this package registers the models on the shared :class:`Base`."""

from __future__ import annotations

from .mcp_evaluation import McpEvaluation
from .mcp_server import (
    MCP_SOURCE_TYPES,
    SOURCE_INTROSPECTED,
    SOURCE_MANUAL,
    TRANSPORT_HTTP,
    TRANSPORT_STDIO,
    TRANSPORTS,
    McpServer,
    McpServerVersion,
)

__all__ = [
    "McpServer",
    "McpServerVersion",
    "McpEvaluation",
    "TRANSPORT_STDIO",
    "TRANSPORT_HTTP",
    "TRANSPORTS",
    "SOURCE_INTROSPECTED",
    "SOURCE_MANUAL",
    "MCP_SOURCE_TYPES",
]
