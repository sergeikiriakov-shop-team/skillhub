"""task-docs scenario — a completed bug fix with minimal given facts, testing bug-vs-
feature classification, the exact naming pattern, the bug template's sections, and the
"do not invent" rule (don't fabricate details beyond what's given).
"""

from evals.harness import Check, Scenario


def _note(ctx) -> str:
    return (ctx.file("note.md") or "")


def _note_lower(ctx) -> str:
    return _note(ctx).lower()


scenario = Scenario(
    name="task_docs_bug_note",
    task_group="task-docs",
    description=(
        "task-docs: document a just-finished bug fix (task 508148) from minimal given facts "
        "— tests bug-vs-feature classification, the docs/<slug>_<id>.md naming pattern, the "
        "bug template's exact sections, and staying honest to only the given facts."
    ),
    task=(
        "You just finished task 508148 on branch `508148_fix_vat_rounding`. The one commit "
        "message is: \"fix VAT rounding when the seller has no currency for today\". The diff "
        "touched `lib/Invoice.php` (the rounding logic) and added a test in "
        "`tests/InvoiceTest.php`. Apply the `task-docs` skill.\n\n"
        "Write the note to {WORKSPACE}/note.md. As the VERY FIRST LINE of the file, state the "
        "exact real path (`docs/<filename>.md`) this note would be created at in the real repo."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote note.md", lambda ctx: ctx.file("note.md") is not None),
        Check(
            "first line states the real docs/ path with the task id",
            lambda ctx: _note(ctx).splitlines() and "docs/" in _note(ctx).splitlines()[0] and "508148" in _note(ctx).splitlines()[0],
        ),
        Check(
            "classifies this as a bug, using the bug template's sections",
            lambda ctx: "root cause" in _note_lower(ctx) and "how to verify" in _note_lower(ctx),
        ),
        Check(
            "does not use the feature template's sections instead",
            lambda ctx: "business logic" not in _note_lower(ctx),
        ),
        Check(
            "the root cause mentions rounding (consistent with the only given fact)",
            lambda ctx: "rounding" in _note_lower(ctx),
        ),
        Check(
            "lists both changed files",
            lambda ctx: "invoice.php" in _note_lower(ctx) and "invoicetest.php" in _note_lower(ctx),
        ),
        Check(
            "written in English",
            lambda ctx: not any(ch in _note(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
    ],
)
