"""commit-text scenario — a genuinely complex 3-part change, to see whether the
model follows the skill's exact shape (task-ref line, ONE-phrase summary line,
detail bullets ONLY for a large/complex commit and never restating the summary)
rather than either cramming everything into a run-on line 2 or firing off git
commands (the skill is explicitly text-only — it never runs git).
"""

from evals.harness import Check, Scenario


def _msg(ctx) -> str:
    return ctx.file("commit_message.txt") or ""


def _msg_lower(ctx) -> str:
    return _msg(ctx).lower()


def _lines(ctx):
    return [l for l in _msg(ctx).splitlines() if l.strip()]


scenario = Scenario(
    name="commit_text_message",
    task_group="commit-message-authoring",
    description=(
        "commit-text over a genuinely complex 3-part change (batch reconciliation "
        "refactor + retry/backoff + an off-by-one fix) — tests the exact shape: task-ref "
        "line 1, ONE-phrase summary line 2, detail bullets only because this commit "
        "qualifies as large/complex and none of them restating line 2, English, and "
        "never emitting an actual git command since the skill only produces text."
    ),
    task=(
        "You are applying the `commit-text` skill. Task link: "
        "https://www.prologistics.info/react/logs/issue_logs/521300/reconcile_invoice_totals\n\n"
        "What changed (from the staged diff): refactored invoice reconciliation to "
        "batch-process rows instead of per-row processing; added a retry with backoff "
        "for payment-gateway timeouts; fixed an off-by-one bug that double-counted the "
        "last invoice in a batch.\n\n"
        "Write the commit message to {WORKSPACE}/commit_message.txt."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote commit_message.txt", lambda ctx: ctx.file("commit_message.txt") is not None),
        Check(
            "line 1 is the task reference",
            lambda ctx: len(_lines(ctx)) >= 1 and ("issue_logs/521300" in _lines(ctx)[0]),
        ),
        Check(
            "line 2 is a single one-phrase summary, not a run-on multi-sentence paragraph",
            lambda ctx: len(_lines(ctx)) >= 2 and _lines(ctx)[1].count(".") <= 1 and len(_lines(ctx)[1]) < 140,
        ),
        Check(
            "adds detail bullets for this large/complex 3-part change",
            lambda ctx: any(l.strip().startswith("-") for l in _lines(ctx)[2:]),
        ),
        Check(
            "at least 2 distinct detail bullets (batch + retry + off-by-one are 3 separate facts)",
            lambda ctx: sum(1 for l in _lines(ctx) if l.strip().startswith("-")) >= 2,
        ),
        Check(
            "written in English",
            lambda ctx: not any(ch in _msg(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
        Check(
            "stays text-only: never emits an actual git command",
            lambda ctx: not any(k in _msg_lower(ctx) for k in ("git commit", "git push", "git add", "git stage")),
        ),
    ],
)
