"""MCP server catalog — listing, detail, introspected-manifest submission and assessment.

Thin HTTP layer over the MCP services (injected via the DI container), mapping domain errors to
HTTP status. Reads are open; submitting a manifest or an assessment requires the contributor role;
deletion requires admin.

A server enters the catalog by CLIENT-SIDE introspection — the caller's Claude Code enumerates the
tool surface of a server it is already connected to and POSTs that manifest. This service never
connects out to a third-party MCP server and holds no credentials for one."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from skillhub_core.mcp.errors import InvalidManifest, McpServerNotFound
from skillhub_core.mcp.schemas import (
    McpAssessmentIn,
    McpRubricOut,
    McpServerDetail,
    McpServerIn,
    McpServerSummary,
)
from skillhub_core.mcp.services import McpRubricService, McpService
from skillhub_core.platform.models import User

from ..auth import require_admin, require_upload
from ..deps import get_mcp_rubric_service, get_mcp_service

router = APIRouter(tags=["mcp"])


@router.get("/mcp/rubric", response_model=McpRubricOut)
def get_mcp_rubric(service: McpRubricService = Depends(get_mcp_rubric_service)) -> McpRubricOut:
    """The MCP evaluation strategy — fetch this before scoring a server's tool surface."""
    return service.get_rubric()


@router.get("/mcp", response_model=list[McpServerSummary])
def list_mcp_servers(
    search: str | None = None,
    family: str | None = None,
    service: McpService = Depends(get_mcp_service),
) -> list[McpServerSummary]:
    return service.list(search=search, family=family)


@router.post("/mcp", response_model=McpServerDetail, status_code=201)
def submit_manifest(
    payload: McpServerIn,
    service: McpService = Depends(get_mcp_service),
    user: User = Depends(require_upload),
) -> McpServerDetail:
    """Create or refresh a server from an introspected tool manifest. Re-submitting an existing
    name adds a new version; an unchanged manifest is a no-op."""
    try:
        return service.submit_manifest(payload.model_dump(), created_by_user_id=user.id)
    except InvalidManifest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mcp/{server_id}", response_model=McpServerDetail)
def get_mcp_server(
    server_id: int, service: McpService = Depends(get_mcp_service)
) -> McpServerDetail:
    try:
        return service.get(server_id)
    except McpServerNotFound as exc:
        raise HTTPException(status_code=404, detail="MCP server not found") from exc


@router.post("/mcp/{server_id}/assessment", response_model=McpServerDetail)
def submit_mcp_assessment(
    server_id: int,
    payload: McpAssessmentIn,
    service: McpService = Depends(get_mcp_service),
    _: User = Depends(require_upload),
) -> McpServerDetail:
    try:
        return service.submit_assessment(
            server_id,
            payload.evaluation.model_dump(),
            model=payload.model,
            rubric_version=payload.rubric_version,
        )
    except McpServerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/mcp/{server_id}", status_code=204)
def delete_mcp_server(
    server_id: int,
    service: McpService = Depends(get_mcp_service),
    _: User = Depends(require_admin),
) -> Response:
    try:
        service.delete(server_id)
    except McpServerNotFound as exc:
        raise HTTPException(status_code=404, detail="MCP server not found") from exc
    return Response(status_code=204)
