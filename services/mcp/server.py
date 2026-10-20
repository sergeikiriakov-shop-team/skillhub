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
from typing import Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from pydantic import BaseModel, ConfigDict, Field

# Reject unknown arguments instead of silently swallowing them. FastMCP derives every tool's
# argument model from this shared base, so setting `extra="forbid"` here does two things at once:
# each advertised inputSchema gains `additionalProperties: false` (a client can no longer send a
# misspelled or invented parameter), and Pydantic enforces the same server-side. Must run BEFORE
# the first @mcp.tool() decoration, because the schema is generated at decoration time.
ArgModelBase.model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

# --- closed vocabularies, mirrored as Literal so they reach the client as real JSON-Schema enums.
#
# These are DUPLICATED, not imported: this container installs only `mcp` + `httpx` (see Dockerfile),
# deliberately excluding skillhub_core so the image stays small (no torch). The source of truth is
# `skillhub_core.skills.constants` (REC_KINDS / REC_STATUSES / REC_TARGET_KINDS / FORMAT_*),
# `skillhub_core.mcp.models.mcp_server` (TRANSPORTS), `skillhub_core.reviews.models.task_review`
# (TASK_REVIEW_STATUSES) and `skillhub_core.platform.models.base` (ROLES) — keep them in step when a
# vocabulary changes there.
#
# Only stable domain vocabularies belong here. Evaluation DIMENSIONS deliberately do NOT: they are
# strategy, served live from /api/rubric so one algorithm governs every developer, and embedding
# them would mean a rubric change needs an MCP redeploy.
RecKind = Literal["synthesize", "split", "improve", "merge", "dedup", "delete", "other"]
RecStatus = Literal["proposed", "accepted", "done", "dismissed"]
RecTargetKind = Literal["skill", "mcp"]
SourceFormat = Literal[
    "claude_skill", "cursor_mdc", "codex_skill", "copilot_instructions", "generic_md"
]
McpTransport = Literal["stdio", "http"]
TaskReviewStatus = Literal["changes_needed", "passed", "approved"]
SelfReviewLane = Literal["default", "backend", "frontend"]
SelfReviewVerdict = Literal["pass", "changes_needed"]
FindingSeverity = Literal["blocker", "major", "minor", "nit"]
UserRole = Literal["viewer", "contributor", "evaluator", "admin"]

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
def list_skills(
    search: Annotated[
        str | None,
        Field(
            description="Literal SUBSTRING match on name/author — not semantic. For "
            "meaning-based lookup ('something that checks a PR') use `search` instead."
        ),
    ] = None,
    category: Annotated[
        str | None,
        Field(description="Exact category key from `get_rubric`'s `categories`, e.g. 'data-access'."),
    ] = None,
) -> Any:
    """List skills, filtered by a literal name/author substring or an exact category key. Returns
    the whole catalog when unfiltered — there is no limit parameter, so prefer a filter."""
    params = {k: v for k, v in {"search": search, "category": category}.items() if v}
    return _read_call("GET", "/api/skills", params=params or None)


@mcp.tool()
def get_skill(
    skill_id: Annotated[int, Field(description="Numeric skill id, e.g. from `list_skills` or `search`.")],
    include_references: Annotated[
        bool,
        Field(
            description="Include the reference FILES' contents. Off by default because they are "
            "the heaviest part of the payload; `references_count` tells you how many exist either "
            "way. Set true when INSTALLING the skill, since you need their contents to write them."
        ),
    ] = False,
) -> Any:
    """Get one skill: its `skill_md`, body, latest evaluation, open recommendations and similar
    skills. Lean by default — reference files are omitted unless you ask for them.

    To INSTALL into the user's Claude Code, call with `include_references=true`, then write
    `skill_md` and each `references[]` {path, content} to `<skills-dir>/<name>/` with your own
    Write tool — this MCP server runs in a container and cannot touch the user's disk."""
    return _read_call(
        "GET", f"/api/skills/{skill_id}", params={"include_references": str(include_references).lower()}
    )


