"""Pydantic schemas: internal parse result, LLM structured outputs and API DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Internal parse result
# ---------------------------------------------------------------------------


class Reference(BaseModel):
    path: str
    content: str


class ParsedSkill(BaseModel):
    """Normalized, Claude-Code-shaped representation produced by the parser."""

    name: str
    description: str = ""
    trigger_text: str | None = None
    body_md: str = ""
    references: list[Reference] = Field(default_factory=list)
    section_headings: list[str] = Field(default_factory=list)
    frontmatter: dict = Field(default_factory=dict)
    source_format: str = "claude_skill"
    raw_content: str = ""

    def searchable_text(self) -> str:
        """Text fed to the embedding model and, in trimmed form, to the LLM."""
        parts = [self.name, self.description, self.body_md]
        parts += [r.content for r in self.references]
        return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# LLM structured outputs
# ---------------------------------------------------------------------------


class EvaluationResult(BaseModel):
    """Quality assessment of a single skill. All dimension scores are 0-10 integers."""

    clarity: int = Field(ge=0, le=10, description="Is the writing clear and unambiguous?")
    trigger_quality: int = Field(
        ge=0, le=10, description="How precisely does it state WHEN the skill should trigger?"
    )
    completeness: int = Field(
        ge=0, le=10, description="Does it cover the workflow with no critical gaps?"
    )
    reusability: int = Field(
        ge=0, le=10, description="Is it generic/parameterized rather than one-off?"
    )
    safety: int = Field(
        ge=0, le=10, description="Does it warn about destructive actions and edge cases?"
    )
    structure: int = Field(
        ge=0, le=10, description="Good headings, examples, progressive disclosure via references?"
    )
    overall: float = Field(ge=0, le=10, description="Weighted overall quality, 0-10.")
    strengths: list[str] = Field(default_factory=list, description="Concrete strengths.")
    weaknesses: list[str] = Field(default_factory=list, description="Concrete, actionable gaps.")
    rationale: str = Field(default="", description="2-4 sentence justification of the scores.")


class CategoryAssignment(BaseModel):
    key: str = Field(description="Category key from the provided taxonomy.")
    confidence: float = Field(ge=0, le=1, description="Confidence 0-1.")


class CategorizationResult(BaseModel):
    primary_category: str = Field(description="Single best-fit category key from the taxonomy.")
    categories: list[CategoryAssignment] = Field(
        default_factory=list, description="All applicable categories with confidences."
    )
    task_group: str | None = Field(
        default=None,
        description="Narrow slug for the skill's SPECIFIC job (e.g. 'single-task-driver', "
        "'sql-data-read'), finer than the broad category. Skills doing the same job MUST share "
        "the same slug so competing variants cluster together. Reuse an existing slug when one "
        "fits (see GET /api/task-groups); only invent a new one for a genuinely new job.",
    )
    tags: list[str] = Field(default_factory=list, description="Free-form lowercase tags.")
    summary: str = Field(default="", description="One-sentence summary of what the skill does.")


# ---------------------------------------------------------------------------
# API DTOs
# ---------------------------------------------------------------------------


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


class AssessmentIn(BaseModel):
    """A completed assessment submitted by the evaluator (Claude Code)."""

    evaluation: EvaluationResult
    categorization: CategorizationResult | None = None
    model: str = Field(default="claude-code", description="What produced the assessment.")
    rubric_version: str | None = Field(
        default=None, description="Defaults to the server's current rubric version."
    )


class RubricOut(BaseModel):
    """Everything the evaluator needs to score, categorize and rank a skill consistently.

    Served to every developer's Claude Code (GET /api/rubric) and rendered on the dashboard's
    Methodology page, so the strategy lives in one place instead of in each reviewer's head."""

    rubric_version: str
    instructions: str
    dimensions: list[dict]
    evaluation_schema: dict
    categories: list[dict]
    weights: dict = Field(default_factory=dict)
    calibration: list[dict] = Field(default_factory=list)
    categorization_rules: str = ""
    selection_strategy: str = ""
    synthesis_strategy: str = ""
    synthesis_algorithm: list[dict] = Field(default_factory=list)
    synthesis_prompt: str = ""


# --- Users / admin ---


class UserCreate(BaseModel):
    name: str
    role: str = "contributor"


class RoleUpdate(BaseModel):
    role: str


class UserOut(BaseModel):
    id: int
    name: str
    role: str
    created_at: datetime


class UserCreated(UserOut):
    token: str = Field(description="Shown once — store it now; only its hash is kept.")


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
    author: str | None
    description: str
    source_format: str
    overall_score: float | None
    categories: list[CategoryOut]
    task_group: str | None = None
    updated_at: datetime


class SkillDetail(SkillSummary):
    trigger_text: str | None
    body_md: str
    references: list[ReferenceIn]
    section_headings: list[str]
    version_no: int
    latest_evaluation: EvaluationOut | None
    similar: list["SimilarSkill"] = Field(default_factory=list)


class SimilarSkill(BaseModel):
    id: int
    name: str
    author: str | None
    similarity: float
    overall_score: float | None
