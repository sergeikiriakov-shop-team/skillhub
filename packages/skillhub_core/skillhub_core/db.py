"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base, Category

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


# Default taxonomy seeded on first boot. Categories can be extended later without migration.
DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"key": "data-access", "label": "Data access", "description": "DB schema, SQL, logs, reporting."},
    {"key": "code-writing", "label": "Code writing", "description": "Backend/frontend code authoring & style."},
    {"key": "code-review", "label": "Code review", "description": "Reviewing diffs and pull requests."},
    {"key": "qa", "label": "QA / verification", "description": "Manual and automated verification of changes."},
    {"key": "orchestration", "label": "Orchestration", "description": "Multi-step task pipelines and batching."},
    {"key": "docs", "label": "Documentation", "description": "Writing docs, notes and reports."},
    {"key": "other", "label": "Other", "description": "Anything that does not fit the above."},
]


def init_db() -> None:
    """Create the pgvector extension, all tables and seed default categories (idempotent)."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    _apply_column_migrations()
    _seed_categories()
    _bootstrap_admin()


def _apply_column_migrations() -> None:
    """Add columns introduced after a table's first creation. ``create_all`` creates missing
    tables but never ALTERs an existing one, so a column added to an already-provisioned table
    (e.g. ``skills.task_group``) must be applied here. Idempotent via ``ADD COLUMN IF NOT EXISTS``."""
    statements = [
        "ALTER TABLE skills ADD COLUMN IF NOT EXISTS task_group VARCHAR(80)",
        "CREATE INDEX IF NOT EXISTS ix_skills_task_group ON skills (task_group)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def _bootstrap_admin() -> None:
    from . import auth

    with SessionLocal() as session:
        auth.ensure_bootstrap_admin(session, _settings.skillhub_admin_token)


def _seed_categories() -> None:
    with SessionLocal() as session:
        existing = {c.key for c in session.query(Category).all()}
        for cat in DEFAULT_CATEGORIES:
            if cat["key"] not in existing:
                session.add(Category(**cat))
        session.commit()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context manager."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closed after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
