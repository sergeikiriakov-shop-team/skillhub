"""check-task scenario — a PM-mode request (no repository) naming the shop but not the
environment, testing the dev-default (never master8), reading the task via the Prolo
admin URL even though the check itself targets the shop, the no-chooser browser-connect
sequence, and not touching git in PM mode.
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


def _touches_git(ctx) -> bool:
    """True only if a git command is used affirmatively, not just named while disclaiming it
    (e.g. "no `git log`, no `git show`" explicitly stating PM-mode git avoidance)."""
    text = _plan(ctx)
    for cmd in ("git log", "git diff", "git rev-parse", "git show"):
        idx = text.find(cmd)
        while idx != -1:
            window = text[max(0, idx - 15):idx]
            if not any(neg in window for neg in ("no ", "not ", "never ", "n't", "avoid")):
                return True
            idx = text.find(cmd, idx + 1)
    return False


scenario = Scenario(
    name="check_task_pm_plan",
    task_group="ui-task-qa",
    description=(
        "check-task: a PM (no repository) asks to verify task 492599's checkout Add-to-Cart fix "
        "on the shop, without naming an environment — tests the dev-default (never master8), "
        "reading the task via the Prolo admin URL even for a shop check, and PM-mode git "
        "avoidance."
    ),
    task=(
        "You are applying the `check-task` skill. A PM (there is NO local git repository "
        "available) asks: \"Please verify task 492599 works — it's about the checkout Add to "
        "Cart button on the shop.\" No environment was specified.\n\n"
        "Do NOT actually connect to a browser or run any tool here. Write your PLAN to "
        "{WORKSPACE}/plan.md: the target, the environment, how you'll read the task, how you'll "
        "connect to the browser, and the check steps, following the skill's rules exactly."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "targets the shop (explicitly named), not the admin default",
            lambda ctx: "shop" in _plan(ctx),
        ),
        Check(
            "defaults the environment to dev, never master8",
            lambda ctx: "dev" in _plan(ctx) and not any(k in _plan(ctx) for k in ("default to `master8`", "default to master8", "defaults to master8", "defaults to `master8`", "using master8", "target: master8", "environment: master8")),
        ),
        Check(
            "reads the task via the Prolo admin URL even though checking the shop",
            lambda ctx: "issue_logs" in _plan(ctx) and any(k in _plan(ctx) for k in ("prolo", "prologistics.info")),
        ),
        Check(
            "stays in PM mode: does not touch git",
            lambda ctx: not _touches_git(ctx),
        ),
        Check(
            "connects to the browser without forcing a chooser (no list_connected_browsers first)",
            lambda ctx: "tabs_context_mcp" in _plan(ctx),
        ),
        Check(
            "does not ask a clarifying question since both the id and description were given",
            lambda ctx: not any(k in _plan(ctx) for k in ("could you provide", "please provide a task link", "can you clarify", "what environment would you like")),
        ),
    ],
)
