"""Task-batch scenario — the INTAKE + orchestration-plan phase (skip-gate + live-queue fan-out).

task-batch is an ORCHESTRATOR: it runs a live queue of tasks, spawning one subagent + one git
worktree per task to drive each to deploy-ready via green-loop, streaming each back as it finishes.
The sandbox can't spawn real subagents/worktrees/git, so this scopes the trial to the phase it CAN
exercise honestly: **Step 0 (skip-if-done gate) + the batch orchestration plan** the orchestrator
produces before fanning out.

The fake tracker serves one ``/queue`` with five tasks whose board columns + comments encode the
right decisions — a discriminating intake:
  * 501 In-progress, actionable        → PROCESS
  * 502 Testing DEV (done, in pipeline) → SKIP
  * 503 To-do, brand-new card          → SKIP (not yet actionable)
  * 504 In-progress, touches the SAME file as 501 (classes/Cart.php) → PROCESS, but SERIALIZE with 501
  * 505 In-progress, ambiguous acceptance (PM question) → PROCESS, but PARK on the open question

A perfect plan reads the queue, applies the skip gate per column, catches the 501/504 dependency,
flags 505 to park, and lays out task-batch's isolation/release/heap/failure model. Out of scope:
actually spawning subagents, git, running green-loop.
"""

from evals.harness import Check, Scenario

QUEUE_JSON = {
    "tasks": [
        {
            "id": 501,
            "slug": "cart-coupon-tests",
            "column": "In progress backend",
            "files": ["classes/Cart.php"],
            "comments": [{"author": "dev", "text": "Skeleton done; add the php -r test harness for coupon stacking."}],
        },
        {
            "id": 502,
            "slug": "invoice-pdf-encoding",
            "column": "Testing DEV",
            "files": ["classes/Invoice.php"],
            "comments": [{"author": "dev", "text": "Fixed and deployed to dev; awaiting PM QA."}],
        },
        {
            "id": 503,
            "slug": "new-loyalty-tier",
            "column": "To do backend",
            "files": [],
            "comments": [],
        },
        {
            "id": 504,
            "slug": "cart-coupon-logging",
            "column": "In progress backend",
            "files": ["classes/Cart.php"],
            "comments": [{"author": "PM", "text": "Add audit logging when a coupon is rejected."}],
        },
        {
            "id": 505,
            "slug": "refund-partial",
            "column": "In progress backend",
            "files": ["classes/Refund.php"],
            "comments": [{"author": "PM", "text": "Is a partial refund allowed when a coupon was used? The acceptance criteria don't say — need a decision."}],
        },
    ]
}


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="task_batch_intake",
    task_group="task-batch",
    description=(
        "Task-batch INTAKE (Step 0 skip-gate + orchestration plan): read a mixed-state queue and, "
        "per task, decide process vs skip by board column; catch the 501/504 same-file dependency "
        "(serialize); flag the ambiguous 505 to park; and lay out the isolation/release/heap/"
        "failure model — without spawning subagents or touching git."
    ),
    task=(
        "You are running the `task-batch` skill over a queue of Prologistics tasks. Do its INTAKE + "
        "orchestration PLANNING only (Step 0 skip-if-done gate + the live-queue fan-out plan) — do "
        "NOT spawn subagents, touch git, or run green-loop here.\n\n"
        "1. Read the queue: GET {FAKE_URL}/queue (each task has its board column, comments, and the "
        "files it touches).\n"
        "2. Write {WORKSPACE}/plan.md:\n"
        "   - For EACH task, decide PROCESS or SKIP and give the reason from its board column / "
        "comments, per task-batch's skip-if-done gate.\n"
        "   - Assign each processed task its `<id>/<slug>` branch off master8.\n"
        "   - Give the batch orchestration plan per task-batch: how tasks are isolated and run, the "
        "concurrency window, any dependencies between tasks, where release notes go, how heap and "
        "master8/dev are handled, what happens to a task that can't be finished, and how finished "
        "tasks are returned.\n"
        "Be exact: apply the skip gate correctly, catch any dependency between tasks, and follow "
        "task-batch's isolation / release-file / heap / failure rules. Don't invent tasks or steps."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/queue", "status": 200, "json": QUEUE_JSON},
    ],
    workspace_seed={},
    checks=[
        Check("read the queue from the tracker", lambda ctx: ctx.called("GET", r"/queue")),
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "skips the done task (Testing DEV / Upload request)",
            lambda ctx: ("testing dev" in _plan(ctx) or "upload request" in _plan(ctx)) and "skip" in _plan(ctx),
        ),
        Check(
            "skips the brand-new To-do card (not yet actionable)",
            lambda ctx: "to do" in _plan(ctx) and "skip" in _plan(ctx),
        ),
        Check(
            "processes the actionable in-progress tasks",
            lambda ctx: "in progress" in _plan(ctx) and ("process" in _plan(ctx) or "drive" in _plan(ctx)),
        ),
        Check(
            "assigns per-task <id>/<slug> branches off master8",
            lambda ctx: "master8" in _plan(ctx) and ("501/" in _plan(ctx) or "504/" in _plan(ctx) or "<id>/<slug>" in _plan(ctx)),
        ),
        Check("isolates each task in its own worktree", lambda ctx: "worktree" in _plan(ctx)),
        Check(
            "bounded concurrency window (parallel, default 3)",
            lambda ctx: ("parallel" in _plan(ctx) or "concurren" in _plan(ctx)) and "3" in _plan(ctx),
        ),
        Check(
            "catches the 501/504 same-file dependency and serializes",
            lambda ctx: "serial" in _plan(ctx)
            and any(k in _plan(ctx) for k in ("overlap", "depend", "same file", "cart.php", "same-file")),
        ),
        Check(
            "parks the ambiguous task rather than aborting the batch",
            lambda ctx: "park" in _plan(ctx),
        ),
        Check(
            "aggregates notes into the one shared docs/RELEASE_NOTES_backend.md",
            lambda ctx: "release_notes_backend" in _plan(ctx),
        ),
        Check(
            "heap push requires the user's approval",
            lambda ctx: "heap" in _plan(ctx) and ("approval" in _plan(ctx) or "approve" in _plan(ctx)),
        ),
        Check(
            "master8/dev are never pushed",
            lambda ctx: ("master8" in _plan(ctx) and "dev" in _plan(ctx))
            and any(k in _plan(ctx) for k in ("never", "not push", "don't push", "not pushed", "never pushed")),
        ),
        Check("drives each task via the green-loop pipeline", lambda ctx: "green-loop" in _plan(ctx)),
        Check(
            "returns each finished task as it's ready (streaming hand-back)",
            lambda ctx: any(k in _plan(ctx) for k in ("as soon as", "immediately", "as they finish", "as each", "stream", "return each", "as it finishes")),
        ),
    ],
)
