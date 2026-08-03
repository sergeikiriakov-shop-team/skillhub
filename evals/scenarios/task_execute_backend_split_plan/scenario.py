"""task-execute scenario — a task with explicit Backend/Frontend fields naming different
files, plus a currently-checked-out unrelated branch, testing the backend-only split (skip
frontend, list it, don't build it), the branch-off-master8 rule (never off the current
branch), the "prove the mechanism first" gate, and the stop-at-commit rule (no push/PR).
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


def _branches_correctly(ctx) -> bool:
    """master8 named as the branch base for 555002, and no phrase saying the branch was
    created off the currently-checked-out 508148/fix-vat-rounding branch instead."""
    text = _plan(ctx)
    if "master8" not in text or "555002" not in text:
        return False
    bad_phrases = (
        "off 508148", "off the current branch", "off current branch",
        "from 508148", "based on 508148", "off fix-vat-rounding",
        "stay on 508148", "reuse 508148", "off my current branch",
    )
    return not any(p in text for p in bad_phrases)


def _stops_at_commit(ctx) -> bool:
    """"commit" present, and at least one of push/merge/PR is explicitly addressed as
    negated (e.g. "no git push", "never merge", "no PR") — with none of them recommended
    as an action actually taken."""
    text = _plan(ctx)
    if "commit" not in text:
        return False
    found_negated = False
    for word in ("push", "merge", " pr", "pull request"):
        idx = text.find(word)
        while idx != -1:
            window = text[max(0, idx - 30):idx]
            if any(neg in window for neg in ("no ", "not ", "never ", "n't", "stop", "не ", "нет ")):
                found_negated = True
            else:
                return False
            idx = text.find(word, idx + 1)
    return found_negated


scenario = Scenario(
    name="task_execute_backend_split_plan",
    task_group="task-execute",
    description=(
        "task-execute: task 555002 names CartService.php as Backend and CartSummary.jsx as "
        "Frontend, while the repo is currently on an unrelated branch (508148/fix-vat-rounding) "
        "— tests the backend-only split, branching fresh off master8 (never off the current "
        "branch), proving the mechanism before fixing, and stopping at the commit."
    ),
    task=(
        "You are applying the `task-execute` skill. Task 555002: \"Discount total shows wrong "
        "value for multi-currency carts at checkout.\" Backend field: `CartService.php` "
        "(recalculation logic). Frontend field: `CartSummary.jsx` (display formatting). No "
        "branch for this task exists yet. The repository is currently checked out on "
        "`508148/fix-vat-rounding` — a different, unrelated task's branch.\n\n"
        "Do NOT actually read the task, touch git, or write code. Write your PLAN to "
        "{WORKSPACE}/plan.md: what you will do backend-side, what you will explicitly skip and "
        "why, which branch you will create and from what base, and what you will and will not do "
        "at the end, following the skill's rules exactly."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "does backend-only work on CartService.php",
            lambda ctx: "cartservice.php" in _plan(ctx),
        ),
        Check(
            "explicitly skips CartSummary.jsx as frontend and lists it rather than building it",
            lambda ctx: "cartsummary.jsx" in _plan(ctx) and any(k in _plan(ctx) for k in ("skip", "out of scope", "not build", "its own branch", "frontend", "не трога", "пропущ")),
        ),
        Check(
            "creates the branch fresh off master8, not off the currently checked-out branch",
            _branches_correctly,
        ),
        Check(
            "proves the mechanism before writing the fix, not just arguing it",
            lambda ctx: any(k in _plan(ctx) for k in ("prove", "reproduce", "demonstrate", "harness", "доказ", "воспроизв")),
        ),
        Check(
            "reads the task via the Prolo UI, not the restricted API",
            lambda ctx: "issue_logs" in _plan(ctx) and "prologistics.info" in _plan(ctx),
        ),
        Check(
            "stops at the commit: explicitly states it will not push, merge, or open a PR",
            _stops_at_commit,
        ),
        Check(
            "never commits on master8/dev directly",
            lambda ctx: not any(k in _plan(ctx) for k in ("commit on master8", "commit to master8", "commit on dev", "commit to dev")),
        ),
    ],
)
