"""SQLAlchemy data-access for the MCP context: the injectable ``SqlMcpRepository`` satisfying the
Protocol in ``skillhub_core.mcp.interfaces``, plus the query/persistence helpers it is built on."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..platform.models import User
from ..skills.models import Recommendation
from ..skills.rubric import compute_overall
from ..skills.schemas import RecommendationOut
from .models import McpEvaluation, McpServer, McpServerVersion
from .rubric import MCP_RUBRIC_VERSION, MCP_RUBRIC_WEIGHTS
from .schemas import (
    McpEvaluationOut,
    McpServerDetail,
    McpServerSummary,
    McpToolOut,
    McpVersionInfo,
)

_CHARS_PER_TOKEN = 4  # same rough heuristic the skills catalog uses; a size proxy, not a measurement.

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


def _user_display(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name or user.email


def _estimated_tokens(version: McpServerVersion | None) -> int | None:
    """Rough context cost of merely HAVING these tools available: every tool name, description and
    parameter schema an agent is shown, via the ~4-chars-per-token heuristic."""
    if version is None:
        return None
    chars = 0
    for tool in version.tools or []:
        chars += len(str(tool.get("name", ""))) + len(str(tool.get("description", "")))
        chars += len(json.dumps(tool.get("input_schema") or {}, ensure_ascii=False))
    return chars // _CHARS_PER_TOKEN


def _tools_out(version: McpServerVersion | None) -> list[McpToolOut]:
    out: list[McpToolOut] = []
    for tool in (version.tools if version else None) or []:
        schema = tool.get("input_schema") or {}
        properties = schema.get("properties") or {}
        out.append(
            McpToolOut(
                name=str(tool.get("name", "")),
                description=str(tool.get("description", "")),
                input_schema=schema,
                required=[str(r) for r in (schema.get("required") or [])],
                param_count=len(properties) if isinstance(properties, dict) else 0,
            )
        )
    return out


def _evaluation_out(evaluation: McpEvaluation | None) -> McpEvaluationOut | None:
    if evaluation is None:
        return None
    return McpEvaluationOut(
        model=evaluation.model,
        rubric_version=evaluation.rubric_version,
        scores=evaluation.scores or {},
        overall_score=evaluation.overall_score,
        strengths=evaluation.strengths or [],
        weaknesses=evaluation.weaknesses or [],
        rationale=evaluation.rationale or "",
        created_at=evaluation.created_at,
    )


def _latest_evaluation(server: McpServer) -> McpEvaluation | None:
    version = server.latest_version
    return version.latest_evaluation if version else None


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


def _to_summary(server: McpServer, open_improve_count: int = 0) -> McpServerSummary:
    version = server.latest_version
    evaluation = _latest_evaluation(server)
    return McpServerSummary(
        id=server.id,
        name=server.name,
        label=server.label,
        description=server.description or "",
        transport=server.transport,
        family=server.family,
        source_type=server.source_type,
        tool_count=version.tool_count if version else 0,
        overall_score=evaluation.overall_score if evaluation else None,
        rubric_version=evaluation.rubric_version if evaluation else None,
        open_improve_count=open_improve_count,
        estimated_tokens=_estimated_tokens(version),
        updated_at=server.updated_at,
    )


def _to_detail(
    server: McpServer, open_recommendations: list[Recommendation] | None = None
) -> McpServerDetail:
    version = server.latest_version
    open_recs = open_recommendations or []
    summary = _to_summary(
        server, sum(1 for r in open_recs if r.kind == "improve")
    )
    return McpServerDetail(
        **summary.model_dump(),
        tools=_tools_out(version),
        version_no=version.version_no if version else 0,
        versions=[
            McpVersionInfo(
                version_no=v.version_no,
                tool_count=v.tool_count,
                author=_user_display(v.creator),
                created_at=v.created_at,
            )
            for v in sorted(server.versions, key=lambda v: v.version_no, reverse=True)
        ],
        contributors=_contributors(server),
        latest_evaluation=_evaluation_out(_latest_evaluation(server)),
        open_recommendations=[
            RecommendationOut.model_validate(r, from_attributes=True) for r in open_recs
        ],
    )


def _contributors(server: McpServer) -> list[str]:
    """Distinct verified submitters across all versions, newest contribution first."""
    seen: dict[str, None] = {}
    for v in sorted(server.versions, key=lambda v: v.version_no, reverse=True):
        who = _user_display(v.creator)
        if who and who not in seen:
            seen[who] = None
    return list(seen.keys())


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