@mcp.tool()
def search(
    query: Annotated[
        str,
        Field(
            description="What the skill should DO, in plain words (e.g. 'review a frontend PR') "
            "— matched by meaning, so it need not appear in the text."
        ),
    ],
) -> Any:
    """Find skills by MEANING (vector search over descriptions). Use this when you know the job but
    not the name; use `list_skills(search=...)` when you know part of the literal name or author."""
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
def list_task_groups() -> Any:
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
def list_recommendations(
    status: Annotated[
        RecStatus | None, Field(description="Lifecycle filter; omit for every status.")
    ] = None,
    target_kind: Annotated[
        RecTargetKind | None,
        Field(description="`skill` = about a SKILL.md, `mcp` = about a server's tool surface."),
    ] = None,
) -> Any:
    """List curator recommendations — proposed catalog changes. Unbounded: returns every match."""
    params = {k: v for k, v in {"status": status, "target_kind": target_kind}.items() if v}
    return _read_call("GET", "/api/recommendations", params=params or None)


@mcp.tool()
def list_mcp_servers(
    search: Annotated[
        str | None, Field(description="Substring match on the server name or description.")
    ] = None,
    family: Annotated[
        str | None,
        Field(
            description="Exact family slug grouping sibling entries that expose the same surface "
            "against different environments, e.g. 'beliani-db-schema' for the prod/dev/heap trio."
        ),
    ] = None,
) -> Any:
    """List catalogued MCP SERVERS (a separate catalog from skills): each with its tool count,
    rubric score, open-improve count and the estimated token cost of merely having its tools
    available."""
    params = {k: v for k, v in {"search": search, "family": family}.items() if v}
    return _read_call("GET", "/api/mcp", params=params or None)


@mcp.tool()
def get_mcp_server(
    server_id: Annotated[int, Field(description="Numeric server id from `list_mcp_servers`.")],
) -> Any:
    """Get one catalogued MCP server: its full introspected tool surface (each tool's name,
    description, parameter schema and required params), its latest evaluation, its version history
    (where schema drift shows up), and every open recommendation about it. Heavy: returns the
    target's entire surface inline."""
    return _read_call("GET", f"/api/mcp/{server_id}")


@mcp.tool()
def get_mcp_rubric() -> Any:
    """Fetch the MCP evaluation strategy — the shared algorithm for scoring an MCP server's TOOL
    SURFACE (distinct from the skills rubric): `instructions`, `dimensions` (schema_precision,
    tool_clarity, discoverability, result_shape, safety, token_economy), `weights`, `calibration`
    anchors, the `evaluation_schema`, the `recommendation_strategy` and the
    `introspection_protocol`. Fetch this before introspecting or scoring an MCP server."""
    return _read_call("GET", "/api/mcp/rubric")


@mcp.tool()
def upload_mcp_server(
    name: Annotated[
        str,
        Field(
            description="The server ENTRY name as connected, e.g. 'beliani-db-schema-prod'. "
            "Re-submitting an existing name adds a version rather than a duplicate."
        ),
    ],
    tools: Annotated[
        list[dict],
        Field(
            description="One entry per tool: {name, description, input_schema}, each copied "
            "VERBATIM from the live server — not from a README or from memory."
        ),
    ],
    description: Annotated[
        str, Field(description="What the server is for, in one or two sentences.")
    ] = "",
    label: Annotated[str | None, Field(description="Human-friendly display name.")] = None,
    transport: Annotated[
        McpTransport, Field(description="How the client reaches it: a local subprocess or remote HTTP.")
    ] = "stdio",
    family: Annotated[
        str | None,
        Field(
            description="Slug grouping sibling entries that expose the same surface against "
            "different environments, e.g. 'beliani-db-schema' for the prod/dev/heap trio."
        ),
    ] = None,
) -> Any:
    """Catalogue an MCP server by INTROSPECTING one you are already connected to.

    SkillHub never connects out to a third-party MCP server and holds no credentials for one — YOU
    are the introspection mechanism. Enumerate the tool surface you can actually see for this
    server and pass it as `tools`: one entry per tool, each `{name, description, input_schema}`,
    where `name` is the exact callable name, `description` is the tool's own description verbatim,
    and `input_schema` is its parameter JSON Schema verbatim.

    Read all of this from the LIVE connected server — never from a skill's `references/tools.md`,
    a README, or memory. The entire point of this catalog is to expose where documentation and the
    real schema have drifted apart, and transcribing the docs would launder exactly the discrepancy
    you are trying to find. Do not summarize, retype or "tidy" a schema, and do not fill in a
    missing description with what you assume the tool probably does: an empty description or an
    untyped parameter is a real finding the rubric scores.

    Re-submitting an existing name adds a new VERSION, so drift is visible in the history; an
    unchanged manifest is a no-op. Requires a contributor+ role; unauthorized in stdio mode
    returns `{action_required: <how to approve>}`."""
    body = {
        "name": name,
        "description": description,
        "label": label,
        "transport": transport,
        "family": family,
        "tools": tools,
    }
    return _authed_call("POST", "/api/mcp", json=body)


