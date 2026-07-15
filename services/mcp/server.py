"""SkillHub MCP server — a thin stdio wrapper over the SkillHub REST API.

Reads are public and need no token. For writes (upload, submit assessment, recommendations) the
server obtains a SkillHub token via the OAuth 2.0 Device Authorization Grant: it asks the API for
a code, surfaces a verification URL + user code to you, you approve it in the browser (signing in
with Google), and the server caches the minted token to a mounted volume so later sessions reuse
it. A `SKILLHUB_TOKEN` env var still overrides everything (back-compat / CI).

Env:
  SKILLHUB_URL         base URL of the API (default http://host.docker.internal:8000)
  SKILLHUB_TOKEN       optional explicit bearer token (skips the device flow)
  SKILLHUB_TOKEN_FILE  where to cache the device-flow token (default /data/token; mount a volume)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("SKILLHUB_URL", "http://host.docker.internal:8000").rstrip("/")
_ENV_TOKEN = os.environ.get("SKILLHUB_TOKEN", "").strip()
TOKEN_FILE = Path(os.environ.get("SKILLHUB_TOKEN_FILE", "/data/token"))
# One write-tool call waits up to this long for you to approve before returning "approve & retry".
_DEVICE_MAX_WAIT = 60

mcp = FastMCP("skillhub")

# Process-lifetime state (the server stays alive for the whole Claude Code session).
_state: dict[str, Any] = {"token": None, "pending": None}


def _client(token: str | None = None) -> httpx.Client:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=BASE, headers=headers, timeout=30)


def _call(
    method: str, path: str, *, params: dict | None = None, json: Any | None = None, token: str | None = None
) -> Any:
    """Perform a request; return parsed JSON, or a structured error dict (never raises)."""
    try:
        with _client(token) as c:
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


# --- token acquisition (device flow) -----------------------------------------------------------


def _token_valid(token: str) -> bool:
    if not token:
        return False
    try:
        with _client(token) as c:
            r = c.get("/api/auth/me")
        return r.status_code == 200 and bool(r.json().get("authenticated"))
    except (httpx.HTTPError, ValueError):
        return False


def _cached_token() -> str | None:
    if _state["token"]:
        return _state["token"]
    if _ENV_TOKEN:
        _state["token"] = _ENV_TOKEN
        return _ENV_TOKEN
    try:
        if TOKEN_FILE.exists():
            t = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if t:
                _state["token"] = t
                return t
    except OSError:
        pass
    return None


def _save_token(token: str) -> None:
    _state["token"] = token
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def _poll_device(device_code: str) -> tuple[str | None, str]:
    """Poll the device-token endpoint once. Returns (access_token|None, error_code)."""
    try:
        with _client() as c:
            r = c.post("/api/auth/device/token", json={"device_code": device_code})
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None, "connection"
    if r.status_code == 200 and data.get("access_token"):
        return data["access_token"], ""
    return None, str(data.get("error", "unknown"))


def _acquire_token(max_wait: int = _DEVICE_MAX_WAIT) -> tuple[str | None, str]:
    """Return (token, "") if authorized, else (None, human_message) describing how to approve."""
    token = _cached_token()
    if token and _token_valid(token):
        _state["token"] = token
        return token, ""
    _state["token"] = None  # stale cached token

    pending = _state.get("pending")
    now = time.monotonic()
    if not pending or now > pending["hard_deadline"]:
        resp = _call("POST", "/api/auth/device/code", json={"client_label": "Claude Code MCP"})
        if not isinstance(resp, dict) or "device_code" not in resp:
            return None, f"Could not start device authorization: {resp}"
        pending = {
            "device_code": resp["device_code"],
            "user_code": resp["user_code"],
            "url": resp.get("verification_uri_complete") or resp.get("verification_uri"),
            "interval": int(resp.get("interval", 5)),
            "hard_deadline": now + int(resp.get("expires_in", 600)),
        }
        _state["pending"] = pending

    deadline = min(now + max_wait, pending["hard_deadline"])
    interval = pending["interval"]
    while time.monotonic() < deadline:
        access_token, err = _poll_device(pending["device_code"])
        if access_token:
            _save_token(access_token)
            _state["pending"] = None
            return access_token, ""
        if err == "slow_down":
            interval += 5
        elif err in ("expired_token", "access_denied"):
            _state["pending"] = None
            break
        time.sleep(interval)

    msg = (
        f"Authorization required. Open {pending['url']} and approve code "
        f"{pending['user_code']} (sign in with Google), then re-run the command."
    )
    return None, msg


def _authed_call(method: str, path: str, **kwargs: Any) -> Any:
    token, message = _acquire_token()
    if token is None:
        return {"action_required": message}
    return _call(method, path, token=token, **kwargs)


# --- read tools (public) -----------------------------------------------------------------------


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
def list_recommendations(status: str | None = None) -> Any:
    """List curator recommendations (proposed catalog changes: synthesize/split/merge/dedup/delete).
    Optionally filter by status: proposed|accepted|done|dismissed."""
    return _call("GET", "/api/recommendations", params={"status": status} if status else None)


# --- auth ---------------------------------------------------------------------------------------


@mcp.tool()
def authenticate() -> Any:
    """Authorize this MCP for writes via the device flow. Returns a verification URL + code to open
    in a browser (sign in with Google, approve), and waits briefly for approval. Safe to call again
    to resume; the token is cached so you normally only do this once per machine."""
    token, message = _acquire_token()
    if token is not None:
        return {"ok": True, "detail": "Authorized. Write tools are ready."}
    return {"action_required": message}


# --- write tools (require a token; trigger the device flow lazily) ------------------------------


@mcp.tool()
def upload_skill(
    content: str,
    author: str | None = None,
    source_format: str = "claude_skill",
    references: list[dict] | None = None,
) -> Any:
    """Import a skill. `content` is the raw SKILL.md text (with YAML frontmatter). `references`
    is a list of {path, content}. `source_format`: claude_skill|cursor_mdc|codex_skill|generic_md.
    Requires a contributor+ role (run `authenticate` first if needed)."""
    body = {
        "content": content,
        "author": author,
        "source_format": source_format,
        "references": references or [],
    }
    return _authed_call("POST", "/api/skills", json=body)


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
    reuse an existing one from list_task_groups), tags[], summary}. Requires an evaluator role."""
    body: dict[str, Any] = {"evaluation": evaluation, "model": model}
    if categorization is not None:
        body["categorization"] = categorization
    return _authed_call("POST", f"/api/skills/{skill_id}/assessment", json=body)


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
    `suggested_action`: a runnable instruction. Requires a contributor+ role."""
    body = {
        "kind": kind,
        "title": title,
        "rationale": rationale,
        "scope": scope,
        "targets": targets or [],
        "suggested_action": suggested_action,
    }
    return _authed_call("POST", "/api/recommendations", json=body)


@mcp.tool()
def set_recommendation_status(rec_id: int, status: str) -> Any:
    """Update a recommendation's status: proposed|accepted|done|dismissed. Requires a contributor+ role."""
    return _authed_call("POST", f"/api/recommendations/{rec_id}/status", json={"status": status})


if __name__ == "__main__":
    mcp.run()
