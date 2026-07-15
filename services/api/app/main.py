"""SkillHub FastAPI application entrypoint.

The service is a system of record + retrieval + display. It parses/embeds/stores skills and
serves them and their (Claude-Code-produced) evaluations. It does not call an LLM itself."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skillhub_core.config import get_settings
from skillhub_core.db import init_db
from skillhub_core.rubric import RUBRIC_VERSION

from .routers import (
    admin,
    categories,
    evaluations,
    recommendations,
    rubric,
    search,
    skills,
    stats,
    task_groups,
)

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

app.include_router(skills.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(task_groups.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(evaluations.router, prefix="/api")
app.include_router(rubric.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "rubric_version": RUBRIC_VERSION}
