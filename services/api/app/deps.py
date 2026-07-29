"""FastAPI dependency providers bridging the DI container to the per-request Session.

The container builds the object graph; FastAPI owns the request-scoped Session (``get_session``)
and we thread it into the container's Factory repositories here. Routers depend on the returned
services, never on the repository module or the Session directly."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from skillhub_core.platform.db import get_session
from skillhub_core.skills.services import NotebookService, RubricService

from .container import Container

container = Container()


def get_rubric_service(session: Session = Depends(get_session)) -> RubricService:
    return container.rubric_service(rubric=container.rubric_repository(session=session))


def get_notebook_service(session: Session = Depends(get_session)) -> NotebookService:
    return container.notebook_service(notebooks=container.notebook_repository(session=session))