@mcp.tool()
def submit_mcp_assessment(
    server_id: Annotated[int, Field(description="Numeric server id from `list_mcp_servers`.")],
    evaluation: Annotated[
        dict,
        Field(
            description="Must match `evaluation_schema` from `get_mcp_rubric` — six 0-10 ints "
            "(schema_precision, tool_clarity, discoverability, result_shape, safety, "
            "token_economy) plus overall, strengths[], weaknesses[], rationale. Not constrained "
            "here on purpose: the dimensions are strategy served live by the rubric endpoint, so "
            "fetch it rather than trusting this text."
        ),
    ],
    model: Annotated[
        str, Field(description="Exact id of the model that produced this assessment, e.g. 'claude-opus-5'.")
    ] = "claude-code",
) -> Any:
    """Submit a completed assessment of an MCP server's tool surface. Fetch `get_mcp_rubric` first
    and score against ITS dimensions — these are not the skills dimensions. Score only what the
    manifest actually contains. Requires a contributor+ role; unauthorized in stdio mode returns
    `{action_required: <how to approve>}`."""
    return _authed_call(
        "POST", f"/api/mcp/{server_id}/assessment", json={"evaluation": evaluation, "model": model}
    )


@mcp.tool()
def get_skill_notebook(
    skill_id: Annotated[int, Field(description="Numeric skill id.")],
    model: Annotated[
        str | None,
        Field(description="Which model's trial to fetch; omit for the best-scoring one."),
    ] = None,
    include_cells: Annotated[
        bool,
        Field(
            description="Include the raw nbformat cells — the full transcript, by far the largest "
            "field. Off by default: the scorecard alone answers reuse-vs-regenerate. Set true only "
            "to actually READ what the run did."
        ),
    ] = False,
) -> Any:
    """Get a sandbox-trial notebook for the skill (the run record from the `evals/` harness).
    Lean by default: returns the scorecard — `summary`, `effectiveness` (0..1), `result_grade`,
    `objective_rate`, `dimensions`, `panel`, executing `model` and `stale` (true once the skill
    changed since the trial ran) — without the transcript. Returns `{error: 404}` if none recorded.

    Call before a sandbox run to decide reuse vs. regenerate for YOUR model: if a fresh
    (non-stale) trial exists for your model and the developer did not ask to regenerate, reuse it."""
    params: dict[str, str] = {"include_cells": str(include_cells).lower()}
    if model:
        params["model"] = model
    return _read_call("GET", f"/api/skills/{skill_id}/notebook", params=params)


@mcp.tool()
def get_skill_fit(
    skill_id: Annotated[int, Field(description="Numeric skill id.")],
) -> Any:
    """Get the skill's effectiveness-by-MODEL matrix: `best_model` and, per model trialed, its
    `effectiveness` (0..1), `scenario` and `stale`. Models with no trial are absent — those are the
    gaps to fill (e.g. "not yet trialed under claude-opus-5"). Use to see which model a skill suits
    best and which models still need a trial run."""
    return _read_call("GET", f"/api/skills/{skill_id}/notebooks")


