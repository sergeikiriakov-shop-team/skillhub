"""Semantic search over skills (falls back to text search if embeddings are unavailable)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from skillhub_core.skills import embeddings, repository, serializers
from skillhub_core.platform.db import get_session
from skillhub_core.skills.schemas import SkillSummary

router = APIRouter(tags=["search"])


class SearchHit(BaseModel):
    skill: SkillSummary
    similarity: float | None = None


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[SearchHit]:
    vector = embeddings.embed(q)
    if vector is not None:
        hits = repository.semantic_search(session, vector, limit=limit)
        return [
            SearchHit(skill=serializers.skill_to_summary(s), similarity=round(sim, 4))
            for s, sim in hits
        ]
    # Fallback: plain name/author match.
    skills = repository.list_skills(session, search=q)[:limit]
    return [SearchHit(skill=serializers.skill_to_summary(s)) for s in skills]
