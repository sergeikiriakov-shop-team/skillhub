"""Repository Protocols for the MCP context — the seams the services depend on.

Return API DTOs (not ORM) so the services stay DB- and framework-free and are unit-testable with an
in-memory fake. The SQLAlchemy implementations live in ``skillhub_core.mcp.repositories``."""

from __future__ import annotations

from typing import Protocol

from .schemas import McpServerDetail, McpServerSummary


class McpRepository(Protocol):
    """Persistence and reads for catalogued MCP servers. The service owns the commit."""

    def list(self, *, search: str | None = None, family: str | None = None) -> list[McpServerSummary]: ...

    def get(self, server_id: int) -> McpServerDetail | None: ...

    def upsert(self, payload: dict, created_by_user_id: int | None) -> McpServerDetail:
        """Create the server, or add a new version to the existing ``name``. An unchanged manifest
        (same content hash as the latest version) is a no-op returning the current state. Flush only."""
        ...

    def save_assessment(
        self, server_id: int, evaluation: dict, model: str, rubric_version: str | None
    ) -> McpServerDetail | None:
        """Attach an evaluation to the server's latest version, recomputing ``overall`` server-side
        from the rubric weights. None if the server (or its version) does not exist. Flush only."""
        ...

    def delete(self, server_id: int) -> bool: ...

    def commit(self) -> None: ...
