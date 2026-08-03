"""prolo-task-driver STRICT intake scenario — Business Goal/Currently/Expected/ToDo intake +
the unit+integration-tests readiness bar that distinguishes this skill from green-loop.

Ground truth: task #71012, a bug where free/0-price line items silently vanish from the daily
order-export CSV. A PM guesses the defect is scoped to one promotion type; a dev flags an unrelated
CSV-header task as out of scope; a PM restates the must-stay-unchanged invariant (cancelled orders
still excluded). A faithful intake must: map the tracker fields into the exact
BusinessGoal/Currently/Expected/ToDo tags (this skill's signature step, absent from green-loop);
derive the DoD from Expected only; explicitly address the PM's scoping question either way; keep the
must-stay-unchanged case; and carry prolo-task-driver's mandatory unit+integration-test readiness
condition (green-loop only requires a php -r harness) alongside php -l / php -r / schema checks and
the standing master8/dev/heap rails.
"""

from evals.harness import Check, Scenario

TASK_JSON = {
    "id": 71012,
    "slug": "order-export-skips-zero-price-items",
    "title": "Order export CSV skips orders with 0 taxable items",
    "column": "In progress backend",
    "backend": True,
    "frontend": True,
    "business_goal": (
        "Finance needs a complete daily order-export CSV for every order placed, including "
        "promotional/free-item orders, so nothing is missed in accounting reconciliation."
    ),
    "currently": (
        "Orders where every line item is priced at 0 (free promo items) are silently missing "
        "from the CSV export entirely."
    ),
    "expected": [
        "Every order in the export date range appears in the CSV, regardless of item price.",
        "An order's export row shows its real item count (never 0 when items exist).",
        "Cancelled orders must still be excluded from the export (existing behavior; do not change).",
    ],
    "checklists": [
        "Confirm the export query does not filter on item price/subtotal > 0",
        "Add a regression case for 0-price line items",
        "Confirm cancelled orders still excluded",
    ],
}

COMMENTS_JSON = {
    "comments": [
        {"author": "dev", "text": "Reproduced on order 991044 - 3 free promo items, but the order doesn't appear in the CSV at all."},
        {"author": "PM", "text": "I think this only affects orders using the 'BOGO' promotion - can we scope the fix to that promotion type?"},
        {"author": "dev", "text": "The CSV column-header change requested last month is a separate task (71020), not part of this one."},
        {"author": "PM", "text": "Whatever you change, cancelled orders must still be excluded - don't undo that."},
    ],
}


def _plan(ctx) -> str:
    return (ctx.file("intake.md") or "").lower()


scenario = Scenario(
    name="prolo_task_driver_intake",
    task_group="single-task-driver",
    description=(
        "prolo-task-driver intake: build the BusinessGoal/Currently/Expected/ToDo structured "
        "prompt + the definition of done for a 0-price-items export bug, with a PM scoping "
        "question, an out-of-scope decoy task, and a must-stay-unchanged invariant. Discriminates "
        "on the exact 4-tag structure and the mandatory unit+integration-tests readiness bar."
    ),
    task=(
        "You are running the `prolo-task-driver` skill on Prologistics backend task #71012 "
        "(Step 2-3 only: build the intake prompt + state the definition of done; do NOT touch git, "
        "code, or a browser here).\n\n"
        "1. Read the task: GET {FAKE_URL}/issue_logs/71012\n"
        "2. Read ALL its comments: GET {FAKE_URL}/issue_logs/71012/comments\n"
        "3. Write {WORKSPACE}/intake.md: the structured BusinessGoal/Currently/Expected/ToDo intake "
        "prompt (per the skill's Step 2.3 format) followed by the definition of done (Step 3) for "
        "reaching deploy-ready.\n\n"
        "Be exact: use the task's own fields for the four tags, derive the DoD only from Expected, "
        "and address every PM/developer comment. Don't invent requirements."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/issue_logs/71012/comments", "status": 200, "json": COMMENTS_JSON},
        {"method": "GET", "path_regex": r"/issue_logs/71012(?!/comments)", "status": 200, "json": TASK_JSON},
    ],
    workspace_seed={},
    checks=[
        Check("read the task from the tracker", lambda ctx: ctx.called("GET", r"/issue_logs/71012")),
        Check("read the comments before planning", lambda ctx: ctx.called("GET", r"/issue_logs/71012/comments")),
        Check("wrote intake.md", lambda ctx: ctx.file("intake.md") is not None),
        Check("produces the <BusinessGoal> tag", lambda ctx: "businessgoal" in _plan(ctx)),
        Check("produces the <Currently> tag", lambda ctx: "currently" in _plan(ctx)),
        Check("produces the <Expected> tag", lambda ctx: "expected" in _plan(ctx)),
        Check("produces the <ToDo> tag from the Checklists", lambda ctx: "todo" in _plan(ctx)),
        Check(
            "DoD covers 0-price items appearing in the export (from Expected, not invented)",
            lambda ctx: any(k in _plan(ctx) for k in ("0-price", "zero-price", "free", "0 price")) and "export" in _plan(ctx),
        ),
        Check(
            "explicitly addresses/answers the PM's BOGO-scoping question",
            lambda ctx: "bogo" in _plan(ctx),
        ),
        Check(
            "keeps the must-stay-unchanged case (cancelled orders still excluded)",
            lambda ctx: "cancel" in _plan(ctx) and any(k in _plan(ctx) for k in ("exclude", "unchanged", "still", "not change", "don't undo")),
        ),
        Check("scopes the CSV-header task 71020 OUT", lambda ctx: "71020" in _plan(ctx)),
        Check("mentions unit tests for new methods", lambda ctx: "unit test" in _plan(ctx)),
        Check("mentions integration tests", lambda ctx: "integration test" in _plan(ctx)),
        Check("plans php -l", lambda ctx: "php -l" in _plan(ctx)),
        Check(
            "plans a php -r harness against the real example (991044)",
            lambda ctx: "php -r" in _plan(ctx) and "991044" in _plan(ctx),
        ),
        Check(
            "plans a schema/data confirmation via the beliani-* MCPs",
            lambda ctx: any(k in _plan(ctx) for k in ("beliani-db-schema", "beliani-sql-query")),
        ),
        Check(
            "master8/dev are never pushed",
            lambda ctx: ("master8" in _plan(ctx) and "dev" in _plan(ctx))
            and any(k in _plan(ctx) for k in ("never", "not push", "don't push", "not pushed", "never pushed")),
        ),
        Check(
            "heap push only with the user's explicit approval",
            lambda ctx: "heap" in _plan(ctx) and any(k in _plan(ctx) for k in ("approval", "approve")),
        ),
    ],
)
