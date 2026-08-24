---
name: review-board
description: >
  Use (the LEAD, typically under `/loop`) to work the SkillHub review board: read the tasks whose
  self-review came back clean and sign them off, or send one back with a reason. Triggers on "review
  board", "очередь ревью", "что ждёт Approved", "check the review queue", or a `/loop review-board`.
  For each waiting task it reads the developer's own review — findings, what each fix closed, the
  earlier runs — via the `skillhub` MCP, presents it, and posts the lead's decision
  (`approve_task_review` / `return_task_review`). It never re-runs the review itself and never
  decides on its own: the sign-off is the lead's, and it asks before posting one.
---

# Review board — sign tasks off, or send them back (lead)

There is one review flow: the **developer** reviews their own change with the skill the team
configured (`self-review`), and that run puts the task on the board with its status. Your half is
the last step — read what the review found and either mark the task **Approved** or return it with
a reason. Requires the `skillhub` MCP connected and the reviewer role (`is_reviewer`) or admin.

## Each tick
1. **Fetch your queue:** `list_review_board(status="passed")` — tasks whose latest self-review came
   back clean and which are waiting for a sign-off. Empty → report "nothing waiting" and stop this
   tick; do not go looking for other work.
2. **For each task** (oldest first): `get_task_review(id)` → the task pointer (`task_ref`, `branch`,
   `repo`), the latest run with its full findings and fixes, and the earlier runs.

## Read the run before you decide
Approving without reading is the one thing that makes the board worthless — the status only says the
skill found nothing blocking, not that the change is right.

- **The findings and their fixes.** Each finding carries what the developer did about it: a fix with
  a commit is closed in code, a fix with only a note is an *answer* ("not addressed, because…").
  `open_finding_count` is how many nobody has answered at all.
- **The earlier runs.** A first run full of blockers followed by a clean one is the flow working. A
  first run that was already clean on a large diff is a reason to look harder, not less.
- **The diff itself, when the stakes call for it.** The board carries a pointer: `git fetch origin`,
  then `git diff origin/master8...origin/<branch>` in the repo the run names. Read it whenever the
  change is risky, the summary is thin, or the run found suspiciously little.

## Post the decision
Ask the user before posting either one — this is their sign-off, not yours.

- **Approve:** `approve_task_review(id)`. Rejected (409) when the task has no run, is already
  approved, or — when the policy requires a clean run — has not passed.
- **Send it back:** `return_task_review(id, comment)`. The comment is mandatory and is exactly what
  the author reads, so make it actionable: file:line, what is wrong, what to do. The task returns to
  `changes_needed` and their next self-review run clears it.

## Loop etiquette
- One decision per task per tick. An approved task leaves the queue; a returned one comes back only
  after the author re-runs their review.
- Do not edit the author's code, commit, or push. You read and decide.
- If you cannot read what you need (branch missing on origin, no run attached), say so — return the
  task with that as the comment rather than approving blind.
- Work the queue until it is empty, then let `/loop` idle until the next tick.
