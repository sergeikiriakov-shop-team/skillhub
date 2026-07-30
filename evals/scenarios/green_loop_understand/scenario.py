"""Green-loop scenario — the *understand → definition-of-done → plan* phase (Step 1–2), STRICT.

Scoped to the phase the sandbox can exercise honestly (read task + comments → derive the definition
of done → plan); the git/browser/`php`/`beliani-*` half is out of scope. This version is deliberately
**discriminating**: the task hands NO checklist — the model must derive what matters from the task
and its comments — and the fixture plants traps that separate a careful reading from a skim:

  * a **withdrawn** requirement (a dropped "5-coupon cap") that must be IGNORED, not planned;
  * a **buried edge** (a fixed coupon larger than the discounted subtotal → the total must not go
    negative) that must be handled;
  * the same-campaign guard is only in a PM comment, and its subtlety is that it applies ACROSS
    coupon types;
  * the current behaviour ("silently replaces the first coupon") is a bug to fix, not to carry
    forward;
  * an AC-2 detail: a rejected duplicate must leave the first coupon applied.

A perfect score requires reading the comments, precision, and scope discipline — not restating the
task. Out of scope for this trial: the execute/fix loop, git, browser QA.
"""

from evals.harness import Check, Scenario

TASK_ID = 61234
SLUG = "cart-coupon-stacking"

TASK_JSON = {
    "id": TASK_ID,
    "slug": SLUG,
    "title": "Coupon stacking: allow one percentage + one fixed coupon per cart",
    "column": "In Progress",
    "description": (
        "Today a cart accepts only a single coupon: adding a second one SILENTLY REPLACES the first "
        "(this is the current behaviour to fix, not to keep). Marketing wants a percentage coupon "
        "and a fixed-amount coupon to be combinable on one cart, with a deterministic order of "
        "application."
    ),
    "expected": [
        "A cart accepts at most ONE percentage coupon AND ONE fixed-amount coupon at the same time.",
        "A second coupon of the same type is rejected with a clear error; the first stays applied.",
        "The percentage is applied to the subtotal BEFORE the fixed amount is subtracted.",
    ],
    "backend_owner": True,
    "frontend": "A badge in the cart UI listing both active coupons — separate FRONTEND task, its own branch.",
}

