"""McpServer aggregate → DTOs.

Separated from persistence so the decisions a reader sees — which version is current, what its
tool surface costs in tokens, who contributed it — sit in one place instead of trailing the
queries."""

from __future__ import annotations

import json

from ...platform.models import User
from ...skills.models import Recommendation
from ...skills.schemas import RecommendationOut
from ..models import McpServer, McpServerVersion
from ..schemas import McpServerDetail, McpServerSummary, McpToolOut, McpVersionInfo
from .evaluation import _evaluation_out, _latest_evaluation

_CHARS_PER_TOKEN = 4  # same rough heuristic the skills catalog uses; a size proxy, not a measurement.


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




