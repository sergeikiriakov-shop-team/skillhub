"""Map ORM objects to API DTOs."""

from __future__ import annotations

from . import adapters
from ..platform.models import User
from .models import Evaluation, Recommendation, Skill, SkillVersion
from .schemas import (
    CategoryOut,
    EvaluationOut,
    ParsedSkill,
    RecommendationOut,
    ReferenceIn,
    SimilarSkill,
    SkillDetail,
    SkillSummary,
    SkillVersionInfo,
)


def _user_display(user: User | None) -> str | None:
    """Verified identity label for a user (name, falling back to email)."""
    if user is None:
        return None
    return user.name or user.email


def _version_author(version: SkillVersion, skill: Skill) -> str | None:
    """Who authored this version: its verified uploader, else the skill's display author (legacy)."""
    return _user_display(version.creator) or skill.author


def _uploaded_by(skill: Skill) -> str | None:
    version = skill.latest_version
    return _user_display(version.creator) if version else None


def evaluation_to_out(evaluation: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        model=evaluation.model,
        rubric_version=evaluation.rubric_version,
        scores=evaluation.scores,
        overall_score=evaluation.overall_score,
        strengths=evaluation.strengths or [],
        weaknesses=evaluation.weaknesses or [],
        rationale=evaluation.rationale or "",
        created_at=evaluation.created_at,
    )


_CHARS_PER_TOKEN = 4  # standard rough heuristic (English/code mix); a size proxy, not a measurement.


def _estimated_tokens(skill: Skill) -> int | None:
    """Rough context-token cost of loading this skill: SKILL.md (raw_content, i.e. frontmatter +
    body) plus every references/* file, via the ~4-chars-per-token heuristic. None if there is no
    version to measure."""
    version = skill.latest_version
    if version is None:
        return None
    chars = len(version.raw_content or "")
    for ref in version.references or []:
        chars += len(ref.get("content", "") if isinstance(ref, dict) else "")
    return chars // _CHARS_PER_TOKEN


def _overall_score(skill: Skill) -> float | None:
    version = skill.latest_version
    if version is None:
        return None
    evaluation = version.latest_evaluation
    return evaluation.overall_score if evaluation else None


def _latest_rubric_version(skill: Skill) -> str | None:
    version = skill.latest_version
    evaluation = version.latest_evaluation if version else None
    return evaluation.rubric_version if evaluation else None


def _categories(skill: Skill) -> list[CategoryOut]:
    out = [
        CategoryOut(key=sc.category.key, label=sc.category.label, confidence=sc.confidence)
        for sc in skill.categories
        if sc.category is not None
    ]
    out.sort(key=lambda c: (c.confidence or 0), reverse=True)
    return out


def skill_to_summary(
    skill: Skill,
    best_effectiveness: tuple[float, str] | None = None,
    open_improve_count: int = 0,
) -> SkillSummary:
    version = skill.latest_version
    effectiveness, effectiveness_model = best_effectiveness or (None, None)
    return SkillSummary(
        id=skill.id,
        name=skill.name,
        author=skill.author,
        uploaded_by=_uploaded_by(skill),
        description=version.description if version else "",
        source_format=version.source_format if version else "claude_skill",
        source_type=skill.source_type,
        overall_score=_overall_score(skill),
        rubric_version=_latest_rubric_version(skill),
        categories=_categories(skill),
        task_group=skill.task_group,
        updated_at=skill.updated_at,
        best_effectiveness=effectiveness,
        best_effectiveness_model=effectiveness_model,
        open_improve_count=open_improve_count,
        estimated_tokens=_estimated_tokens(skill),
    )


def _canonical_skill_md(skill: Skill) -> str:
    """Render the full SKILL.md a developer would drop into their Claude Code skills dir."""
    version = skill.latest_version
    if version is None:
        return ""
    parsed = ParsedSkill(
        name=skill.name,
        description=version.description or "",
        body_md=version.body_md or "",
    )
    return adapters.to_claude_skill(parsed)


def _version_history(skill: Skill) -> list[SkillVersionInfo]:
    return [
        SkillVersionInfo(
            version_no=v.version_no, author=_version_author(v, skill), created_at=v.created_at
        )
        for v in sorted(skill.versions, key=lambda v: v.version_no, reverse=True)
    ]


def _contributors(skill: Skill) -> list[str]:
    """Distinct verified authors across all versions, newest contribution first."""
    seen: dict[str, None] = {}
    for v in sorted(skill.versions, key=lambda v: v.version_no, reverse=True):
        who = _user_display(v.creator)
        if who and who not in seen:
            seen[who] = None
    return list(seen.keys())


def _recommendation_to_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        kind=rec.kind,
        title=rec.title,
        rationale=rec.rationale,
        scope=rec.scope,
        targets=rec.targets or [],
        suggested_action=rec.suggested_action,
        status=rec.status,
        created_by=rec.created_by,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def skill_to_detail(
    skill: Skill,
    similar: list[tuple[Skill, float]] | None = None,
    open_recommendations: list[Recommendation] | None = None,
) -> SkillDetail:
    version = skill.latest_version
    evaluation = version.latest_evaluation if version else None
    open_recs = open_recommendations or []
    return SkillDetail(
        id=skill.id,
        name=skill.name,
        author=skill.author,
        uploaded_by=_uploaded_by(skill),
        description=version.description if version else "",
        source_format=version.source_format if version else "claude_skill",
        source_type=skill.source_type,
        overall_score=_overall_score(skill),
        rubric_version=_latest_rubric_version(skill),
        categories=_categories(skill),
        task_group=skill.task_group,
        updated_at=skill.updated_at,
        open_improve_count=sum(1 for r in open_recs if r.kind == "improve"),
        open_recommendations=[_recommendation_to_out(r) for r in open_recs],
        estimated_tokens=_estimated_tokens(skill),
        trigger_text=version.trigger_text if version else None,
        body_md=version.body_md if version else "",
        skill_md=_canonical_skill_md(skill),
        references=[ReferenceIn(**r) for r in (version.references or [])] if version else [],
        section_headings=version.section_headings if version else [],
        version_no=version.version_no if version else 0,
        contributors=_contributors(skill),
        versions=_version_history(skill),
        latest_evaluation=evaluation_to_out(evaluation) if evaluation else None,
        similar=[
            SimilarSkill(
                id=other.id,
                name=other.name,
                author=other.author,
                similarity=round(sim, 4),
                overall_score=_overall_score(other),
            )
            for other, sim in (similar or [])
        ],
    )
