"""SkillHub MCP server — a thin wrapper over the SkillHub REST API, in two transports.

- ``http`` (SKILLHUB_MCP_TRANSPORT=http): a remote streamable-HTTP server hosted on the SkillHub
  box. Auth is standard MCP OAuth — SkillHub is the authorization server (browser login via
  GitHub); this process is the *resource server*. It validates the incoming Bearer against
  ``/api/auth/me`` and forwards that same token to the REST API. No local Docker, no cached token.
- ``stdio`` (default): the legacy local wrapper Claude Code spawns via ``docker run -i``. Reads are
  public; writes obtain a token via the OAuth 2.0 Device Authorization Grant, cached to a volume.
  A ``SKILLHUB_TOKEN`` env var still overrides everything (back-compat / CI).

Env:
  SKILLHUB_MCP_TRANSPORT  stdio (default) | http
  SKILLHUB_URL            base URL of the REST API (default http://host.docker.internal:8000)
  SKILLHUB_PUBLIC_URL     public origin of SkillHub (http mode: OAuth issuer + resource base)
  MCP_HOST / MCP_PORT     bind address for http mode (default 0.0.0.0:9000)
  SKILLHUB_TOKEN          optional explicit bearer token (stdio: skips the device flow)
  SKILLHUB_TOKEN_FILE     where to cache the device-flow token (stdio; default /data/token)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

TRANSPORT = os.environ.get("SKILLHUB_MCP_TRANSPORT", "stdio").strip().lower()
BASE = os.environ.get("SKILLHUB_URL", "http://host.docker.internal:8000").rstrip("/")
PUBLIC_URL = os.environ.get("SKILLHUB_PUBLIC_URL", BASE).rstrip("/")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "9000"))
_ENV_TOKEN = os.environ.get("SKILLHUB_TOKEN", "").strip()
TOKEN_FILE = Path(os.environ.get("SKILLHUB_TOKEN_FILE", "/data/token"))
# One write-tool call waits up to this long for you to approve before returning "approve & retry".
_DEVICE_MAX_WAIT = 60

if TRANSPORT == "http":
    # Resource-server mode: validate the Bearer minted by SkillHub's OAuth AS, and let the SDK serve
    # the protected-resource metadata + emit 401/WWW-Authenticate so Claude Code runs the browser flow.
    from mcp.server.auth.middleware.auth_context import get_access_token
    from mcp.server.auth.provider import AccessToken, TokenVerifier
    from mcp.server.auth.settings import AuthSettings

    class _SkillHubVerifier(TokenVerifier):
        async def verify_token(self, token: str) -> AccessToken | None:
            try:
                async with httpx.AsyncClient(base_url=BASE, timeout=15) as c:
                    r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                data = r.json() if r.status_code == 200 else {}
            except (httpx.HTTPError, ValueError):
                return None
            if not data.get("authenticated"):
                return None
            return AccessToken(
                token=token, client_id="skillhub-mcp", scopes=[], subject=str(data.get("id"))
            )

    mcp = FastMCP(
        "skillhub",
        host=MCP_HOST,
        port=MCP_PORT,
        token_verifier=_SkillHubVerifier(),
        auth=AuthSettings(
            issuer_url=PUBLIC_URL,
            resource_server_url=f"{PUBLIC_URL}/mcp",
            required_scopes=[],
        ),
    )
else:
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
        f"{pending['user_code']} (sign in with GitHub), then re-run the command."
    )
    return None, msg


def _http_token() -> str | None:
    """http mode: the Bearer the client presented on this MCP request (already verified by the SDK).
    We forward the same token to the REST API, which enforces read-gating and roles."""
    tok = get_access_token()
    return tok.token if tok else None


def _authed_call(method: str, path: str, **kwargs: Any) -> Any:
    if TRANSPORT == "http":
        return _call(method, path, token=_http_token(), **kwargs)
    token, message = _acquire_token()
    if token is None:
        return {"action_required": message}
    return _call(method, path, token=token, **kwargs)


def _read_call(method: str, path: str, **kwargs: Any) -> Any:
    """Read from the API. In http mode the per-request OAuth token is forwarded. In stdio mode it
    tries any cached token and, if the instance gates reads (401), runs the device flow and retries."""
    if TRANSPORT == "http":
        return _call(method, path, token=_http_token(), **kwargs)
    r = _call(method, path, token=_cached_token(), **kwargs)
    if isinstance(r, dict) and r.get("error") == 401:
        token, message = _acquire_token()
        if token is None:
            return {"action_required": message}
        r = _call(method, path, token=token, **kwargs)
    return r


# --- read tools (public unless the instance gates reads) ---------------------------------------


@mcp.tool()
def list_unevaluated() -> Any:
    """List skills with no evaluation yet — the work queue to score."""
    return _read_call("GET", "/api/skills", params={"evaluated": "false"})


@mcp.tool()
def list_skills(search: str | None = None, category: str | None = None) -> Any:
    """List skills, optionally filtered by a name/author substring or a category key."""
    params = {k: v for k, v in {"search": search, "category": category}.items() if v}
    return _read_call("GET", "/api/skills", params=params or None)


@mcp.tool()
def get_skill(skill_id: int) -> Any:
    """Get one skill with its content, latest evaluation and similar skills. To INSTALL the skill
    into the user's Claude Code, use `skill_md` (the ready-to-write SKILL.md) and `references[]`
    ({path, content}) and write them to `<skills-dir>/<name>/` with your own Write tool — this
    MCP server runs in a container and cannot touch the user's disk."""
    return _read_call("GET", f"/api/skills/{skill_id}")


