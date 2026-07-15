"""SkillHub MCP server — a thin stdio wrapper over the SkillHub REST API.

Each developer runs this from their own Claude Code (via `docker run -i`) with their own
token, so authorization is enforced by the API. The server holds no business logic; it just
forwards calls and surfaces auth/validation errors.

Env:
  SKILLHUB_URL    base URL of the API (default http://host.docker.internal:8000)
  SKILLHUB_TOKEN  bearer token; required for uploads/evaluations, optional for reads
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("SKILLHUB_URL", "http://host.docker.internal:8000").rstrip("/")
TOKEN = os.environ.get("SKILLHUB_TOKEN", "")

mcp = FastMCP("skillhub")


def _client() -> httpx.Client:
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    return httpx.Client(base_url=BASE, headers=headers, timeout=30)


def _call(method: str, path: str, *, params: dict | None = None, json: Any | None = None) -> Any:
    """Perform a request; return parsed JSON, or a structured error dict (never raises)."""
    try:
        with _client() as c:
            r = c.request(method, path, params=params, json=json)
        if r.status_code >= 400:
            detail: Any
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            return {"error": r.status_code, "detail": detail}
        if r.status_code == 204 or not r.content:
            return {"ok": True}
        return r.json()
    except httpx.HTTPError as exc:
        return {"error": "connection", "detail": f"{exc} (SKILLHUB_URL={BASE})"}


@mcp.tool()
def list_unevaluated() -> Any:
    """List skills with no evaluation yet — the work queue to score."""
    return _call("GET", "/api/skills", params={"evaluated": "false"})


@mcp.tool()
def list_skills(search: str | None = None, category: str | None = None) -> Any:
    """List skills, optionally filtered by a name/author substring or a category key."""
    params = {k: v for k, v in {"search": search, "category": category}.items() if v}
    return _call("GET", "/api/skills", params=params or None)


@mcp.tool()
def get_skill(skill_id: int) -> Any:
    """Get one skill with its content, latest evaluation and similar skills. To INSTALL the skill
    into the user's Claude Code, use `skill_md` (the ready-to-write SKILL.md) and `references[]`
    ({path, content}) and write them to `<skills-dir>/<name>/` with your own Write tool — this
    MCP server runs in a container and cannot touch the user's disk."""
    return _call("GET", f"/api/skills/{skill_id}")


@mcp.tool()
def search(query: str) -> Any:
    """Semantic search over skills (by meaning)."""
    return _call("GET", "/api/search", params={"q": query})


@mcp.tool()
def get_rubric() -> Any:
    """Fetch the full evaluation + curation strategy (one shared algorithm for every developer):
    `instructions`, `dimensions`, `weights`, `calibration` anchors, the `evaluation_schema`, the
    `categories` taxonomy, `categorization_rules` (broad category + narrow task_group),
    `selection_strategy` (how to pick the best in a group) and the synthesis spec
    (`synthesis_strategy`, `synthesis_algorithm`, `synthesis_prompt`). Fetch this before scoring,
    categorizing, selecting a best-of-group, or synthesizing an ideal skill."""
    return _call("GET", "/api/rubric")


@mcp.tool()
def list_task_groups(status: str | None = None) -> Any:
    """List the existing narrow task-groups (the specific-job layer below the broad categories),
    with each group's skill count and average score. Call this BEFORE assigning a `task_group` on
    an assessment and REUSE a matching slug, so skills that do the same job cluster together
    instead of fragmenting across near-duplicate slugs."""
    return _call("GET", "/api/task-groups")


@mcp.tool()
def get_stats() -> Any:
    """Aggregate dashboard stats (totals, evaluated count, average score, per-category)."""
    return _call("GET", "/api/stats")


@mcp.tool()
def upload_skill(
    content: str,
    author: str | None = None,
    source_format: str = "claude_skill",
    references: list[dict] | None = None,
) -> Any:
    """Import a skill. `content` is the raw SKILL.md text (with YAML frontmatter). `references`
    is a list of {path, content}. `source_format`: claude_skill|cursor_mdc|codex_skill|generic_md.
    Requires a contributor+ token."""
    body = {
        "content": content,
        "author": author,
        "source_format": source_format,
        "references": references or [],
    }
    return _call("POST", "/api/skills", json=body)


@mcp.tool()
def submit_assessment(
    skill_id: int,
    evaluation: dict,
    categorization: dict | None = None,
    model: str = "claude-code",
) -> Any:
    """Submit a completed assessment. `evaluation` must match the rubric schema
    (clarity, trigger_quality, completeness, reusability, safety, structure as 0-10 ints, plus
    overall 0-10, strengths[], weaknesses[], rationale). `categorization` is optional
    {primary_category, categories:[{key,confidence}], task_group (a narrow specific-job slug —
    reuse an existing one from list_task_groups), tags[], summary}. Requires an evaluator token."""
    body: dict[str, Any] = {"evaluation": evaluation, "model": model}
    if categorization is not None:
        body["categorization"] = categorization
    return _call("POST", f"/api/skills/{skill_id}/assessment", json=body)


@mcp.tool()
def list_recommendations(status: str | None = None) -> Any:
    """List curator recommendations (proposed catalog changes: synthesize/split/merge/dedup/delete).
    Optionally filter by status: proposed|accepted|done|dismissed."""
    return _call("GET", "/api/recommendations", params={"status": status} if status else None)


@mcp.tool()
def add_recommendation(
    kind: str,
    title: str,
    rationale: str = "",
    scope: str | None = None,
    targets: list[str] | None = None,
    suggested_action: str = "",
) -> Any:
    """Propose a catalog change so it is stored and shown on the dashboard for a developer to run
    later. `kind`: synthesize|split|merge|dedup|delete|other. `scope`: a category/task_group/skill.
    `suggested_action`: a runnable instruction. Requires a contributor+ token."""
    body = {
        "kind": kind,
        "title": title,
        "rationale": rationale,
        "scope": scope,
        "targets": targets or [],
        "suggested_action": suggested_action,
    }
    return _call("POST", "/api/recommendations", json=body)


@mcp.tool()
def set_recommendation_status(rec_id: int, status: str) -> Any:
    """Update a recommendation's status: proposed|accepted|done|dismissed. Requires a contributor+ token."""
    return _call("POST", f"/api/recommendations/{rec_id}/status", json={"status": status})


if __name__ == "__main__":
    mcp.run()
