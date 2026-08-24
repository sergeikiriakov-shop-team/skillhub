---
name: review-status
description: >
  Use (a DEVELOPER, typically under `/loop`) to check where your tasks stand on the SkillHub review
  board — what the lead sent back, what is still waiting for their sign-off, and what got Approved.
  Triggers on "review status", "что там с ревью", "any review feedback?", or a `/loop review-status`.
  Reads your own rows via the `skillhub` MCP (`list_review_board(mine=true)`) and reports the next
  step: fix and re-run `self-review`, or wait, or done. NOTIFY-ONLY — it does not change code, and it
  never posts a verdict.
---

# Review status — where your tasks stand (developer)

One flow: your own `self-review` run puts a task on the board and sets its status; the lead then
marks it **Approved** or sends it back with a comment. This skill tells you which of those happened.
Designed to run under `/loop` on a developer's machine (e.g. `/loop 15m review-status`). Requires the
`skillhub` MCP connected.

## Each tick
1. **Your rows:** `list_review_board(mine=true)` — every task you self-reviewed, with its status.
2. If nothing has moved since you last reported, say so and stop this tick.
3. For anything that needs attention, `get_task_review(id)` for the lead's comment and the latest
   run's findings.

## Report (notify only — do NOT change code)
- **`changes_needed`** — the task is with you. Two ways it got there, and they read differently:
  - the run itself found blockers/majors → show them (severity · file:line · what to do);
  - the lead returned it → `lead_comment` is why, quote it verbatim.

  Next step either way: fix the points on the task's branch, commit, record what each fix closed
  (`record_self_review_fixes`), then **re-run `self-review`** — a fresh run is what moves the status.
  Ask the user whether to start fixing now; do not begin editing on your own from this loop.
- **`passed`** — clean run, waiting for the lead's sign-off. Nothing for you to do; say how long it
  has been waiting so the user can nudge if it is stale.
- **`approved`** — done, with who approved it and when. Deployment and the tracker remain the user's
  separate step.

## Loop etiquette
- Notify once per change; don't re-nag about the same unchanged row every tick (track what you
  already surfaced this session).
- This skill never approves, returns, edits code, pushes, or touches the tracker. It reports and
  hands off to `self-review` on the user's go-ahead.