# --- auth ---------------------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Check/obtain authorization for write tools, and report WHICH SkillHub instance this "
        f"server is bound to — every read and write below goes to {PUBLIC_URL}, a catalog shared "
        "with the whole team, not a personal scratch copy. In http mode auth is handled by your "
        "MCP client's OAuth (browser sign-in) before any tool runs, so this just reports status. "
        "In stdio mode it runs the device flow: returns a verification URL + code to open in a "
        "browser (sign in with GitHub, approve), caching the token so you normally do this only "
        "once per machine."
    )
)
def authenticate() -> Any:
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
    content: Annotated[
        str, Field(description="The raw SKILL.md text, including its YAML frontmatter.")
    ],
    author: Annotated[
        str | None, Field(description="Display author; defaults to your verified identity.")
    ] = None,
    source_format: Annotated[
        SourceFormat, Field(description="Which client's format `content` is written in.")
    ] = "claude_skill",
    references: Annotated[
        list[dict] | None,
        Field(description="Companion files as {path, content}, e.g. references/tools.md."),
    ] = None,
) -> Any:
    """Import a skill into the shared team catalog. Requires a contributor+ role (run
    `authenticate` first if needed); unauthorized in stdio mode returns
    `{action_required: <how to approve>}` rather than raising.

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
    skill_id: Annotated[int, Field(description="Numeric skill id being scored.")],
    evaluation: Annotated[
        dict,
        Field(
            description="Must match `evaluation_schema` from `get_rubric` — six 0-10 ints "
            "(clarity, trigger_quality, completeness, reusability, safety, structure) plus "
            "overall, strengths[], weaknesses[], rationale. Not constrained here on purpose: the "
            "dimensions are strategy served live by the rubric endpoint, so fetch it rather than "
            "trusting this text."
        ),
    ],
    categorization: Annotated[
        dict | None,
        Field(
            description="Optional {primary_category, categories:[{key,confidence}], task_group, "
            "tags[], summary}. Reuse an existing task_group slug from `list_task_groups`."
        ),
    ] = None,
    model: Annotated[
        str, Field(description="Exact id of the model that produced this assessment.")
    ] = "claude-code",
) -> Any:
    """Submit a completed skill assessment. Requires an evaluator role; unauthorized in stdio mode
    returns `{action_required: <how to approve>}`."""
    body: dict[str, Any] = {"evaluation": evaluation, "model": model}
    if categorization is not None:
        body["categorization"] = categorization
    return _authed_call("POST", f"/api/skills/{skill_id}/assessment", json=body)


@mcp.tool()
def add_recommendation(
    kind: Annotated[
        RecKind,
        Field(
            description="`improve` = upgrade ONE entry in place (examples, references/, tighter "
            "trigger) without splitting it; the rest regroup or retire entries."
        ),
    ],
    title: Annotated[str, Field(description="One line naming the change, not the symptom.")],
    rationale: Annotated[
        str,
        Field(description="The EVIDENCE: what in the manifest/trial/text shows this is real."),
    ] = "",
    scope: Annotated[
        str | None, Field(description="What it applies to: a category, task_group, skill or server.")
    ] = None,
    targets: Annotated[
        list[str] | None, Field(description="Exact names of the skills or servers involved.")
    ] = None,
    suggested_action: Annotated[
        str, Field(description="A runnable instruction another developer's Claude Code can execute.")
    ] = "",
    anchor: Annotated[
        str | None,
        Field(
            description="For an `improve` about ONE spot, the EXACT text it attaches to: a heading "
            "from `get_skill`'s `section_headings` (e.g. 'Workflow'), or a tool name from "
            "`get_mcp_server`'s `tools` (e.g. 'find_columns'). It then renders inline at that spot "
            "instead of only in a side list. Omit for anything about the whole entry."
        ),
    ] = None,
    target_kind: Annotated[
        RecTargetKind,
        Field(description="Which catalog this is about; cross-catalog findings are fine on either side."),
    ] = "skill",
) -> Any:
    """Propose a catalog change so it is stored and shown on the dashboard for a developer to run
    later. Requires a contributor+ role; unauthorized in stdio mode returns
    `{action_required: <how to approve>}`."""
    body = {
        "target_kind": target_kind,
        "kind": kind,
        "title": title,
        "rationale": rationale,
        "scope": scope,
        "targets": targets or [],
        "suggested_action": suggested_action,
        "anchor": anchor,
    }
    return _authed_call("POST", "/api/recommendations", json=body)


@mcp.tool()
def set_recommendation_status(
    rec_id: Annotated[int, Field(description="Numeric recommendation id from `list_recommendations`.")],
    status: Annotated[
        RecStatus,
        Field(description="`accepted` = will do, `done` = carried out, `dismissed` = won't do."),
    ],
) -> Any:
    """Update a recommendation's status. Shared state: a recommendation may have been filed by
    someone else, and restatusing it (e.g. `dismissed`) is visible to the whole team and is not
    versioned — check `list_recommendations` first if you did not file it. Requires a contributor+
    role; unauthorized in stdio mode returns `{action_required: <how to approve>}`."""
    return _authed_call("POST", f"/api/recommendations/{rec_id}/status", json={"status": status})


@mcp.tool()
def submit_skill_notebook(
    skill_id: Annotated[int, Field(description="Numeric skill the trial was run against.")],
    notebook: Annotated[
        dict, Field(description="The nbformat object the harness emits as `trial.ipynb`.")
    ],
    model: Annotated[
        str,
        Field(
            description="The EXECUTING model that produced this trial — your own exact id, e.g. "
            "'claude-opus-5'. Trials are keyed per (skill, model), so this decides which one is "
            "REPLACED; other models' trials are untouched."
        ),
    ],
    summary: Annotated[
        dict | None,
        Field(
            description="The harness's `trial.json`: objective `entries` plus the judge panel's "
            "`result_grade`, `dimensions` and `panel`."
        ),
    ] = None,
    scenario: Annotated[str, Field(description="Scenario name the trial ran, e.g. 'green_loop_understand'.")] = "",
    task_group: Annotated[str | None, Field(description="Task-group slug this trial belongs to.")] = None,
) -> Any:
    """Store (create or REGENERATE) a sandbox-trial notebook for the skill. The tested
    skill-version snapshot (for the stale flag) is taken server-side. Requires a contributor+ role;
    unauthorized in stdio mode returns `{action_required: <how to approve>}`. Run right after a
    sandbox trial so the result shows in the skill's effectiveness-by-model matrix."""
    body = {
        "model": model,
        "notebook": notebook,
        "summary": summary or {},
        "scenario": scenario,
        "task_group": task_group,
    }
    return _authed_call("PUT", f"/api/skills/{skill_id}/notebook", json=body)


