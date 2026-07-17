---
name: review-status
description: >
  Use (typically a DEVELOPER, under `/loop`) to check the outcome of tasks you submitted to the
  SkillHub review board. Triggers on "review status", "any review feedback?", "что там с ревью",
  or a `/loop review-status`. Surfaces your reviews that need action — `changes_requested` (with the
  lead's comments) and `approved` — via the `skillhub` MCP. v1 is NOTIFY-ONLY: it reports the verdict
  and the next step (fix + resubmit, or acknowledge); it does not change code itself.
---

# Review status — check feedback on your submitted tasks (developer)

Poll the SkillHub review board for verdicts on tasks you submitted. Designed to run under `/loop` on
a developer's machine (e.g. `/loop 15m review-status`). Requires the `skillhub` MCP connected.

## Each tick
1. **Needs your action:** `list_my_reviews(status="changes_requested")` and
   `list_my_reviews(status="approved")`.
2. If both are empty, report "no review feedback" and stop this tick.
3. For each item, `get_review(review_id)` to read the latest verdict + the lead's comments from the
   thread.

## Report (notify only — do NOT change code in v1)
- **changes_requested:** show the task, the branch, and the lead's comments verbatim, then state the
  next step: fix the points on the task's branch and run `resubmit_review(review_id, commit_shas,
  note)` — or, once green-loop is wired to the board, re-run `green-loop` on the task and it will
  apply the fixes and resubmit. Ask the user whether to proceed with fixes now; do not start editing
  on your own from this loop.
- **approved:** congratulate briefly and offer to close it: `ack_review(review_id)` (an approved
  review becomes `done` on ack). Production rollout / tracker moves remain the user's separate step.

## Loop etiquette
- Notify once per new/changed verdict; don't re-nag about the same unchanged item every tick (track
  what you already surfaced this session).
- This skill never posts verdicts, edits code, pushes, or touches the tracker — it only reports and
  hands off to `resubmit_review` / `ack_review` (or green-loop) on the user's go-ahead.
