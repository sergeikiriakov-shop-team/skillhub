---
name: review-inbox
description: >
  Use (typically the LEAD, under `/loop`) to pull Prologistics tasks awaiting review from the SkillHub
  review board and review each with the repo's review skills. Triggers on "review inbox", "check the
  review queue", "проверь очередь ревью", or a `/loop review-inbox`. For each queued task it fetches
  the pointer (task, branch, commit SHAs), checks out/fetches the branch, reviews the real diff via
  `code-review` (and `check-task` for UI when relevant), then posts a verdict (approve /
  changes_requested + comments) back through the `skillhub` MCP. Only the lead (`is_reviewer`) may post
  verdicts.
---

# Review inbox — pull and review queued tasks (lead)

Poll the SkillHub review board for tasks awaiting review and review them. Designed to run under
`/loop` on the lead's machine (e.g. `/loop 10m review-inbox`). Requires the `skillhub` MCP connected;
posting a verdict requires the **reviewer/lead** role (`is_reviewer`) — an admin grants it.

## Each tick
1. **Fetch the queue:** `list_review_queue()` (reviews with status `submitted`). If empty, report
   "nothing to review" and stop this tick — do not do anything else.
2. **For each review** (oldest first): `get_review(review_id)` to read the pointer + the author's
   summary + `verified_notes` + the thread (including any prior verdicts/resubmits).

## Review one task (pointer -> real diff)
The board carries a pointer, not the code — review the actual branch:
1. **Refresh + fetch the branch:** `git fetch origin` then inspect `origin/<branch>` (or the local
   branch). Look at the branch's own commits/diff vs `origin/master8`
   (`git diff origin/master8...origin/<branch>`, `git show <sha>`), scoped to the `files`/`commit_shas`
   in the review.
2. **Review the diff** with the repo's review skill — invoke `code-review` (frontend diffs:
   `frontend-pr-review`). Check correctness, the task's acceptance criteria, `beliani-code-style`, and
   whether the author's `verified_notes` hold up. For UI-affecting tasks, optionally walk it with
   `check-task`.
3. **Decide.** Do NOT edit the author's code or push anything — you only review and report.

## Post the verdict
- **Approve:** `submit_review_result(review_id, "approve", comments)` — `comments` optional (e.g.
  "LGTM, verified X").
- **Changes requested:** `submit_review_result(review_id, "changes_requested", comments)` — `comments`
  are **required**: concrete, actionable findings (file:line, what's wrong, what to do). The author's
  `review-status` loop surfaces these and they fix + `resubmit_review`.

## Loop etiquette
- One verdict per review per tick; a review you already decided leaves the queue (it's no longer
  `submitted`) until the author resubmits.
- Never post a verdict without actually reading the diff. If you cannot fetch the branch (missing on
  origin), say so in `changes_requested` comments rather than approving blind.
- Keep going until the queue is empty, then let `/loop` idle until the next tick.
