"""Map ORM objects to API DTOs."""

from __future__ import annotations

from . import adapters
from .models import Evaluation, Skill
from .schemas import (
    CategoryOut,
    EvaluationOut,
    ParsedSkill,
    ReferenceIn,
    SimilarSkill,
    SkillDetail,
    SkillSummary,
)


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


def skill_to_summary(skill: Skill) -> SkillSummary:
    version = skill.latest_version
    return SkillSummary(
        id=skill.id,
        name=skill.name,
        author=skill.author,
        description=version.description if version else "",
        source_format=version.source_format if version else "claude_skill",
        source_type=skill.source_type,
        overall_score=_overall_score(skill),
        rubric_version=_latest_rubric_version(skill),
        categories=_categories(skill),
        task_group=skill.task_group,
        updated_at=skill.updated_at,
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


def skill_to_detail(skill: Skill, similar: list[tuple[Skill, float]] | None = None) -> SkillDetail:
    version = skill.latest_version
    evaluation = version.latest_evaluation if version else None
    return SkillDetail(
        id=skill.id,
        name=skill.name,
        author=skill.author,
        description=version.description if version else "",
        source_format=version.source_format if version else "claude_skill",
        source_type=skill.source_type,
        overall_score=_overall_score(skill),
        rubric_version=_latest_rubric_version(skill),
        categories=_categories(skill),
        task_group=skill.task_group,
        updated_at=skill.updated_at,
        trigger_text=version.trigger_text if version else None,
        body_md=version.body_md if version else "",
        skill_md=_canonical_skill_md(skill),
        references=[ReferenceIn(**r) for r in (version.references or [])] if version else [],
        section_headings=version.section_headings if version else [],
        version_no=version.version_no if version else 0,
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
