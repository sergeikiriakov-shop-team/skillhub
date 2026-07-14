"""Airflow DAG: re-evaluate and re-categorize every skill in the registry.

Design: Airflow only orchestrates. The heavy work (LLM evaluation, embeddings) lives in the
SkillHub API, which the DAG drives over HTTP. This keeps Airflow's dependency set independent
from ``skillhub_core`` and makes the pipeline callable the same way from anywhere.

Trigger manually from the Airflow UI, or set a schedule below once you want it periodic.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime

from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

API_URL = os.environ.get("SKILLHUB_API_URL", "http://api:8000").rstrip("/")


def _get(path: str) -> object:
    req = urllib.request.Request(f"{API_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{API_URL}{path}", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


@dag(
    dag_id="batch_reevaluate",
    description="Re-evaluate and re-categorize all SkillHub skills via the API.",
    schedule=None,  # manual; e.g. "@weekly" to run periodically
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["skillhub"],
)
def batch_reevaluate():
    @task
    def list_skill_ids() -> list[int]:
        skills = _get("/api/health")  # sanity check the API is reachable
        logger.info("API health: %s", skills)
        data = _get("/api/skills")
        ids = [s["id"] for s in data]
        logger.info("Found %d skill(s) to re-evaluate", len(ids))
        return ids

    @task
    def reevaluate(skill_id: int) -> dict:
        status, body = _post(f"/api/skills/{skill_id}/reevaluate")
        logger.info("skill %s -> %s %s", skill_id, status, body)
        return {"skill_id": skill_id, "status": status}

    ids = list_skill_ids()
    # Dynamic task mapping: one mapped task instance per skill.
    reevaluate.expand(skill_id=ids)


batch_reevaluate()
