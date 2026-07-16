"""SkillHub FastAPI application entrypoint.

The service is a system of record + retrieval + display. It parses/embeds/stores skills and
serves them and their (Claude-Code-produced) evaluations. It does not call an LLM itself."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skillhub_core.config import get_settings
from skillhub_core.db import init_db
from skillhub_core.rubric import RUBRIC_VERSION

from .auth import require_read_access
from .routers import (
    admin,
    auth,
    categories,
    evaluations,
    oauth,
    recommendations,
    rubric,
    search,
    skills,
    stats,
    task_groups,
)
from .routers.oauth import authorization_server_metadata

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skillhub.api")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()
    logger.info("SkillHub API ready (rubric v%s).", RUBRIC_VERSION)
    yield


app = FastAPI(title="SkillHub API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth + health stay open. All data routers go through require_read_access, which is a no-op when
# SKILLHUB_PUBLIC_READS=true and requires a logged-in user otherwise (writes keep their own role gates).
_gated = [Depends(require_read_access)]
app.include_router(auth.router, prefix="/api")
# OAuth 2.1 authorization server for the remote HTTP MCP — infrastructure, never read-gated.
app.include_router(oauth.router, prefix="/api")
app.include_router(skills.router, prefix="/api", dependencies=_gated)
app.include_router(categories.router, prefix="/api", dependencies=_gated)
app.include_router(task_groups.router, prefix="/api", dependencies=_gated)
app.include_router(recommendations.router, prefix="/api", dependencies=_gated)
app.include_router(search.router, prefix="/api", dependencies=_gated)
app.include_router(evaluations.router, prefix="/api", dependencies=_gated)
app.include_router(rubric.router, prefix="/api", dependencies=_gated)
app.include_router(stats.router, prefix="/api", dependencies=_gated)
app.include_router(admin.router, prefix="/api", dependencies=_gated)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "rubric_version": RUBRIC_VERSION}


@app.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata() -> dict:
    """RFC 8414 discovery for the MCP OAuth flow. The protected-resource metadata that points here
    is served by the mcp service at /.well-known/oauth-protected-resource/mcp."""
    return authorization_server_metadata()
