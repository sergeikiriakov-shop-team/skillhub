"""Example sandbox scenario (domain-neutral): fetch a task from a fake API and write a plan.

Exercises a generic "turn a tracker task into a plan" skill without any real tracker: the fake
service serves one task; the skill must fetch it and produce a plan covering every checklist item.
This is the template for authoring new scenarios — copy the folder and edit."""

from evals.harness import Check, Scenario

TASK_JSON = {
    "id": 1,
    "title": "Add a due-date filter to the issue list",
    "goal": "Operators can narrow the issue list by due date.",
    "expected": "A due-date control appears in the filters and combines with the existing filters.",
    "checklist": [
        "a due-date control appears",
        "the filter state syncs to the URL",
        "issues with a null due date are excluded, not crashed on",
    ],
}


def _plan(ctx) -> str:
    return (ctx.file("plan.md") or "").lower()


scenario = Scenario(
    name="task_fetch_and_plan",
    description="Fetch task #1 from the fake task API and write a plan covering its checklist.",
    task=(
        "Using the task API at {FAKE_URL}, fetch task #1 (GET {FAKE_URL}/tasks/1). Read its goal, "
        "expected result and checklist, then write {WORKSPACE}/plan.md: restate the goal in one "
        "line and list concrete implementation steps that cover EVERY checklist item. Do not "
        "invent requirements that are not in the task."
    ),
    routes=[
        {"method": "GET", "path_regex": r"/tasks/1", "status": 200, "json": TASK_JSON},
    ],
    workspace_seed={},
    checks=[
        Check("fetched task #1 from the API", lambda ctx: ctx.called("GET", r"/tasks/1")),
        Check("wrote plan.md", lambda ctx: ctx.file("plan.md") is not None),
        Check("plan restates the goal (mentions due date / filter)", lambda ctx: "due date" in _plan(ctx) or "filter" in _plan(ctx)),
        Check("covers checklist item: URL sync", lambda ctx: "url" in _plan(ctx)),
        Check("covers checklist item: null due date", lambda ctx: "null" in _plan(ctx)),
    ],
)
