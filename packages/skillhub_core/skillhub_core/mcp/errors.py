"""Domain errors for the MCP context.

Services raise these; the API layer maps them to HTTP status codes, so the services stay
framework-agnostic and unit-testable without FastAPI."""

from __future__ import annotations


class McpError(Exception):
    """Base class for MCP-context domain errors."""


class McpServerNotFound(McpError):
    """An operation referenced an MCP server id that does not exist (mapped to 404)."""


class InvalidManifest(McpError):
    """A submitted tool manifest failed validation — no name, or no tools (mapped to 400)."""
