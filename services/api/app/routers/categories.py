"""Taxonomy listing with per-category skill counts."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from skillhub_core.platform.db import get_session
from skillhub_core.skills.models import Category, SkillCategory

router = APIRouter(tags=["categories"])


class CategoryInfo(BaseModel):
    key: str
    label: str
    description: str
    skill_count: int


@router.get("/categories", response_model=list[CategoryInfo])
def list_categories(session: Session = Depends(get_session)) -> list[CategoryInfo]:
    counts = dict(
        session.execute(
            select(SkillCategory.category_id, func.count(func.distinct(SkillCategory.skill_id)))
            .group_by(SkillCategory.category_id)
        ).all()
    )
    categories = session.scalars(select(Category).order_by(Category.id)).all()
    return [
        CategoryInfo(
            key=c.key,
            label=c.label,
            description=c.description,
            skill_count=int(counts.get(c.id, 0)),
        )
        for c in categories
    ]
