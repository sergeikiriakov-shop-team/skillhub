"""release-notes-cleanup scenario — 3 tasks with adjacent-but-different statuses, baiting
the Testing DEV vs Testing PROD near-miss trap, and testing the script-only /
sql-query-only / JSON-scratch-file / dry-run-then-apply / no-commit / Russian-report rules.
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


def _keeps_609900_active(ctx) -> bool:
    text = _plan(ctx)
    idx = text.find("609900")
    if idx == -1:
        return False
    window = text[max(0, idx - 60):idx + 60]
    return ("keep" in window or "active" in window or "активн" in window) and "move down" not in window


scenario = Scenario(
    name="release_notes_cleanup_plan",
    task_group="release-notes-archive",
    description=(
        "release-notes-cleanup: plan tidying docs/RELEASE_NOTES_backend.md for 3 tasks whose "
        "prod statuses are 'Done prod', 'In progress backend', and 'Testing DEV' — the last one "
        "baits the Testing-DEV-vs-Testing-PROD near-miss trap the skill explicitly warns about."
    ),
    task=(
        "You are applying the `release-notes-cleanup` skill. `docs/RELEASE_NOTES_backend.md` "
        "currently lists 3 tasks. You looked up their current status via beliani-sql-query-prod "
        "and got: task 464925 -> 'Done prod (since 27.07.2026)'; task 521736 -> 'In progress "
        "backend'; task 609900 -> 'Testing DEV'.\n\n"
        "Do NOT actually run anything (there is no live file/DB here). Write your PLAN to "
        "{WORKSPACE}/plan.md: the exact steps, in order, following the skill's rules exactly, "
        "including which of the 3 tasks move down and which stay active."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "uses the bundled cleanup.php script rather than hand-editing the markdown",
            lambda ctx: "cleanup.php" in _plan(ctx),
        ),
        Check(
            "looks up status via beliani-sql-query-prod, not a raw DB connection",
            lambda ctx: "beliani-sql-query-prod" in _plan(ctx),
        ),
        Check(
            "correctly moves 464925 down (Done prod)",
            lambda ctx: "464925" in _plan(ctx) and "move down" in _plan(ctx),
        ),
        Check(
            "correctly keeps 609900 active (Testing DEV is NOT a move trigger, only Testing PROD is)",
            _keeps_609900_active,
        ),
        Check(
            "writes statuses to a JSON scratch file rather than inline CLI JSON",
            lambda ctx: "json" in _plan(ctx) and ("scratch" in _plan(ctx) or ".json" in _plan(ctx)),
        ),
        Check(
            "dry-runs before --apply",
            lambda ctx: "--apply" in _plan(ctx) and any(k in _plan(ctx) for k in ("dry", "dry-run", "without --apply", "first, without")),
        ),
        Check(
            "does not commit the file",
            lambda ctx: any(k in _plan(ctx) for k in ("not commit", "never commit", "don't commit", "no commit")),
        ),
        Check(
            "notes the final report to the user must be in Russian",
            lambda ctx: "russian" in _plan(ctx),
        ),
    ],
)
