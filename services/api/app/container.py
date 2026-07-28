"""dependency-injector container — the composition root for the API.

Providers construct the object graph; the per-request SQLAlchemy Session is NOT a provider (the
library has no request scope) — FastAPI owns it via ``get_session`` and it is threaded into the
Factory repositories at call time in ``deps.py``. Services depend on repository Protocols, so this
is the one place the concrete SQLAlchemy implementations are wired in."""

from __future__ import annotations

from dependency_injector import containers, providers

from skillhub_core.skills.repositories import SqlRubricRepository
from skillhub_core.skills.services import RubricService


class Container(containers.DeclarativeContainer):
    # Repositories: Factory — the request Session is supplied at call time (see deps.py).
    rubric_repository = providers.Factory(SqlRubricRepository)

    # Services: Factory — their repositories are supplied at call time.
    rubric_service = providers.Factory(RubricService)
