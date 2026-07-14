"""SkillHub FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skillhub_core.config import get_settings
from skillhub_core.db import init_db

from .routers import categories, evaluations, search, skills

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skillhub.api")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()
    logger.info("SkillHub API ready (LLM %s).", "enabled" if settings.llm_enabled else "disabled")
    yield


app = FastAPI(title="SkillHub API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(evaluations.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm_enabled": settings.llm_enabled, "model": settings.skillhub_llm_model}
