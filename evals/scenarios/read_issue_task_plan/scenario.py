"""read-issue-task scenario — the code word triggers a full read with no scope
re-ask, split across the skill's own named DB tables (schema-confirmed first)
and the ACL-gated UI for comments.
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="read_issue_task_plan",
    task_group="issue-task-read",
    description=(
        "read-issue-task: the user says the code word 'issue_logs 512755' — plan how to read "
        "the full task (no live tools). Discriminates on not re-asking for scope, naming the "
        "skill's own DB tables (schema-confirmed first), and reading comments via the ACL-gated "
        "UI rather than guessing a DB comment table."
    ),
    task=(
        "You are applying the `read-issue-task` skill. The user just said: \"issue_logs 512755\". "
        "Do NOT actually call any tool here (there is no live target). Write your PLAN to "
        "{WORKSPACE}/plan.md: what you will read, via which tables/tools, and in what order, "
        "following the skill's rules exactly."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "reads the full task without re-asking for scope",
            lambda ctx: any(k in _plan(ctx) for k in ("without re-asking", "without asking", "no need to ask", "not ask for scope", "read the full task", "read the whole task", "end to end", "no scope question", "no scope clarification", "fixed by the code word")),
        ),
        Check(
            "names the task-body/checklist/activity tables",
            lambda ctx: "issuelog" in _plan(ctx) and "issue_checklist" in _plan(ctx) and "issue_timestamp" in _plan(ctx),
        ),
        Check(
            "confirms structure via the db-schema tool before querying",
            lambda ctx: "db-schema" in _plan(ctx) or "mcp-db-schema" in _plan(ctx),
        ),
        Check(
            "reads comments via the UI, not a guessed DB table",
            lambda ctx: "ui" in _plan(ctx) and "comment" in _plan(ctx) and not any(k in _plan(ctx) for k in ("comment table", "query the comments", "comments table", "issue_comment")),
        ),
        Check(
            "states why comments go through the UI (ACL-gated)",
            lambda ctx: "acl" in _plan(ctx),
        ),
    ],
)
