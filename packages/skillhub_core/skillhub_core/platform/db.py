"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

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
    _seed_rubric_weights()
    _seed_skill_notebooks()
    _bootstrap_admin()


def _apply_column_migrations() -> None:
    """Add columns introduced after a table's first creation. ``create_all`` creates missing
    tables but never ALTERs an existing one, so a column added to an already-provisioned table
    (e.g. ``skills.task_group``) must be applied here. Idempotent via ``ADD COLUMN IF NOT EXISTS``."""
    statements = [
        "ALTER TABLE skills ADD COLUMN IF NOT EXISTS task_group VARCHAR(80)",
        "CREATE INDEX IF NOT EXISTS ix_skills_task_group ON skills (task_group)",
        # OAuth rework: provider-agnostic identity columns on the pre-existing users table + drop
        # the legacy single-token NOT NULL. Uniqueness lives in named indexes (partial: NULLs ok).
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(320)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_sub VARCHAR(255)",
        "ALTER TABLE users ALTER COLUMN token_hash DROP NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)",
        # Migrate any earlier google_sub column into the generic pair, then retire it. Guarded so
        # it is a no-op on a fresh DB that never had google_sub.
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name='users' AND column_name='google_sub') THEN "
        "UPDATE users SET auth_provider='google', provider_sub=google_sub "
        "WHERE provider_sub IS NULL AND google_sub IS NOT NULL; END IF; END $$",
        "DROP INDEX IF EXISTS uq_users_google_sub",
        "ALTER TABLE users DROP COLUMN IF EXISTS google_sub",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_provider_identity "
        "ON users (auth_provider, provider_sub)",
        # Task Review context: reviewer/lead capability flag on the shared users table.
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_reviewer BOOLEAN NOT NULL DEFAULT false",
        # Carry any legacy per-user tokens over to auth_tokens so existing MCP tokens keep working.
        "INSERT INTO auth_tokens (user_id, token_hash, kind, created_at) "
        "SELECT id, token_hash, 'device', now() FROM users WHERE token_hash IS NOT NULL "
        "ON CONFLICT (token_hash) DO NOTHING",
        # Team registry: verified authorship + one canonical skill per name. Existing data is
        # clean (all names unique), so switching the identity to name alone is safe.
        "ALTER TABLE skills ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE skill_versions ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE skills DROP CONSTRAINT IF EXISTS uq_skill_identity",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_skills_name ON skills (name)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def _bootstrap_admin() -> None:
    from . import auth

    with SessionLocal() as session:
        auth.ensure_bootstrap_admin(session, _settings.skillhub_admin_token)


def _seed_categories() -> None:
    from ..skills.models import Category

    with SessionLocal() as session:
        existing = {c.key for c in session.query(Category).all()}
        for cat in DEFAULT_CATEGORIES:
            if cat["key"] not in existing:
                session.add(Category(**cat))
        session.commit()


def _seed_rubric_weights() -> None:
    """Seed the admin-managed dimension weights from the rubric defaults (missing dimensions only),
    then align stored ``overall`` scores with the weighted-mean definition so the server-computed
    score is authoritative from first boot. Idempotent."""
    from ..skills import repository
    from ..skills.models import RubricWeight
    from ..skills.rubric import RUBRIC_WEIGHTS

    with SessionLocal() as session:
        existing = {r.dimension for r in session.query(RubricWeight).all()}
        for dimension, weight in RUBRIC_WEIGHTS.items():
            if dimension not in existing:
                session.add(RubricWeight(dimension=dimension, weight=float(weight)))
        session.commit()
        if repository.recompute_overall_scores(session):
            session.commit()


def _seed_skill_notebooks() -> None:
    """Attach the recorded green-loop sandbox trial to the ``green-loop`` skill, so the Trials view
    has a real example immediately, and keep that seed-owned demo in sync with the shipped fixture
    on each boot. Best-effort + idempotent, and it never clobbers a notebook a real user submitted
    (``created_by_user_id`` set) nor breaks boot."""
    import json
    from pathlib import Path

    from ..skills import repository
    from ..skills.models import Skill, SkillNotebook

    seed_dir = Path(__file__).resolve().parents[1] / "skills" / "seed_data"
    nb_file = seed_dir / "green_loop_trial.ipynb"
    sum_file = seed_dir / "green_loop_trial.json"
    try:
        if not nb_file.exists():
            return
        notebook = json.loads(nb_file.read_text(encoding="utf-8"))
        summary = json.loads(sum_file.read_text(encoding="utf-8")) if sum_file.exists() else {}
        with SessionLocal() as session:
            skill = session.query(Skill).filter(Skill.name == "green-loop").first()
            if skill is None:
                return
            existing = session.get(SkillNotebook, skill.id)
            if existing is not None:
                # Leave a user-submitted notebook alone; only refresh the seed-owned demo, and only
                # when the shipped fixture actually changed.
                if existing.created_by_user_id is not None or existing.notebook == notebook:
                    return
            row = repository.upsert_skill_notebook(
                session,
                skill_id=skill.id,
                scenario=str(summary.get("scenario") or "green_loop_understand"),
                task_group=summary.get("task_group") or "green-loop",
                notebook=notebook,
                summary=summary,
                created_by_user_id=None,
            )
            if row is not None:
                session.commit()
    except Exception as exc:  # never let demo seeding break boot
        print(f"skill-notebook seed skipped: {exc}")


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