# --- The review board (one row per task; the lead approves or sends it back) ----------------------


@mcp.tool()
def list_review_board(
    status: Annotated[
        TaskReviewStatus | None,
        Field(description="Filter by state; omit for the whole board."),
    ] = None,
    mine: Annotated[bool, Field(description="Only tasks you self-reviewed.")] = False,
) -> Any:
    """The review board: one row per task, not per run. `status='passed'` is the LEAD'S QUEUE —
    tasks whose latest self-review came back clean and which are waiting for a sign-off.
    `status='changes_needed'` is what the author still has to fix (either the run found something,
    or the lead sent it back with a comment)."""
    params: dict[str, Any] = {}
    if status:
        params["status"] = status
    if mine:
        params["mine"] = "true"
    return _read_call("GET", "/api/task-reviews", params=params)


@mcp.tool()
def get_task_review(
    task_review_id: Annotated[int, Field(description="Numeric id from `list_review_board`.")],
) -> Any:
    """One task with its whole run history and the latest run's findings and fixes — what the lead
    reads before approving. `open_finding_count` is how many findings nobody has answered yet."""
    return _read_call("GET", f"/api/task-reviews/{task_review_id}")


@mcp.tool()
def approve_task_review(
    task_review_id: Annotated[int, Field(description="Numeric id from `list_review_board`.")],
) -> Any:
    """Sign a task off as the lead — the final step of the flow. Read `get_task_review` first: this
    approves what the self-review found, so approving without looking is the one way to make the
    board meaningless. Rejected (409) when the task has no run at all, is already approved, or —
    if the policy requires a clean run — has not passed. Requires the reviewer role; unauthorized
    in stdio mode returns `{action_required: <how to approve>}`."""
    return _authed_call("POST", f"/api/task-reviews/{task_review_id}/approve", json={})


@mcp.tool()
def return_task_review(
    task_review_id: Annotated[int, Field(description="Numeric id from `list_review_board`.")],
    comment: Annotated[
        str, Field(description="What must change. Required — a bare rejection costs a round trip.")
    ],
) -> Any:
    """Send a task back to its author instead of approving it — for when the run came back clean
    but you disagree, or you want something changed anyway. The comment is mandatory and is what
    the author sees; their next self-review run clears it. Requires the reviewer role."""
    return _authed_call(
        "POST", f"/api/task-reviews/{task_review_id}/return", json={"comment": comment}
    )


