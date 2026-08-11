"""Persistence for the McpServer aggregate: introspected versions, their tool surface and scores.

Serialization lives in ``..serializers``; this module queries and writes."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ...skills.models import Recommendation
from ...skills.rubric import compute_overall
from ..models import McpEvaluation, McpServer, McpServerVersion
from ..rubric import MCP_RUBRIC_VERSION, MCP_RUBRIC_WEIGHTS
from ..schemas import McpServerDetail, McpServerSummary
from ..serializers import _to_detail, _to_summary

_DIMENSION_KEYS = tuple(MCP_RUBRIC_WEIGHTS.keys())


def _loaded_server_query():
    return select(McpServer).options(
        selectinload(McpServer.versions).selectinload(McpServerVersion.evaluations),
        selectinload(McpServer.versions).selectinload(McpServerVersion.creator),
    )


def manifest_hash(tools: list[dict]) -> str:
    """Stable hash of a tool manifest — order-insensitive on tools, so a server that merely
    reorders its tool list does not read as drift."""
    normalized = sorted(
        (
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema") or {},
            }
            for t in tools
        ),
        key=lambda t: t["name"],
    )
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()




def open_mcp_recommendations(session: Session, server: McpServer) -> list[Recommendation]:
    """Every OPEN (proposed/accepted) recommendation with ``target_kind='mcp'`` applying to this
    server: it is a named target, or the scope matches the server's name or family. Mirrors
    ``open_recommendations_for_skill`` in the skills context."""
    rows = session.scalars(
        select(Recommendation).where(
            Recommendation.target_kind == "mcp",
            Recommendation.status.in_(["proposed", "accepted"]),
        )
    ).all()
    matches = []
    for rec in rows:
        targets = rec.targets or []
        if (
            server.name in targets
            or rec.scope == server.name
            or (server.family is not None and rec.scope == server.family)
        ):
            matches.append(rec)
    return matches


def open_improve_count_by_server(session: Session, names: list[str]) -> dict[str, int]:
    """Count of OPEN ``improve`` MCP recommendations per server name, for the catalog card."""
    counts: dict[str, int] = {}
    if not names:
        return counts
    rows = session.scalars(
        select(Recommendation).where(
            Recommendation.target_kind == "mcp",
            Recommendation.kind == "improve",
            Recommendation.status.in_(["proposed", "accepted"]),
        )
    ).all()
    for rec in rows:
        for name in rec.targets or []:
            if name in names:
                counts[name] = counts.get(name, 0) + 1
    return counts




class SqlMcpRepository:
    """``McpRepository`` backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, *, search: str | None = None, family: str | None = None
    ) -> list[McpServerSummary]:
        stmt = _loaded_server_query()
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(McpServer.name).like(like),
                    func.lower(McpServer.description).like(like),
                )
            )
        if family:
            stmt = stmt.where(McpServer.family == family)
        servers = list(self._session.scalars(stmt.order_by(McpServer.name)).unique().all())
        improve = open_improve_count_by_server(self._session, [s.name for s in servers])
        return [_to_summary(s, improve.get(s.name, 0)) for s in servers]

    def get(self, server_id: int) -> McpServerDetail | None:
        server = (
            self._session.scalars(_loaded_server_query().where(McpServer.id == server_id))
            .unique()
            .first()
        )
        if server is None:
            return None
        return _to_detail(server, open_mcp_recommendations(self._session, server))

    def upsert(self, payload: dict, created_by_user_id: int | None) -> McpServerDetail:
        name = str(payload.get("name", "")).strip()
        tools = [dict(t) for t in (payload.get("tools") or [])]

        server = self._session.scalars(select(McpServer).where(McpServer.name == name)).first()
        if server is None:
            server = McpServer(
                name=name,
                label=payload.get("label"),
                description=payload.get("description") or "",
                transport=payload.get("transport") or "stdio",
                family=payload.get("family"),
                source_type=payload.get("source_type") or "introspected",
                created_by_user_id=created_by_user_id,
            )
            self._session.add(server)
            self._session.flush()
        else:
            # Metadata is refreshed on every submission; the tool surface is versioned below.
            server.description = payload.get("description") or server.description
            if payload.get("label"):
                server.label = payload["label"]
            if payload.get("transport"):
                server.transport = payload["transport"]
            if payload.get("family"):
                server.family = payload["family"]

        content_hash = manifest_hash(tools)
        latest = server.latest_version
        if latest is None or latest.content_hash != content_hash:
            self._session.add(
                McpServerVersion(
                    server_id=server.id,
                    version_no=(latest.version_no + 1) if latest else 1,
                    tools=tools,
                    tool_count=len(tools),
                    content_hash=content_hash,
                    created_by_user_id=created_by_user_id,
                )
            )
            self._session.flush()
            self._session.refresh(server)

        return _to_detail(server, open_mcp_recommendations(self._session, server))

    def save_assessment(
        self, server_id: int, evaluation: dict, model: str, rubric_version: str | None
    ) -> McpServerDetail | None:
        server = (
            self._session.scalars(_loaded_server_query().where(McpServer.id == server_id))
            .unique()
            .first()
        )
        if server is None:
            return None
        version = server.latest_version
        if version is None:
            return None

        scores = {key: evaluation[key] for key in _DIMENSION_KEYS if key in evaluation}
        # `overall` is server-authoritative: the weighted mean under the rubric's weights, not the
        # model's own holistic figure — so scores stay deterministic and re-rankable.
        overall = compute_overall(scores, MCP_RUBRIC_WEIGHTS)
        if overall is None:
            overall = float(evaluation.get("overall") or 0.0)

        self._session.add(
            McpEvaluation(
                server_version_id=version.id,
                model=model,
                rubric_version=rubric_version or MCP_RUBRIC_VERSION,
                scores=scores,
                overall_score=overall,
                strengths=evaluation.get("strengths") or [],
                weaknesses=evaluation.get("weaknesses") or [],
                rationale=evaluation.get("rationale") or "",
            )
        )
        self._session.flush()
        self._session.refresh(server)
        return _to_detail(server, open_mcp_recommendations(self._session, server))

    def delete(self, server_id: int) -> bool:
        server = self._session.get(McpServer, server_id)
        if server is None:
            return False
        self._session.delete(server)
        self._session.flush()
        return True

    def commit(self) -> None:
        self._session.commit()


