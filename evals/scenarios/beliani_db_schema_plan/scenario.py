"""beliani-db-schema / -refined — shared plan scenario.

Both skills mandate the same discipline: never guess structure, use
find_tables/find_columns → get_table_schema → get_table_indexes (before a
SQL/perf change) → DDL tools only if needed; pick prod/dev, never
self-switch to heap; never pass `environment`; structure only, not rows. One
task is reused for #4 (plain) and #24 (refined).

No live MCP call here (kept reproducible/offline, same convention as the
sql-query plan scenarios this session) — the task asks for the PLAN, with a
deliberately ambiguous column name to force find_columns/find_tables instead
of jumping straight to get_table_schema.
"""

from evals.harness import Check, Scenario


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="beliani_db_schema_plan",
    task_group="db-schema-lookup",
    description=(
        "beliani-db-schema (plain #4 / refined #24, shared fixture): plan the schema lookups "
        "needed before writing a filtered UPDATE on the `shipment` table, where the exact "
        "column storing the tracking number is NOT given and must be found, not guessed."
    ),
    task=(
        "You are applying the `beliani-db-schema` skill. You need to write a query that finds "
        "a shipment row by its tracking number and updates 3 fields on it (status, "
        "delivered_at, carrier_ref) — you don't know the exact column name that stores the "
        "tracking number on the `shipment` table, nor whether it's uniquely indexed.\n\n"
        "Do NOT actually call the MCP here (there is no live target). Instead, write your PLAN "
        "to {WORKSPACE}/plan.md: which MCP entry you'd use, the exact tools you'd call and in "
        "what order, and what each call is meant to establish."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check(
            "starts from find_tables/find_columns since the exact column name is unknown",
            lambda ctx: "find_columns" in _plan(ctx) or "find_tables" in _plan(ctx),
        ),
        Check(
            "follows with get_table_schema on the shipment table",
            lambda ctx: "get_table_schema" in _plan(ctx) and "shipment" in _plan(ctx),
        ),
        Check(
            "separately checks indexes before the SQL/perf change",
            lambda ctx: "get_table_indexes" in _plan(ctx),
        ),
        Check(
            "picks prod or dev as the primary entry",
            lambda ctx: any(k in _plan(ctx) for k in ("beliani-db-schema-prod", "beliani-db-schema-dev")),
        ),
        Check(
            "does not invent/guess the tracking-number column name as fact",
            lambda ctx: not any(k in _plan(ctx) for k in ("the column is called", "the column name is", "it's stored in the column")),
        ),
        Check(
            "does not pass an environment parameter to the tools",
            lambda ctx: "environment=" not in _plan(ctx).replace(" ", "") and "environment =" not in _plan(ctx),
        ),
        Check(
            "stays structure-only (does not plan to fetch actual row data through this MCP)",
            lambda ctx: not any(k in _plan(ctx) for k in ("fetch the row", "read the row data", "select the actual row", "get the row values")),
        ),
    ],
)
