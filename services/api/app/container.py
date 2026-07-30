"""dependency-injector container — the composition root for the API.

Providers construct the object graph; the per-request SQLAlchemy Session is NOT a provider (the
library has no request scope) — FastAPI owns it via ``get_session`` and it is threaded into the
Factory repositories at call time in ``deps.py``. Services depend on repository Protocols, so this
is the one place the concrete SQLAlchemy implementations are wired in."""

from __future__ import annotations

from dependency_injector import containers, providers

from skillhub_core.platform.repositories import SqlUserAdminRepository
from skillhub_core.platform.services import UserAdminService
from skillhub_core.reviews.repositories import SqlReviewRepository
from skillhub_core.reviews.services import ReviewService
from skillhub_core.skills.repositories import (
    SqlCatalogRepository,
    SqlEvaluationRepository,
    SqlNotebookRepository,
    SqlRecommendationRepository,
    SqlRubricRepository,
    SqlSkillRepository,
)
from skillhub_core.skills.services import (
    CatalogService,
    EvaluationService,
    IngestService,
    NotebookService,
    RecommendationService,
    RubricService,
    SkillService,
)


class Container(containers.DeclarativeContainer):
    # Repositories: Factory — the request Session is supplied at call time (see deps.py).
    rubric_repository = providers.Factory(SqlRubricRepository)
    notebook_repository = providers.Factory(SqlNotebookRepository)
    skill_repository = providers.Factory(SqlSkillRepository)
    evaluation_repository = providers.Factory(SqlEvaluationRepository)
    recommendation_repository = providers.Factory(SqlRecommendationRepository)
    catalog_repository = providers.Factory(SqlCatalogRepository)
    review_repository = providers.Factory(SqlReviewRepository)
    user_admin_repository = providers.Factory(SqlUserAdminRepository)

    # Services: Factory — their repositories are supplied at call time.
    rubric_service = providers.Factory(RubricService)
    notebook_service = providers.Factory(NotebookService)
    skill_service = providers.Factory(SkillService)
    ingest_service = providers.Factory(IngestService)
    evaluation_service = providers.Factory(EvaluationService)
    recommendation_service = providers.Factory(RecommendationService)
    catalog_service = providers.Factory(CatalogService)
    review_service = providers.Factory(ReviewService)
    user_admin_service = providers.Factory(UserAdminService)