@mcp.tool()
def delete_task_review(
    task_review_id: Annotated[int, Field(description="Numeric id from `list_review_board`.")],
) -> Any:
    """Remove a task and ALL its self-review runs from the board — for a duplicate or a mistyped
    task_ref. The author may while it is unapproved; after a sign-off only an admin may, so an
    approval cannot be quietly erased. Unauthorized in stdio mode returns
    `{action_required: <how to approve>}`."""
    return _authed_call("DELETE", f"/api/task-reviews/{task_review_id}")


# --- Self-review (review your OWN change with the skill the team configured) ---------------------


class Finding(BaseModel):
    """One issue found in your own change."""

    model_config = ConfigDict(extra="forbid")

    severity: Annotated[FindingSeverity, Field(description="How badly it must be fixed.")]
    title: Annotated[str, Field(description="One-line statement of the issue.")]
    file: Annotated[str | None, Field(description="Repo-relative path.")] = None
    line: Annotated[int | None, Field(description="1-indexed line it anchors to.")] = None
    detail: Annotated[str, Field(description="Why it is wrong / what breaks.")] = ""
    suggestion: Annotated[str, Field(description="The concrete fix.")] = ""


@mcp.tool()
def get_self_review_policy() -> Any:
    """Which catalog skill the team uses to review its OWN changes, per lane (default / backend /
    frontend), and whether a self-review is mandatory before handing a task to the lead. Read this
    FIRST, then fetch that skill with `get_skill` and apply it to your diff. The choice is a server
    setting, so everyone self-reviews the same way."""
    return _read_call("GET", "/api/self-reviews/policy")


@mcp.tool()
def submit_self_review(
    task_ref: Annotated[str, Field(description="The issue_logs id or link the work belongs to.")],
    findings: Annotated[
        list[Finding] | None, Field(description="Issues found; empty means the change is clean.")
    ] = None,
    branch: Annotated[str | None, Field(description="Branch that was reviewed.")] = None,
    commit_shas: Annotated[list[str] | None, Field(description="Commits reviewed.")] = None,
    repo: Annotated[
        str | None,
        Field(
            description="Repository reviewed, verbatim from `git remote get-url origin` (ssh or "
            "https). Findings deep-link into it, so pass it — teams work in several repos and "
            "without it a finding cannot be opened at its line."
        ),
    ] = None,
    lane: Annotated[
        SelfReviewLane, Field(description="Which policy lane the change falls into.")
    ] = "default",
    skill: Annotated[
        str | None,
        Field(description="Skill you actually applied; omit to record the lane's configured one."),
    ] = None,
    model: Annotated[str, Field(description="Model that ran the review, e.g. claude-opus-5.")] = "",
    verdict: Annotated[
        SelfReviewVerdict | None,
        Field(description="Omit to derive it: any blocker/major finding means changes_needed."),
    ] = None,
    summary: Annotated[str, Field(description="What the review covered and concluded.")] = "",
    title: Annotated[str, Field(description="Short human title for the task on the board.")] = "",
) -> Any:
    """Post the result of reviewing your OWN change with the configured skill. This is what puts
    the task on the review board: the row is created on the first run, and every later run updates
    its status — clean run means it is waiting for the lead, findings mean it is back with you.
    Unauthorized in stdio mode returns `{action_required: <how to approve>}`."""
    body = {
        "task_ref": task_ref, "branch": branch, "commit_shas": commit_shas or [], "repo": repo,
        "lane": lane, "skill": skill, "model": model, "verdict": verdict,
        "summary": summary, "title": title,
        "findings": [f.model_dump() for f in (findings or [])],
    }
    return _authed_call("POST", "/api/self-reviews", json=body)


