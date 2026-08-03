"""beliani-server-logs / -refined — shared plan scenario.

Both skills mandate: discover the log_name via list_server_log_names first
(never guess it), filter+paginate query_server_logs rather than pulling
everything, correlate via file/line to code, pick prod/dev (heap only if
asked), never pass `environment`, and stay read-only. One task reused for #5
(plain) and #25 (refined).
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="beliani_server_logs_plan",
    task_group="server-logs-query",
    description=(
        "beliani-server-logs (plain #5 / refined #25, shared fixture): plan how to investigate "
        "'checkout sometimes fails silently around 14:00-15:00 today on prod' via server logs — "
        "the exact log_name is unknown, so the discriminator is list-first discipline, "
        "filtered/paginated querying, file/line correlation, and staying read-only."
    ),
    task=(
        "You are applying the `beliani-server-logs` skill. Customers report that checkout "
        "sometimes fails silently, roughly between 14:00 and 15:00 TODAY, on PROD. You don't "
        "know which log_name holds checkout errors.\n\n"
        "Do NOT actually call the MCP here (there is no live target). Write your PLAN to "
        "{WORKSPACE}/plan.md: which MCP entry, the exact tool calls in order, the filters "
        "you'd apply, and how you'd use the result to find the faulty code."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "discovers the log_name via list_server_log_names rather than guessing one",
            lambda ctx: "list_server_log_names" in _plan(ctx),
        ),
        Check(
            "calls query_server_logs with a narrowing filter (time/date window)",
            lambda ctx: "query_server_logs" in _plan(ctx) and any(k in _plan(ctx) for k in ("14:", "date_from", "time =", "time=", "14-15", "time filter")),
        ),
        Check(
            "correlates the result to code via the file/line fields",
            lambda ctx: "file" in _plan(ctx) and "line" in _plan(ctx),
        ),
        Check(
            "picks the prod entry (not heap) since the symptom is on prod",
            lambda ctx: "beliani-server-logs-prod" in _plan(ctx) and "beliani-server-logs-heap" not in _plan(ctx),
        ),
        Check(
            "does not pass an environment parameter to the tools",
            lambda ctx: "environment=" not in _plan(ctx).replace(" ", "") and "environment =" not in _plan(ctx),
        ),
        Check(
            "plans to filter/paginate rather than pull an unbounded result set",
            lambda ctx: any(k in _plan(ctx) for k in ("limit", "offset", "has_more", "paginat")),
        ),
        Check(
            "stays read-only (no claim of having fixed/changed anything)",
            lambda ctx: not any(k in _plan(ctx) for k in ("i fixed", "i deployed", "i changed the code", "i patched")),
        ),
    ],
)
