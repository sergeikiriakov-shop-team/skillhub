"""Application services for the MCP context.

Depend only on the repository Protocol, own the transaction boundary, and raise domain errors the
API layer maps to HTTP. No SQLAlchemy, no FastAPI."""

from __future__ import annotations

from .errors import InvalidManifest, McpServerNotFound
from .interfaces import McpRepository
from .rubric import (
    MCP_INTROSPECTION_PROTOCOL,
    MCP_RECOMMENDATION_STRATEGY,
    MCP_RUBRIC_CALIBRATION,
    MCP_RUBRIC_DIMENSIONS,
    MCP_RUBRIC_INSTRUCTIONS,
    MCP_RUBRIC_VERSION,
    MCP_RUBRIC_WEIGHTS,
)
from .schemas import (
    McpEvaluationResult,
    McpRubricOut,
    McpServerDetail,
    McpServerSummary,
)


class McpRubricService:
    """Serves the MCP evaluation strategy. Static by design — unlike the skills rubric, the MCP
    weights are not admin-editable yet, so there is nothing to persist."""

    def get_rubric(self) -> McpRubricOut:
        return McpRubricOut(
            rubric_version=MCP_RUBRIC_VERSION,
            instructions=MCP_RUBRIC_INSTRUCTIONS,
            dimensions=MCP_RUBRIC_DIMENSIONS,
            weights=MCP_RUBRIC_WEIGHTS,
            calibration=MCP_RUBRIC_CALIBRATION,
            evaluation_schema=McpEvaluationResult.model_json_schema(),
            recommendation_strategy=MCP_RECOMMENDATION_STRATEGY,
            introspection_protocol=MCP_INTROSPECTION_PROTOCOL,
        )


class McpService:
    """Catalogued MCP servers: listing, detail, manifest submission and assessment."""

    def __init__(self, servers: McpRepository) -> None:
        self._servers = servers

    def list(self, search: str | None = None, family: str | None = None) -> list[McpServerSummary]:
        return self._servers.list(search=search, family=family)

    def get(self, server_id: int) -> McpServerDetail:
        server = self._servers.get(server_id)
        if server is None:
            raise McpServerNotFound(f"mcp server {server_id} does not exist")
        return server

    def submit_manifest(self, payload: dict, *, created_by_user_id: int | None) -> McpServerDetail:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise InvalidManifest("a server name is required")
        tools = payload.get("tools") or []
        if not tools:
            raise InvalidManifest(
                "a manifest with no tools is not a usable surface — introspect the connected "
                "server and submit its actual tool list"
            )
        for tool in tools:
            if not str((tool or {}).get("name") or "").strip():
                raise InvalidManifest("every tool needs its exact name")
        server = self._servers.upsert({**payload, "name": name, "tools": tools}, created_by_user_id)
        self._servers.commit()
        return server

    def submit_assessment(
        self, server_id: int, evaluation: dict, *, model: str, rubric_version: str | None = None
    ) -> McpServerDetail:
        server = self._servers.save_assessment(server_id, evaluation, model, rubric_version)
        if server is None:
            raise McpServerNotFound(
                f"mcp server {server_id} does not exist, or has no introspected version to score"
            )
        self._servers.commit()
        return server

    def delete(self, server_id: int) -> None:
        if not self._servers.delete(server_id):
            raise McpServerNotFound(f"mcp server {server_id} does not exist")
        self._servers.commit()
