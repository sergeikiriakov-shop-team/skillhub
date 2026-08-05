"""FastAPI dependency providers bridging the DI container to the per-request Session.

The container builds the object graph; FastAPI owns the request-scoped Session (``get_session``)
and we thread it into the container's Factory repositories here. Routers depend on the returned
services, never on the repository module or the Session directly."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from skillhub_core.mcp.services import McpRubricService, McpService
from skillhub_core.platform.db import get_session
from skillhub_core.platform.services import UserAdminService
from skillhub_core.reviews.services import ReviewService
from skillhub_core.skills.services import (
    CatalogService,
    EvaluationService,
    IngestService,
    NotebookService,
    RecommendationService,
    RubricService,
    SkillService,
)

from .container import Container

container = Container()


def get_rubric_service(session: Session = Depends(get_session)) -> RubricService:
    return container.rubric_service(rubric=container.rubric_repository(session=session))


def get_notebook_service(session: Session = Depends(get_session)) -> NotebookService:
    return container.notebook_service(notebooks=container.notebook_repository(session=session))


def get_skill_service(session: Session = Depends(get_session)) -> SkillService:
    return container.skill_service(skills=container.skill_repository(session=session))


def get_ingest_service(session: Session = Depends(get_session)) -> IngestService:
    return container.ingest_service(skills=container.skill_repository(session=session))


def get_evaluation_service(session: Session = Depends(get_session)) -> EvaluationService:
    return container.evaluation_service(evaluations=container.evaluation_repository(session=session))


def get_recommendation_service(session: Session = Depends(get_session)) -> RecommendationService:
    return container.recommendation_service(
        recommendations=container.recommendation_repository(session=session)
    )


def get_catalog_service(session: Session = Depends(get_session)) -> CatalogService:
    return container.catalog_service(catalog=container.catalog_repository(session=session))


def get_review_service(session: Session = Depends(get_session)) -> ReviewService:
    return container.review_service(reviews=container.review_repository(session=session))


def get_mcp_service(session: Session = Depends(get_session)) -> McpService:
    return container.mcp_service(servers=container.mcp_repository(session=session))


def get_mcp_rubric_service() -> McpRubricService:
    return container.mcp_rubric_service()


def get_user_admin_service(session: Session = Depends(get_session)) -> UserAdminService:
    return container.user_admin_service(users=container.user_admin_repository(session=session))
