"""task-reeval scenario — an already-shipped query whose release note claims a "10x faster"
result; tests that the baseline is re-measured rather than trusted from the note, the
correctness/equivalence gate is mandatory before any efficiency claim, the 2-failed-hypothesis
cap is respected, no DDL/ALTER is proposed against prod, and the skill stays advisory
(never edits, commits, or deploys).
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="task_reeval_query_assessment_plan",
    task_group="task-optimality-reeval",
    description=(
        "task-reeval: assess an already-shipped query fix for task 512345, whose release note "
        "claims '10x faster' — tests re-measuring the baseline instead of trusting the claimed "
        "number, the mandatory correctness/equivalence gate before any efficiency claim, the "
        "2-failed-hypothesis cap, never proposing DDL/ALTER on prod, and staying advisory-only."
    ),
    task=(
        "You are applying the `task-reeval` skill. Task 512345 shipped a query fix: "
        "`SELECT * FROM auction WHERE shop_id = ? AND status IN (...)`. The release note for "
        "this task claims the fix made the page '10x faster'.\n\n"
        "Do NOT actually run anything. Write your PLAN to {WORKSPACE}/plan.md: how you'd assess "
        "this task end to end, following the skill's rules exactly."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "does not trust the release note's claimed number, re-measures the baseline itself",
            lambda ctx: any(k in _plan(ctx) for k in ("re-measure", "remeasure", "measure the baseline", "never trust", "not trust the release", "own measurement", "перезамер")),
        ),
        Check(
            "states the correctness/equivalence gate is mandatory before any efficiency claim",
            lambda ctx: any(k in _plan(ctx) for k in ("correctness", "equivalence")) and any(k in _plan(ctx) for k in ("mandatory", "gate", "before any", "first")),
        ),
        Check(
            "respects the 2-failed-hypothesis cap",
            lambda ctx: "2" in _plan(ctx) and any(k in _plan(ctx) for k in ("failed hypoth", "cap", "hypotheses")),
        ),
        Check(
            "never proposes running DDL/ALTER on prod, reasons from EXPLAIN instead",
            lambda ctx: "explain" in _plan(ctx) and not any(k in _plan(ctx) for k in ("alter table", "create index", "run ddl", "apply the index")),
        ),
        Check(
            "stays advisory-only: explicitly states it will not edit, commit, or deploy",
            lambda ctx: any(k in _plan(ctx) for k in (
                "advisory", "never edit", "does not edit", "not commit", "never commit",
                "no commit", "not deploy", "never deploy", "no deploy", "read-only",
                "no code edit", "no edits", "purely advisory", "purely the recommendation",
                "never implement", "not implement", "не редактир", "не коммит", "не деплой",
                "не внедря", "консультатив",
            )),
        ),
        Check(
            "verifies the row sets / results are identical before calling anything a win",
            lambda ctx: any(k in _plan(ctx) for k in ("identical", "same result", "same row", "except", "equivalent result")),
        ),
        Check(
            "the plan/report follows the skill's language rule (Russian by default)",
            lambda ctx: any(ch in _plan(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
    ],
)