@mcp.tool()
def search(query: str) -> Any:
    """Semantic search over skills (by meaning)."""
    return _read_call("GET", "/api/search", params={"q": query})


@mcp.tool()
def get_rubric() -> Any:
    """Fetch the full evaluation + curation strategy (one shared algorithm for every developer):
    `instructions`, `dimensions`, `weights`, `calibration` anchors, the `evaluation_schema`, the
    `categories` taxonomy, `categorization_rules` (broad category + narrow task_group),
    `selection_strategy` (how to pick the best in a group) and the synthesis spec
    (`synthesis_strategy`, `synthesis_algorithm`, `synthesis_prompt`). Fetch this before scoring,
    categorizing, selecting a best-of-group, or synthesizing an ideal skill."""
    return _read_call("GET", "/api/rubric")


@mcp.tool()
def list_task_groups(status: str | None = None) -> Any:
    """List the existing narrow task-groups (the specific-job layer below the broad categories),
    with each group's skill count and average score. Call this BEFORE assigning a `task_group` on
    an assessment and REUSE a matching slug, so skills that do the same job cluster together
    instead of fragmenting across near-duplicate slugs."""
    return _read_call("GET", "/api/task-groups")


@mcp.tool()
def get_stats() -> Any:
    """Aggregate dashboard stats (totals, evaluated count, average score, per-category)."""
    return _read_call("GET", "/api/stats")


@mcp.tool()
def list_recommendations(status: str | None = None) -> Any:
    """List curator recommendations (proposed catalog changes: synthesize/split/improve/merge/dedup/delete).
    Optionally filter by status: proposed|accepted|done|dismissed."""
    return _read_call("GET", "/api/recommendations", params={"status": status} if status else None)


@mcp.tool()
def get_skill_notebook(skill_id: int) -> Any:
    """Get the skill's ONE sandbox-trial notebook (the run record from the `evals/` harness): the
    `notebook` (nbformat cells), the `summary` scorecard, and `stale` (true once the skill changed
    since the trial ran). Returns `{error: 404}` if no trial has been recorded. Call this before a
    sandbox run to decide reuse vs. regenerate: if a fresh (non-stale) notebook exists and the
    developer did not ask to regenerate, reuse it instead of running again."""
    return _read_call("GET", f"/api/skills/{skill_id}/notebook")


# --- auth ---------------------------------------------------------------------------------------


