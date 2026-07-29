"""Green-loop scenario — the *understand → definition-of-done → plan* phase (Step 1–2 only).

Green-loop (`~/.claude/skills/green-loop`) is deeply environment-coupled: it drives a Prologistics
backend task to deploy-ready using real git (heap/dev), browser QA (`check-task`), `php -l`/`php -r`
and the `beliani-*` MCPs. The sandbox CANNOT reproduce that half faithfully, so this scenario scopes
the trial to the phase the harness *can* exercise honestly:

  Step 1  read the task in the tracker + its PM/developer comments **before touching code**, and
  Step 2  derive the *definition of done* from the task's own acceptance criteria (not invented),
          then write a plan that respects green-loop's rules.

The fake service stands in for Prolo: one backend task at ``/issue_logs/<id>`` plus its
``/comments``. The checks assert green-loop's real discriminators for this phase — reads the task
AND the comments first, takes the definition of done from the acceptance criteria (including the
subtle ordering rule), addresses the PM comment, scopes the frontend item OUT, plans the real
verification signals, targets the full ``<id>/<slug>`` feature branch, and does NOT propose a PR
(delivery is cherry-pick only). Out of scope for this trial: the execute/fix loop, git, browser QA.
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
        "Today a cart accepts only a single coupon. Marketing wants a percentage coupon and a "
        "fixed-amount coupon to be combinable on one cart, with a deterministic order of application."
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
    ]
}


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="green_loop_understand",
    task_group="green-loop",
    description=(
        "Green-loop Step 1–2: read task #61234 and its comments from the fake tracker, then write a "
        "plan whose definition of done comes from the task's acceptance criteria (not invented)."
    ),
    task=(
        "You are running the `green-loop` skill on backend task #61234, but ONLY its Step 1–2 "
        "(understand the task and its state, then state the definition of done and a plan) — do NOT "
        "execute code, touch git, or run browser QA in this sandbox.\n\n"
        "1. Read the task from the fake tracker: GET {FAKE_URL}/issue_logs/61234 .\n"
        "2. BEFORE planning, read its comments (work is already started): "
        "GET {FAKE_URL}/issue_logs/61234/comments .\n"
        "3. Write {WORKSPACE}/plan.md that, per green-loop:\n"
        "   - states the DEFINITION OF DONE taken from the task's `expected` acceptance criteria "
        "(don't invent requirements), including the ordering rule (percentage BEFORE fixed);\n"
        "   - addresses the PM comment (same-campaign guard);\n"
        "   - scopes the frontend badge OUT (separate branch), not counted as a gap;\n"
        "   - lists the verification signals green-loop would use (php -l, a php -r harness, "
        "browser QA via check-task) — as the plan, not run here;\n"
        "   - targets the full feature branch 61234/cart-coupon-stacking;\n"
        "   - delivery is cherry-pick only — do NOT propose or prepare a pull request."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/issue_logs/61234", "status": 200, "json": TASK_JSON},
        {"method": "GET", "path_regex": r"/issue_logs/61234/comments", "status": 200, "json": COMMENTS_JSON},
    ],
    workspace_seed={},
    checks=[
        Check("read the task from the tracker", lambda ctx: ctx.called("GET", r"/issue_logs/61234$")),
        Check("read PM/dev comments before planning", lambda ctx: ctx.called("GET", r"/issue_logs/61234/comments")),
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "definition of done = acceptance criteria (ordering rule)",
            lambda ctx: "percentage" in _plan(ctx) and "before" in _plan(ctx) and "fixed" in _plan(ctx),
        ),
        Check("addresses the PM comment (same-campaign guard)", lambda ctx: "campaign" in _plan(ctx)),
        Check(
            "scopes the frontend badge OUT",
            lambda ctx: "frontend" in _plan(ctx) and ("out of scope" in _plan(ctx) or "separate" in _plan(ctx) or "own branch" in _plan(ctx)),
        ),
        Check(
            "plans the real verification signals",
            lambda ctx: "php -l" in _plan(ctx) and "php -r" in _plan(ctx) and ("check-task" in _plan(ctx) or "browser" in _plan(ctx)),
        ),
        Check("targets the full <id>/<slug> feature branch", lambda ctx: "61234/cart-coupon-stacking" in _plan(ctx)),
        Check(
            "does NOT propose a pull request (cherry-pick only)",
            # Fail only if the plan PROPOSES opening a PR — not merely if it says the words
            # "pull request" (a faithful plan says it will NOT open one, which must still pass).
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
