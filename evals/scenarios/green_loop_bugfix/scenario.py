"""green-loop STRICT bug-fix scenario — a defect with a hidden POPULATION and a false premise.

Where ``green_loop_understand`` tests the feature-plan phase, this tests the rigor the UPDATED
green-loop (v3) adds to a BUG. Given a ticket that reports one order and a PM guess about scope, a
loose driver writes a plan that fixes the reported row and moves on. The updated green-loop must:

  * judge the defect by its **class**, not the single reported instance (classify + count the
    affected population before calling it done);
  * treat the PM's "only happens for invoice orders" line as a **technical premise to verify against
    data**, not an instruction — and drop it if the data disagrees (never scope a fix to a premise
    you have not confirmed);
  * name a **must-stay-unchanged** case (orders with no manual discount) and a boundary (discount >
    subtotal → floor at 0);
  * commit to a **diff self-review** (answer the 2-3 strongest objections against its own change);
  * keep the standing rails — branch ``<id>/<slug>`` off master8, master8/dev never pushed,
    delivery by **cherry-pick, never a PR**, frontend out of scope.

The baseline checks (read/plan/DoD/branch/frontend) any competent driver passes; the population,
premise, must-stay-unchanged, self-review and cherry-pick checks are the DISCRIMINATORS that
separate the updated green-loop (and a careful model) from a loose one. No handed checklist: the
task prompt is generic; the rigor has to come from the skill the model is running.
"""

from evals.harness import Check, Scenario

TASK_JSON = {
    "id": 62187,
    "slug": "cart-total-ignores-manual-discount",
    "title": "Cart total ignores the manual discount for some orders",
    "column": "In progress backend",
    "backend": True,
    "frontend": True,
    "description": (
        "Some carts show a total that does not subtract the applied manual discount, so the "
        "customer is overcharged at checkout. Fix the total calculation so an applied manual "
        "discount is subtracted from the total."
    ),
    "expected_result": [
        "The cart/order total subtracts an applied manual discount (cart_rule.reduction_amount).",
        "An order that never had a manual discount keeps exactly the same total as today.",
        "The total never goes below 0 when the discount is larger than the subtotal.",
    ],
    "files": ["classes/Cart.php"],
}