COMMENTS_JSON = {
    "comments": [
        {
            "author": "PM",
            "text": (
                "Also block stacking two coupons that share the same campaign id, even if their "
                "types differ — otherwise one campaign can be double-dipped."
            ),
        },
        {
            "author": "dev",
            "text": (
                "Branch 61234/cart-coupon-stacking already has the validator skeleton; what's left "
                "is the ordering rule and the same-campaign guard."
            ),
        },
        {
            "author": "PM",
            "text": (
                "Earlier we discussed also capping the cart at a maximum of 5 coupons — we have "
                "DROPPED that for this task, please ignore it, it is out of scope now."
            ),
        },
        {
            "author": "dev",
            "text": (
                "Heads up on the ordering: a fixed-amount coupon can be larger than the discounted "
                "subtotal, so make sure the final total can never go negative."
            ),
        },
    ]
}


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="green_loop_understand",
    task_group="green-loop",
    description=(
        "Green-loop Step 1–2 (STRICT): read task #61234 and ALL its comments, then write a plan "
        "whose definition of done is derived from the acceptance criteria + comments — catching the "
        "buried same-campaign guard and negative-total edge, ignoring the withdrawn 5-coupon cap, "
        "and not restating a handed checklist."
    ),
    task=(
        "You are running the `green-loop` skill on backend task #61234 — its Step 1–2 ONLY: "
        "understand the task and its current state, then state the definition of done and a plan. "
        "Do NOT execute code, touch git, or run browser QA in this sandbox.\n\n"
        "Steps:\n"
        "1. Read the task: GET {FAKE_URL}/issue_logs/61234 .\n"
        "2. Work is already started, so BEFORE planning read ALL its comments: "
        "GET {FAKE_URL}/issue_logs/61234/comments .\n"
        "3. Write {WORKSPACE}/plan.md.\n\n"
        "Apply green-loop faithfully and precisely — you are NOT given a checklist, derive it:\n"
        "- The definition of done comes from the task's OWN `expected` acceptance criteria AND the "
        "PM/developer comments — not from you. Read the comments carefully: some add a real "
        "requirement, some withdraw one, some flag an edge case. Include what is required, and do "
        "NOT plan anything that was dropped or is out of scope.\n"
        "- Green-loop is backend-only; it commits on the task's full feature branch off master8, "
        "never touches master8/dev, and delivery is cherry-pick only (never a pull request).\n"
        "- State the verification you WOULD run (it is not run here).\n"
        "Be exact; do not invent requirements and do not carry forward the current buggy behaviour."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/issue_logs/61234", "status": 200, "json": TASK_JSON},
        {"method": "GET", "path_regex": r"/issue_logs/61234/comments", "status": 200, "json": COMMENTS_JSON},
    ],
    workspace_seed={},
    checks=[
        Check("read the task from the tracker", lambda ctx: ctx.called("GET", r"/issue_logs/61234$")),
        Check("read the comments before planning", lambda ctx: ctx.called("GET", r"/issue_logs/61234/comments")),
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "definition of done covers combinable percentage + fixed",
            lambda ctx: "percentage" in _plan(ctx) and "fixed" in _plan(ctx),
        ),
        Check(
            "gets the ordering rule right (percentage on the subtotal, then fixed)",
            lambda ctx: all(w in _plan(ctx) for w in ("percentage", "fixed", "subtotal"))
            and any(w in _plan(ctx) for w in ("before", "first", "then")),
        ),
        Check(
            "AC2: a rejected duplicate keeps the first coupon applied",
            lambda ctx: any(
                w in _plan(ctx)
                for w in (
                    "first stays", "stays applied", "still applied", "keeps the first",
                    "first one stays", "first coupon stays", "leaves the existing",
                    "existing coupon untouched", "first remains", "already applied stays",
                    "first coupon already applied stays",
                )
            ),
        ),
        Check("catches the same-campaign guard (only in a PM comment)", lambda ctx: "campaign" in _plan(ctx)),
        Check(
            "notes the campaign guard applies ACROSS coupon types",
            lambda ctx: "campaign" in _plan(ctx)
            and any(
                w in _plan(ctx)
                for w in ("even if", "even when", "regardless", "different type", "both types", "across type", "different types")
            ),
        ),
        Check(
            "handles the negative-total edge (fixed > discounted subtotal)",
            lambda ctx: any(
                w in _plan(ctx)
                for w in (
                    "negative", "below zero", "below 0", "not go below", "never go below", "floor",
                    "clamp", "max(0", ">= 0", "≥ 0", "can't go negative", "cannot go negative",
                    "never go negative", "not go negative", "no lower than 0",
                )
            ),
        ),
        Check(
            "scopes the frontend badge OUT",
            lambda ctx: "frontend" in _plan(ctx)
            and any(w in _plan(ctx) for w in ("out of scope", "separate", "own branch", "not a gap")),
        ),
        Check(
            "plans the real verification signals",
            lambda ctx: "php -l" in _plan(ctx) and "php -r" in _plan(ctx) and ("check-task" in _plan(ctx) or "browser" in _plan(ctx)),
        ),
        Check("targets the full <id>/<slug> feature branch", lambda ctx: "61234/cart-coupon-stacking" in _plan(ctx)),
        Check(
            "does NOT propose a pull request (cherry-pick only)",
            lambda ctx: not any(
                phrase in _plan(ctx)
                for phrase in (
                    "open a pull request", "open a pr", "opening a pull request",
                    "prepare a pull request", "create a pull request", "submit a pull request",
                    "raise a pull request", "pull request to master", "pr to master",
                )
            ),
        ),
    ],
)
