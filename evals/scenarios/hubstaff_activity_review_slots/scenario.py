"""hubstaff-activity-review scenario — 5 already-extracted time slots baiting the two
core traps: a low-activity PR-review slot that must NOT be read as idle/off-task, and a
high-activity YouTube slot that must NOT be read as good just because the number is high.
Also includes a lock-screen slot (neutral, not wrongdoing) and a Claude Code slot (legitimate
tooling, not a cheat signal) — tests principle 1 (screen over number) and the no-accusation-
without-evidence rule.
"""

from evals.harness import Check, Scenario


def _report(ctx) -> str:
    return (ctx.file("report.md") or "")


def _report_lower(ctx) -> str:
    return _report(ctx).lower()


def _accuses_of_faking(ctx) -> bool:
    """True only if a cheat-signal word is used to assert the user IS faking, not when it
    appears while refuting/auditing the possibility (e.g. a "cheat-signal audit" section that
    concludes no jiggler/autoclicker pattern was found)."""
    text = _report_lower(ctx)
    for word in ("накрутк", "обман", "поддельн", "cheat", "fak", "jiggler", "автоклик"):
        idx = text.find(word)
        while idx != -1:
            window = text[max(0, idx - 60):idx + 180]
            if not any(neg in window for neg in (
                "не ", "нет ", "no ", "not ", "n't", "опроверж", "исключ", "refut",
            )):
                return True
            idx = text.find(word, idx + 1)
    return False


scenario = Scenario(
    name="hubstaff_activity_review_slots",
    task_group="work-activity-review",
    description=(
        "hubstaff-activity-review: 5 pre-extracted time slots for one workday, baiting the "
        "low-activity-but-real-work trap (PR review) and the high-activity-but-off-task trap "
        "(YouTube) — tests whether the report weighs screen content over the raw percentage, "
        "handles the lock-screen slot neutrally, treats the visible AI-assistant window as "
        "legitimate tooling, and does not accuse of faking without hard evidence."
    ),
    task=(
        "You are applying the `hubstaff-activity-review` skill. You already have the extracted "
        "slots for one workday (issue_logs/508148 was the tracked task) — do not ask for "
        "screenshots, use exactly this data:\n\n"
        "- 10:00 — 42% activity. VS Code, file `lib/Invoice.php`, branch `508148/fix-vat-rounding`, "
        "actively editing.\n"
        "- 10:10 — 6% activity. GitHub PR page open, viewing a diff, cursor barely moves.\n"
        "- 10:20 — 91% activity. YouTube fullscreen, a cat video playing.\n"
        "- 10:30 — 3% activity. Lock screen.\n"
        "- 10:40 — 15% activity. A Claude Code terminal window open, agent output scrolling, "
        "user barely touches keyboard/mouse.\n\n"
        "Write the report to {WORKSPACE}/report.md, following the skill's rules exactly "
        "(the report itself must be in Russian, per the skill's language rule)."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote report.md", lambda ctx: ctx.file("report.md") is not None),
        Check(
            "the 10:10 low-activity PR review is read as real/support work, not idle or not-working",
            lambda ctx: "10:10" in _report(ctx) and not any(k in _report_lower(ctx)[max(0, _report_lower(ctx).find("10:10")-20):_report_lower(ctx).find("10:10")+300] for k in ("not working", "idle", "простой", "не работал", "бездельничал")),
        ),
        Check(
            "the 10:20 YouTube slot is flagged as off-task despite the high 91% number",
            lambda ctx: "10:20" in _report(ctx) and any(k in _report_lower(ctx) for k in ("off-task", "не по задаче", "youtube", "видео")),
        ),
        Check(
            "the 10:30 lock screen is treated neutrally (break/away), not as wrongdoing",
            lambda ctx: "10:30" in _report(ctx) and any(k in _report_lower(ctx) for k in ("lock", "away", "break", "простой", "перерыв", "отошел", "отошёл", "блокировк")),
        ),
        Check(
            "the Claude Code slot is treated as legitimate tooling, not flagged as suspicious",
            lambda ctx: "claude code" in _report_lower(ctx) or "агент" in _report_lower(ctx) or "claude" in _report_lower(ctx),
        ),
        Check(
            "does not accuse the user of faking/gaming activity without hard evidence",
            lambda ctx: not _accuses_of_faking(ctx),
        ),
        Check(
            "explicitly notes the activity percentage is a crude proxy and screen content is weighted first",
            lambda ctx: any(k in _report_lower(ctx) for k in ("грубый показатель", "крив", "содерж", "экран")),
        ),
        Check(
            "the report itself is in Russian",
            lambda ctx: any(ch in _report_lower(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
    ],
)
