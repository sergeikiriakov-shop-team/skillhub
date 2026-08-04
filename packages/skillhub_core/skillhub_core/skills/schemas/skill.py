"""Skill API DTOs — the read/write shapes served over /api/skills (and search/stats)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .recommendation import RecommendationOut


class ReferenceIn(BaseModel):
    path: str
    content: str


class SkillCreate(BaseModel):
    """Payload for uploading/importing a skill. The service parses, embeds and stores it;
    evaluation is done separately by Claude Code (POST /api/skills/{id}/assessment)."""

    content: str = Field(description="Raw SKILL.md text, including YAML frontmatter.")
    author: str | None = None
    references: list[ReferenceIn] = Field(default_factory=list)
    source_format: str = "claude_skill"


class StatsOut(BaseModel):
    total: int
    evaluated: int
    avg_overall: float | None
    by_category: list[dict]
    top: list[dict]


class CategoryOut(BaseModel):
    key: str
    label: str
    confidence: float | None = None


class EvaluationOut(BaseModel):
    model: str
    rubric_version: str
    scores: dict
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    rationale: str
    created_at: datetime


class SkillSummary(BaseModel):
    id: int
    name: str
    author: str | None  # display author (verified uploader of the first version, or import label)
    uploaded_by: str | None = None  # verified identity of the latest version's uploader
    description: str
    source_format: str
    source_type: str = "upload"
    overall_score: float | None
    rubric_version: str | None = None  # version of the latest evaluation; None if unscored
    categories: list[CategoryOut]
    task_group: str | None = None
    updated_at: datetime
    # Empirical headline from the sandbox-trial matrix (0..1) — the best (skill, model)
    # effectiveness recorded across all trials, i.e. what the skill actually does under its best
    # model, judge-panel graded and gated by the objective scorecard. None if never trialed; the
    # static rubric `overall_score` above is a structural/doc score and is not the same signal.
    best_effectiveness: float | None = None
    best_effectiveness_model: str | None = None
    # Open (proposed/accepted) `improve`-kind curator recommendations naming this skill — a
    # concrete, actionable suggestion, distinct from the score/effectiveness signals above.
    open_improve_count: int = 0
    # Rough context-token cost of LOADING this skill (SKILL.md + all references/*), estimated via
    # the standard ~4-chars-per-token heuristic — not a measured trial cost, just a size proxy so
    # a much heavier skill doesn't look free next to a lean one. None if the skill has no content.
    estimated_tokens: int | None = None


class SkillVersionInfo(BaseModel):
    """One entry in a skill's version history."""

    version_no: int
    author: str | None
    created_at: datetime


class SkillDetail(SkillSummary):
    trigger_text: str | None
    body_md: str
    skill_md: str = Field(
        default="",
        description="The full canonical SKILL.md (name+description frontmatter + body), ready to "
        "write to <skills-dir>/<name>/SKILL.md when installing the skill into Claude Code.",
    )
    references: list[ReferenceIn]
    section_headings: list[str]
    version_no: int
    contributors: list[str] = Field(default_factory=list)  # distinct verified authors across versions
    versions: list[SkillVersionInfo] = Field(default_factory=list)
    latest_evaluation: EvaluationOut | None
    similar: list["SimilarSkill"] = Field(default_factory=list)
    similar_warning: dict | None = None  # set only on upload when a similar skill exists
    # Every OPEN (proposed/accepted) curator recommendation applying to this skill (named as a
    # target, or its scope matches the skill's name / task_group / one of its categories) —
    # computed server-side, in the SAME request as the skill itself, so the page doesn't depend on
    # a second, independently-failable /recommendations fetch to show them.
    open_recommendations: list[RecommendationOut] = Field(default_factory=list)


class SimilarSkill(BaseModel):
    id: int
    name: str
    author: str | None
    similarity: float
    overall_score: float | None
