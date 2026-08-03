"""branch-cleanup STRICT report scenario — the skill's own documented correctness traps.

branch-cleanup's body names several hard-won edge cases explicitly (task-id extraction from
anywhere in the name, ignoring short/variant digit runs, multi-match -> ambiguous -> keep, "Done
prod" alone is not closure, and the "issue.closed is ALWAYS false" trap). This scenario bakes each
one into a fake branch list + fake tracker responses, so a faithful run must get every one right —
a naive run that just checks "is status truthy" or "is the branch in Done prod" will mis-file at
least one. Report-only (no --apply): nothing should be deleted or pushed.
"""

from evals.harness import Check, Scenario

CURRENT_USER_EMAIL = "sergei.kiriakov@beliani.net"
CURRENT_USER_NAME = "Sergei Kiriakov"

BRANCHES = [
    # (name, committer, task ids embedded)
    "601234_fix-vat-rounding",
    "602100_add-export-filter",
    "603050_refactor-cart",
    "feature/checkout-604400-final",
    "605600_no_4714/fallback",
    "607700_608800/merge-fix",
    "mobile_pick_41_refactor",
    "609900_shipping-calc",
]

BRANCH_LIST_TEXT = (
    "refs/heads/601234_fix-vat-rounding\n"
    "refs/heads/602100_add-export-filter\n"
    "refs/heads/603050_refactor-cart\n"
    "refs/heads/feature/checkout-604400-final\n"
    "refs/heads/605600_no_4714/fallback\n"
    "refs/heads/607700_608800/merge-fix\n"
    "refs/heads/mobile_pick_41_refactor\n"
    "refs/heads/609900_shipping-calc\n"
)

COMMITTERS_TEXT = (
    "601234_fix-vat-rounding: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "602100_add-export-filter: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "603050_refactor-cart: Ivan Petrov <ivan.petrov@example.com>\n"
    "feature/checkout-604400-final: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "605600_no_4714/fallback: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "607700_608800/merge-fix: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "mobile_pick_41_refactor: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
    "609900_shipping-calc: Sergei Kiriakov <sergei.kiriakov@beliani.net>\n"
)

TRACKER_JSON = {
    "601234": {"status": "close", "closed": False, "column": "Done prod", "title": "Fix VAT rounding on partial refund"},
    "602100": {"status": "open", "closed": False, "column": "Done prod", "title": "Add export filter for shop 9"},
    "603050": {"status": "close", "closed": False, "column": "Done prod", "title": "Refactor cart discount calc"},
    "604400": {"status": "close", "closed": False, "column": "Done prod", "title": "Checkout: fix duplicate charge"},
    "605600": {"status": "close", "closed": False, "column": "Done prod", "title": "Fallback shipping rate"},
    "607700": {"status": "close", "closed": False, "column": "Done prod", "title": "Merge cart+refund logic (part A)"},
    "608800": {"status": "open", "closed": False, "column": "Testing DEV", "title": "Merge cart+refund logic (part B)"},
    "609900": {"status": "open", "closed": True, "column": "In progress backend", "title": "Shipping calc: add zone C"},
}


def _report(ctx) -> str:
    return (ctx.file("report.md") or "").lower()


scenario = Scenario(
    name="branch_cleanup_report",
    task_group="git-branch-cleanup",
    description=(
        "branch-cleanup report-only run over 8 branches encoding the skill's own documented traps: "
        "a task id not at the start of the name, a short/variant digit run to ignore, a two-task "
        "ambiguous match (must be kept, never deleted), a 'Done prod' column with status still "
        "open (not closure), the 'issue.closed is always false/misleading' trap, an owner "
        "mismatch, and a branch with no task id at all (ignored)."
    ),
    task=(
        "You are running the `branch-cleanup` skill in REPORT-ONLY mode (no --apply token). "
        f"Current user: name=\"{CURRENT_USER_NAME}\", email=\"{CURRENT_USER_EMAIL}\" (from git config).\n\n"
        "Local branches (`git for-each-ref --format='%(refname:short)' refs/heads`):\n"
        f"{BRANCH_LIST_TEXT}\n"
        "Last committer per branch (`git log -1 --format='%cn <%ce>' <branch>`):\n"
        f"{COMMITTERS_TEXT}\n"
        "Tracker lookups (`fetch_issue_log` via the beliani-issue-log MCP), keyed by task id — "
        "call GET {FAKE_URL}/issue_logs/<id> for each unique 5-6 digit id you extract from a "
        "branch name:\n\n"
        "Build the three report tables (candidates / kept-with-reason / ignored) and the summary "
        "line, exactly as the skill specifies, and write them to {WORKSPACE}/report.md. Report mode "
        "only: delete nothing, push nothing."
    ),
    routes=[
        {"method": "GET", "path_regex": rf"/issue_logs/{tid}(?!\d)", "status": 200, "json": data}
        for tid, data in TRACKER_JSON.items()
    ],
    workspace_seed={},
    checks=[
        Check("wrote report.md", lambda ctx: ctx.file("report.md") is not None),
        Check(
            "candidates the real closed-and-mine branch (601234)",
            lambda ctx: "601234" in _report(ctx) and "candidate" in _report(ctx),
        ),
        Check(
            "candidates the branch whose task id is NOT at the start (604400)",
            lambda ctx: "604400" in _report(ctx) and "candidate" in _report(ctx),
        ),
        Check(
            "candidates 605600 without being fooled by the short trailing '4714' run",
            lambda ctx: "605600" in _report(ctx) and "candidate" in _report(ctx) and "4714" not in _report(ctx).replace("no_4714", ""),
        ),
        Check(
            "keeps 602100 because 'Done prod' alone is not closure (status still open)",
            lambda ctx: "602100" in _report(ctx)
            and any(k in _report(ctx) for k in ("not closed", "still open", "status=open", "status open", "done prod")),
        ),
        Check(
            "keeps 603050 for an owner mismatch (not the current user)",
            lambda ctx: "603050" in _report(ctx)
            and any(k in _report(ctx) for k in ("owner", "not mine", "ivan petrov", "not the current user")),
        ),
        Check(
            "flags the two-task branch (607700/608800) as AMBIGUOUS and keeps it",
            lambda ctx: "ambiguous" in _report(ctx) and "607700" in _report(ctx) and "608800" in _report(ctx),
        ),
        Check(
            "keeps 609900 despite closed=true, going by status (open) not the closed boolean",
            lambda ctx: "609900" in _report(ctx)
            and any(k in _report(ctx) for k in ("closed is always false", "closed=false", "closed boolean", "ignore issue.closed", "status", "not closed")),
        ),
        Check(
            "puts the no-task-id branch (mobile_pick_41) in the ignored list, not a candidate",
            lambda ctx: "mobile_pick_41" in _report(ctx) and "ignored" in _report(ctx),
        ),
        Check(
            "stays report-only: no deletion or push performed",
            lambda ctx: not any(k in _report(ctx) for k in ("deleted branch", "pushed --delete", "i deleted", "branches deleted:", "git branch -d", "git push origin --delete")),
        ),
    ],
)