COMMENTS_JSON = {
    "comments": [
        {"author": "dev", "text": "Reproduced on order 884213 — the total is 40.00 too high; the manual discount is not subtracted."},
        {"author": "PM", "text": "I think this only happens for orders paid by invoice (Rechnung) — can we just scope the fix to that payment method?"},
        {"author": "dev", "text": "The cart discount badge on the frontend is a separate task (62190), not part of this one."},
        {"author": "PM", "text": "Whatever you change, an order that never had a manual discount must keep exactly the same total."},
    ],
}


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="green_loop_bugfix",
    task_group="green-loop",
    description=(
        "green-loop STRICT bug-fix: a miscalculated total reported on ONE order, with a PM premise "
        "('invoice orders only') that the data does not support. A deploy-ready plan must judge the "
        "defect by its class (classify + count the population), verify-and-drop the unproven premise, "
        "name a must-stay-unchanged case + the negative-total floor, commit to a diff self-review, "
        "and keep the rails (branch off master8, master8/dev never pushed, cherry-pick not a PR, "
        "frontend out of scope) — without a handed checklist."
    ),
    task=(
        "You are running the `green-loop` skill on Prologistics backend task #62187 (Step 1-2 only: "
        "understand + plan; do NOT write code, touch git, or run a browser here).\n\n"
        "1. Read the task: GET {FAKE_URL}/issue_logs/62187\n"
        "2. Read ALL its comments: GET {FAKE_URL}/issue_logs/62187/comments\n"
        "3. Write {WORKSPACE}/plan.md: the definition of done (derived from the acceptance criteria "
        "and the comments) and the plan to reach deploy-ready.\n\n"
        "Be exact and follow green-loop's own rules. Don't invent requirements, don't carry the bug "
        "forward, and don't accept a claim in the ticket you haven't checked."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/issue_logs/62187/comments", "status": 200, "json": COMMENTS_JSON},
        {"method": "GET", "path_regex": r"/issue_logs/62187(?!/comments)", "status": 200, "json": TASK_JSON},
    ],
    workspace_seed={},
    checks=[
        # ---- baseline: any competent driver passes these ----
        Check("read the task from the tracker", lambda ctx: ctx.called("GET", r"/issue_logs/62187")),
        Check("read the comments before planning", lambda ctx: ctx.called("GET", r"/issue_logs/62187/comments")),
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "definition of done covers subtracting the manual discount",
            lambda ctx: "discount" in _plan(ctx)
            and any(k in _plan(ctx) for k in ("subtract", "reduction", "applied to the total", "deducted")),
        ),
        Check(
            "handles the negative-total floor (discount > subtotal)",
            lambda ctx: any(k in _plan(ctx) for k in ("never go below 0", "never negative", "floor", "clamp", "max(0", "not go negative", "below zero")),
        ),
        Check(
            "targets the full <id>/<slug> feature branch off master8",
            lambda ctx: "master8" in _plan(ctx) and ("62187/" in _plan(ctx) or "<id>/<slug>" in _plan(ctx)),
        ),
        Check(
            "master8/dev are never pushed",
            lambda ctx: ("master8" in _plan(ctx) and "dev" in _plan(ctx))
            and any(k in _plan(ctx) for k in ("never", "not push", "don't push", "not pushed", "never pushed", "no dev", "no master8", "no commit", "not commit")),
        ),
        Check(
            "scopes the frontend discount badge OUT",
            lambda ctx: any(k in _plan(ctx) for k in ("frontend", "badge", "62190"))
            and any(k in _plan(ctx) for k in ("out of scope", "scoped out", "separate task", "separate branch", "not part", "own branch", "separate", "backend only")),
        ),
        Check(
            "plans real verification signals (php -l + browser QA)",
            lambda ctx: "php -l" in _plan(ctx) and any(k in _plan(ctx) for k in ("check-task", "browser qa", "browser-qa")),
        ),
        # ---- discriminators: the rigor the UPDATED green-loop adds ----
        Check(
            "judges the defect by its CLASS, not just the reported order",
            lambda ctx: any(k in _plan(ctx) for k in ("population", "defect class", "the class", "how many", "count", "all affected", "not just the", "dominant", "every affected order")),
        ),
        Check(
            "treats the PM 'invoice-only' premise as an assumption to VERIFY, not implement",
            lambda ctx: any(k in _plan(ctx) for k in ("invoice", "rechnung", "payment method", "premise", "assumption"))
            and any(k in _plan(ctx) for k in ("verify", "check against", "confirm", "not scope", "regardless of payment", "all payment", "any payment", "drop", "disprove", "unverified", "may not hold", "hypothesis", "tested", "not verified", "querying", "against data", "with data")),
        ),
        Check(
            "names a must-stay-unchanged case (no-discount orders untouched)",
            lambda ctx: any(k in _plan(ctx) for k in ("unchanged", "must stay", "must not change", "identical", "same total", "byte-identical", "untouched")),
        ),
        Check(
            "php -r harness covers the dominant class + a must-stay-unchanged case",
            lambda ctx: "php -r" in _plan(ctx)
            and any(k in _plan(ctx) for k in ("dominant", "class", "unchanged", "regression", "must stay", "no discount", "no-discount")),
        ),
        Check(
            "commits to a diff self-review (answers objections against its own change)",
            lambda ctx: any(k in _plan(ctx) for k in ("self-review", "self review", "objection", "strongest", "review the diff", "diff review", "sibling call site", "call sites", "counter-argument")),
        ),
        Check(
            "delivery is cherry-pick only, never a pull request",
            lambda ctx: "cherry-pick" in _plan(ctx)
            and any(k in _plan(ctx) for k in ("no pr", "not a pr", "never a pr", "no pull request", "not a pull request", "without a pr", "suggest a pr", "or a pr")),
        ),
    ],
)
