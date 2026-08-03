"""task-time-note scenario — a tiny diff with a large hidden investigation behind it,
testing the "small diff does not mean a small number" rule and the exact 3-line
Russian output block, plus the never-invent-a-number rule.
"""

from evals.harness import Check, Scenario


def _block(ctx) -> str:
    return (ctx.file("block.md") or "")


def _block_lower(ctx) -> str:
    return _block(ctx).lower()


scenario = Scenario(
    name="task_time_note_block",
    task_group="task-time-note",
    description=(
        "task-time-note: size a task whose diff is tiny (5 lines) but whose commit body "
        "describes a real multi-file root-cause investigation and a bounce-back from Testing "
        "PROD — tests whether the agent's own estimate follows the investigation, not the diff "
        "size, and produces the exact 3-line Russian block."
    ),
    task=(
        "You already read ticket 555001's page: **Backend Estimation (h)** = \"6 ч\". The "
        "**Timer/Estimations** block for the backend-assigned developer shows **Totals: "
        "03:20:00**. The commit is a 5-line fix in one file, but its commit body says: "
        "\"root-caused by tracing the discount-application order through PricingEngine.php, "
        "CartService.php, and OrderTotals.php after a bounce-back from Testing PROD (2nd round) "
        "uncovered the pricing was applied before a currency conversion.\"\n\n"
        "Apply the `task-time-note` skill and write the three-line block to {WORKSPACE}/block.md."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote block.md", lambda ctx: ctx.file("block.md") is not None),
        Check(
            "states the allocated estimate (6h) on the Выделено line",
            lambda ctx: "выделено" in _block_lower(ctx) and "6" in _block(ctx),
        ),
        Check(
            "gives an agent estimate with a stated reason",
            lambda ctx: "ориентировочная оценка" in _block_lower(ctx),
        ),
        Check(
            "the reason cites the investigation/bounce-back, not just the diff size",
            lambda ctx: any(k in _block_lower(ctx) for k in ("root-caus", "root caus", "bounce", "investigat", "трасс", "перепро", "возврат")),
        ),
        Check(
            "states the actually-tracked time (03:20)",
            lambda ctx: "фактически затрекано" in _block_lower(ctx) and ("03:20" in _block(ctx) or "3:20" in _block(ctx)),
        ),
        Check(
            "the block itself is in Russian",
            lambda ctx: any(ch in _block_lower(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
    ],
)
