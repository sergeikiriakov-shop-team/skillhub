"""weekly-task-report STRICT scenario — a fake week of git history exercising the skill's own
documented traps: the issue id living only in the commit BODY (not the subject), a task authored
but not yet landed on dev/master8, and the step-3b rule that drops an already-"Testing PROD" id
from the not-landed section even though it never touched dev/master8 this window.
"""

from evals.harness import Check, Scenario

DEV_LOG = (
    "a1b2c3d|2026-07-28|issue_logs/601000 Fix rounding on partial refund\n"
    "e4f5g6h|2026-07-30|issue_logs/601005 Add audit log for coupon rejection\n"
    "s4d5f6g|2026-07-31|Refund calc tweak\n"
)

MASTER8_LOG = (
    "z9y8x7w|2026-07-29|601005 Add audit log for coupon rejection\n"
)

ALL_AUTHOR_LOG = (
    "a1b2c3d|2026-07-28|issue_logs/601000 Fix rounding on partial refund\n"
    "e4f5g6h|2026-07-30|issue_logs/601005 Add audit log for coupon rejection\n"
    "s4d5f6g|2026-07-31|Refund calc tweak\n"
    "p0o9i8u|2026-08-01|601020 WIP vat exemption check\n"
    "t7u8i9o|2026-08-02|601050 Diagnostic script for prod check\n"
)

COMMIT_BODY_S4D5F6G = "Refund calc tweak\n\nSee issue_logs/601040 for the reported case."

STATUS_JSON = {
    "601000": "In progress backend",
    "601005": "Testing PROD",
    "601020": "To do backend",
    "601040": "In progress backend",
    "601050": "Testing PROD",
}


def _report(ctx) -> str:
    return (ctx.file("report.md") or "").lower()


scenario = Scenario(
    name="weekly_task_report_window",
    task_group="weekly-rollout-report",
    description=(
        "weekly-task-report over a fake window: a task that landed on dev only, one that landed on "
        "both dev and master8/prod, a commit whose issue id lives only in the BODY (not the "
        "subject), a task authored this week but not yet landed anywhere, and a decoy task with no "
        "fresh commit that must be EXCLUDED from 'not landed' because its current status is "
        "already Testing PROD (the step-3b filter)."
    ),
    task=(
        "You are running the `weekly-task-report` skill for the window 2026-07-27 to 2026-08-03. "
        "Author email: sergei.kiriakov@beliani.net.\n\n"
        "`git log heads/dev --author=... --since=... --until=... --format=\"%h|%cd|%s\" --date=short`:\n"
        f"{DEV_LOG}\n"
        "`git log heads/master8 --author=... --since=... --until=... --format=\"%h|%cd|%s\" --date=short`:\n"
        f"{MASTER8_LOG}\n"
        "`git log --all --author=... --since=... --until=... --format=\"%h|%ad|%s\" --date=short`:\n"
        f"{ALL_AUTHOR_LOG}\n"
        "`git show --format=\"%B\" --no-patch s4d5f6g` (the commit body, since the subject has no "
        "issue_logs id):\n"
        f"{COMMIT_BODY_S4D5F6G}\n\n"
        "Tracker status per id (via beliani-sql-query-prod), status_name: "
        f"{STATUS_JSON}\n\n"
        "Compose the report per the skill's Step 6 structure and write it to {WORKSPACE}/report.md."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote report.md", lambda ctx: ctx.file("report.md") is not None),
        Check("states the date window", lambda ctx: "2026-07-27" in _report(ctx) or "27.07" in _report(ctx)),
        Check(
            "601000 landed on dev only (not master8/prod)",
            lambda ctx: "601000" in _report(ctx),
        ),
        Check(
            "601005 landed on both dev and master8/prod",
            lambda ctx: "601005" in _report(ctx) and any(k in _report(ctx) for k in ("master8", "prod")),
        ),
        Check(
            "finds 601040 via the commit body, not the subject",
            lambda ctx: "601040" in _report(ctx),
        ),
        Check(
            "601020 listed as authored but not yet landed on dev/master8",
            lambda ctx: "601020" in _report(ctx) and any(k in _report(ctx) for k in ("не дошло", "not landed", "not yet", "hasn't landed")),
        ),
        Check(
            "601050 excluded from not-landed because it's already Testing PROD",
            lambda ctx: "601050" not in _report(ctx).split("не дошло")[-1] if "не дошло" in _report(ctx) else "601050" not in _report(ctx),
        ),
        Check(
            "enriches at least one task with its current tracker status",
            lambda ctx: any(k in _report(ctx) for k in ("in progress backend", "testing prod", "to do backend")),
        ),
    ],
)