@mcp.tool()
def authenticate() -> Any:
    """Check/obtain authorization for write tools. In http mode auth is handled by your MCP client's
    OAuth (browser sign-in) before any tool runs — this just reports status. In stdio mode it runs
    the device flow: returns a verification URL + code to open in a browser (sign in with GitHub,
    approve), caching the token so you normally do this only once per machine."""
    if TRANSPORT == "http":
        if _http_token():
            return {"ok": True, "detail": "Authorized via OAuth. Write tools are ready."}
        return {"action_required": "Not authorized — your MCP client should run the OAuth sign-in."}
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
    Requires a contributor+ role (run `authenticate` first if needed).

    De-duplication: skills are keyed by name — re-uploading an existing name adds a new VERSION of
    that one skill (not a copy), attributed to you. Uploading content IDENTICAL to an existing skill
    under a DIFFERENT name is rejected with HTTP 409 (`error: 409`, `detail.existing_name`) — update
    that skill instead. A merely-similar (not identical) skill is accepted; the response then carries
    a `similar_warning` {skill_id, name, similarity} so you can double-check it isn't a duplicate."""
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
    later. `kind`: synthesize|split|improve|merge|dedup|delete|other (`improve` = upgrade/restructure
    ONE skill in place — move detail into references/, add examples, tighten the trigger, progressive
    disclosure — without splitting it). `scope`: a category/task_group/skill. `suggested_action`: a
    runnable instruction. Requires a contributor+ role."""
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


@mcp.tool()
def submit_skill_notebook(
    skill_id: int,
    notebook: dict,
    summary: dict | None = None,
    scenario: str = "",
    task_group: str | None = None,
) -> Any:
    """Store (create or REGENERATE) the skill's one sandbox-trial notebook — the run record the
    `evals/` harness emits (`trial.ipynb` = `notebook`, `trial.json` = `summary`). There is one
    notebook per skill; submitting replaces it. The tested skill-version snapshot (for the stale
    flag) is taken server-side. Requires a contributor+ role. Run this right after a sandbox trial
    so the result shows on the skill's page in the dashboard."""
    body = {
        "notebook": notebook,
        "summary": summary or {},
        "scenario": scenario,
        "task_group": task_group,
    }
    return _authed_call("PUT", f"/api/skills/{skill_id}/notebook", json=body)


# --- Task Review context (peer-review handoff developer <-> lead) ------------------------------


@mcp.tool()
def submit_for_review(
    task_ref: str,
    title: str = "",
    branch: str | None = None,
    commit_shas: list[str] | None = None,
    summary: str = "",
    files: list[str] | None = None,
    verified_notes: str = "",
) -> Any:
    """Submit a deploy-ready Prologistics task for review by the lead. Pass a POINTER to the work —
    the code stays in git; the reviewer fetches the branch and reviews the real diff. `task_ref` is
    the issue_logs id/link; `commit_shas`/`files` describe the change; `summary` is what changed and
    why; `verified_notes` is what you checked (php -l / harness / QA) and what you did not. The single
    lead is auto-assigned. Returns the created review (with its id and status)."""
    body = {
        "task_ref": task_ref, "title": title, "branch": branch,
        "commit_shas": commit_shas or [], "summary": summary,
        "files": files or [], "verified_notes": verified_notes,
    }
    return _authed_call("POST", "/api/reviews", json=body)


@mcp.tool()
def list_review_queue() -> Any:
    """Lead's inbox: reviews awaiting review (status `submitted`). For each, run `get_review`, fetch
    the branch and review the diff, then post `submit_review_result`."""
    return _read_call("GET", "/api/reviews", params={"status": "submitted"})


@mcp.tool()
def list_my_reviews(status: str | None = None) -> Any:
    """Reviews you authored. Filter by `status` (submitted|changes_requested|approved|done). The ones
    needing your action are `changes_requested` (fix + `resubmit_review`) and `approved` (`ack_review`)."""
    params = {"mine": "true"}
    if status:
        params["status"] = status
    return _read_call("GET", "/api/reviews", params=params)


@mcp.tool()
def get_review(review_id: int) -> Any:
    """Get one review with its full thread (submit -> verdict -> resubmit -> ...), pointer fields
    (task_ref, branch, commit_shas, files), summary and the author's verification notes."""
    return _read_call("GET", f"/api/reviews/{review_id}")


@mcp.tool()
def submit_review_result(review_id: int, verdict: str, comments: str = "") -> Any:
    """Lead posts a verdict on a review. `verdict`: `approve` | `changes_requested` (comments required
    for changes_requested). Requires the reviewer (lead) role. Only a review awaiting review can be
    decided."""
    return _authed_call(
        "POST", f"/api/reviews/{review_id}/result", json={"verdict": verdict, "comments": comments}
    )


@mcp.tool()
def resubmit_review(review_id: int, commit_shas: list[str] | None = None, note: str = "") -> Any:
    """Author sends a task back for another round after addressing the review comments. Pass the new
    `commit_shas` and a `note` on what changed. Moves the review back into the lead's queue."""
    return _authed_call(
        "POST", f"/api/reviews/{review_id}/resubmit",
        json={"commit_shas": commit_shas or [], "note": note},
    )


@mcp.tool()
def ack_review(review_id: int) -> Any:
    """Author acknowledges the outcome; an approved review is closed (status `done`)."""
    return _authed_call("POST", f"/api/reviews/{review_id}/ack", json={})


if __name__ == "__main__":
    if TRANSPORT == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