@mcp.tool()
def list_self_reviews(
    mine: Annotated[bool, Field(description="Only the ones you ran.")] = True,
    task_ref: Annotated[str | None, Field(description="Filter by task.")] = None,
    task_review_id: Annotated[
        int | None, Field(description="Only the runs belonging to this board task.")
    ] = None,
) -> Any:
    """Self-reviews, newest first — each with its verdict and finding counts. Use `get_self_review`
    for the full findings list."""
    params: dict[str, Any] = {"mine": "true" if mine else "false"}
    if task_ref:
        params["task_ref"] = task_ref
    if task_review_id is not None:
        params["task_review_id"] = str(task_review_id)
    return _read_call("GET", "/api/self-reviews", params=params)


@mcp.tool()
def get_self_review(
    self_review_id: Annotated[int, Field(description="Numeric self-review id from a list tool.")],
) -> Any:
    """One self-review with every finding (severity, file, line, detail, suggestion), each with a
    deep link to its line and whatever fixes have been recorded against it."""
    return _read_call("GET", f"/api/self-reviews/{self_review_id}")


@mcp.tool()
def delete_self_review(
    self_review_id: Annotated[int, Field(description="Numeric self-review id you ran.")],
) -> Any:
    """Delete one of your own self-reviews — a mis-targeted run, a duplicate, or one posted against
    the wrong task. Its fixes go with it, and so does its entry in any peer review's thread; the
    peer review itself survives. Admins may delete any. Unauthorized in stdio mode returns
    `{action_required: <how to approve>}`."""
    return _authed_call("DELETE", f"/api/self-reviews/{self_review_id}")


class Fix(BaseModel):
    """How one finding was addressed."""

    model_config = ConfigDict(extra="forbid")

    finding_index: Annotated[
        int, Field(description="0-based position of the finding in the review's list.")
    ]
    commit_sha: Annotated[
        str | None, Field(description="Commit that fixes it; omit when the answer is not code.")
    ] = None
    note: Annotated[str, Field(description="What you did, or why nothing was needed.")] = ""


@mcp.tool()
def record_self_review_fixes(
    self_review_id: Annotated[int, Field(description="The self-review you are answering.")],
    fixes: Annotated[list[Fix], Field(description="One entry per finding you addressed.")],
) -> Any:
    """Say what you did about individual findings, AFTER fixing them. Purely additive: the verdict,
    the severities and the findings stay exactly as the skill reported them — this only shows the
    reader which commit closed which point, so the review reads as a before/after instead of a list
    of complaints. Only the review's author may record fixes; unauthorized in stdio mode returns
    `{action_required: <how to approve>}`."""
    return _authed_call(
        "POST", f"/api/self-reviews/{self_review_id}/fixes", json=[f.model_dump() for f in fixes]
    )


# --- Admin: users, roles and the lead flag (admin only) ------------------------------------------


@mcp.tool()
def list_users() -> Any:
    """Everyone who has signed in to SkillHub: id, name, role and `is_reviewer` (the lead flag).
    Use the id with `set_user_role` / `set_reviewer`. Admin only — anyone else gets 403."""
    return _authed_call("GET", "/api/admin/users")


@mcp.tool()
def set_user_role(
    user_id: Annotated[int, Field(description="Numeric id from `list_users`.")],
    role: Annotated[
        UserRole,
        Field(
            description="viewer reads · contributor uploads · evaluator also scores · admin also "
            "manages users and the self-review policy."
        ),
    ],
) -> Any:
    """Change someone's role. Admin only. Refused with 409 for your OWN role — another admin has to
    change it, so nobody locks themselves out of user management. The lead flag is separate: see
    `set_reviewer`. A user must have signed in once before they appear here."""
    return _authed_call("POST", f"/api/admin/users/{user_id}/role", json={"role": role})


@mcp.tool()
def set_reviewer(
    user_id: Annotated[int, Field(description="Numeric id from `list_users`.")],
    is_reviewer: Annotated[
        bool, Field(description="true makes them a lead on the review board; false revokes it.")
    ],
) -> Any:
    """Grant or revoke the lead flag: a lead may approve tasks on the review board or send them back
    with a comment. Independent of the role — an admin can mark a lead without being one, and admins
    can sign off tasks anyway. Admin only."""
    return _authed_call(
        "POST", f"/api/admin/users/{user_id}/reviewer", json={"is_reviewer": is_reviewer}
    )


if __name__ == "__main__":
    if TRANSPORT == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
