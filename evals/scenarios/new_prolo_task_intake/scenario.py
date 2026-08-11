"""new-prolo-task — its OWN contract, not its successor's.

This skill is deprecated in favour of prolo-task-driver, and the existing `prolo_task_driver_intake`
scenario checks things this one never promised (a mandatory unit+integration-test readiness bar).
Judging it there would report a low score for not doing something it does not claim to do, so this
scenario tests exactly what its SKILL.md specifies:

- branch prep BEFORE reading the task: commit tracked changes with the verbatim message
  `Auto commit by Claude.` (never `git add -A`, never on master8/dev), then branch
  `issue_logs/<id>` off a freshly fetched `master8`;
- read exactly four fields — Business Goal, Currently, Expected, Checklists — and carry them
  VERBATIM ("take the text as is, do not rewrite or shorten it"), which is the rule the seeded page
  is built to catch: the Expected block contains a must-not-change invariant that a summarizing
  agent drops.

The page text is seeded rather than served, because the skill reads it through the browser — the
browser is what the sandbox cannot provide, and the rest of the contract is fully testable without it.
"""

import re

from evals.harness import Check, Scenario

PAGE = """Issue Log# 509968

Business Goal
Finance needs a complete daily order-export CSV for every order placed, including promotional/free-item orders, so nothing is missed in accounting reconciliation.

Currently
Orders where every line item is priced at 0 (free promo items) are silently missing from the CSV export entirely.

Expected
Every order in the export date range appears in the CSV, regardless of item price. An order's export row shows its real item count (never 0 when items exist). Cancelled orders must still be excluded from the export (existing behavior; do not change).

Checklists
- Confirm the export query does not filter on item price/subtotal > 0
- Add a regression case for 0-price line items
- Confirm cancelled orders still excluded
"""


def _prompt(ctx) -> str:
    return ctx.file("prompt.md") or ""


def _low(ctx) -> str:
    return _prompt(ctx).lower()


def _branch(ctx) -> str:
    return (ctx.file("branch.sh") or "").lower()


scenario = Scenario(
    name="new_prolo_task_intake",
    task_group="single-task-driver-deprecated",
    description=(
        "new-prolo-task: prepare the branch, then turn task 509968's page into its structured "
        "prompt — tests the verbatim-fields rule (an invariant buried in Expected must survive) "
        "and the branch contract (issue_logs/<id> off master8, tracked-only auto-commit)."
    ),
    task=(
        "You are running the `new-prolo-task` skill for "
        "https://www.prologistics.info/react/logs/issue_logs/509968/order-export-skips-zero-price-items\n\n"
        "The working tree has two modified tracked files and one untracked scratch file, and HEAD "
        "is currently on a feature branch (not master8/dev).\n\n"
        "The task page reads:\n\n"
        f"{PAGE}\n"
        "Do two things:\n"
        "1. Write the exact git commands you would run to prepare the branch, in order, to "
        "{WORKSPACE}/branch.sh (commands only, one per line).\n"
        "2. Write the structured prompt the skill produces to {WORKSPACE}/prompt.md."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote branch.sh", lambda ctx: _branch(ctx) != ""),
        Check("wrote prompt.md", lambda ctx: _prompt(ctx) != ""),
        Check(
            "commits tracked changes with the verbatim message",
            lambda ctx: "auto commit by claude." in _branch(ctx),
        ),
        Check(
            "uses commit -am, never git add -A (untracked files stay out)",
            lambda ctx: "-am" in _branch(ctx) and "add -a" not in _branch(ctx),
        ),
        Check(
            "refreshes master8 before branching off it",
            lambda ctx: "fetch origin master8" in _branch(ctx),
        ),
        Check(
            "branch is named issue_logs/<id> from the link",
            lambda ctx: re.search(r"issue_logs/509968", _branch(ctx)) is not None,
        ),
        Check(
            "branches off master8, not the current feature branch",
            lambda ctx: re.search(r"(switch -c|checkout -b)\s+issue_logs/509968\s+\S*master8", _branch(ctx))
            is not None,
        ),
        Check("carries the Business Goal field", lambda ctx: "business goal" in _low(ctx)),
        Check("carries the Currently field", lambda ctx: "currently" in _low(ctx)),
        Check("carries the Expected field", lambda ctx: "expected" in _low(ctx)),
        Check("carries the Checklists items", lambda ctx: "checklist" in _low(ctx)),
        Check(
            "keeps the buried invariant verbatim: cancelled orders stay excluded",
            lambda ctx: "cancelled orders must still be excluded" in _low(ctx),
        ),
        Check(
            "keeps the real-item-count requirement, not just the headline one",
            lambda ctx: "item count" in _low(ctx),
        ),
        Check(
            "all three checklist items survive, not just the first",
            lambda ctx: "regression case" in _low(ctx) and "price/subtotal" in _low(ctx),
        ),
    ],
)
