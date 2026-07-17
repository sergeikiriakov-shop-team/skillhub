"""Internal parse result — the normalized, Claude-Code-shaped skill produced by the parser."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
