---
name: submit-for-review
description: >
  Use to hand a finished, deploy-ready Prologistics task to the team lead for review via the SkillHub
  review board, when the user says "отправь на ревью", "send for review", "готово, на ревью", or
  otherwise wants a completed task reviewed. Collects a POINTER to the work (task id/link, feature
  branch, commit SHAs, changed files, a summary, and what was verified) and submits it through the
  `skillhub` MCP `submit_for_review` tool — the code stays in git; the lead fetches the branch and
  reviews the real diff. Not for doing the task itself (that's green-loop / task-execute).
---

# Submit a task for review

Hand a **deploy-ready** backend task to the lead through the SkillHub review board. This sends a
**pointer + context**, not the code: the lead's Claude Code fetches the branch and reviews the real
diff. Requires the `skillhub` MCP connected (see `connect-skillhub`); you submit as your verified
identity.

## Preconditions
- The task is on its own feature branch `<id>/<slug>`, committed. If work is uncommitted or you are
  on `master8`/`dev`, stop and tell the user — submit only committed work on a task branch.
- The task is actually ready (ideally already driven by `green-loop`). If not clearly ready, ask.

## Gather the pointer (all from git + the task)
Run these against the task's branch (one git command at a time; no `cd`):
- **task_ref** — the issue_logs id or link (from the branch name `<id>/...` or ask the user).
- **branch** — `git rev-parse --abbrev-ref HEAD` (must be `<id>/<slug>`).
- **commit_shas** — the branch's own commits: `git log --format=%H origin/master8..HEAD` (fall back to
  `git log --format=%H -n 20 HEAD` if `origin/master8` is missing). Use full SHAs.
- **files** — changed files: `git diff --name-only origin/master8..HEAD` (same fallback).
- **summary** — what changed and why. Reuse the task's `docs/RELEASE_NOTES_backend.md` entry if
  green-loop wrote one; otherwise write 2-4 sentences from the diff + the task's acceptance criteria.
- **verified_notes** — what you verified and what you did NOT: `php -l`, a `php -r` harness, unit/
  integration tests, schema/rows via `beliani-*`, browser QA via `check-task` — and any gaps.

## Submit
Call `submit_for_review(task_ref, title, branch, commit_shas, summary, files, verified_notes)`.
- `title` — a short human title (task subject).
- On success, report the returned **review id** and status (`submitted`) and that it is queued for
  the lead. The lead picks it up via their `review-inbox` loop.

## After submitting
- Tell the user how to track it: their `review-status` loop (or ask "any review feedback?") surfaces
  the verdict. If the lead requests changes, fix them and re-run this flow's `resubmit_review` (or,
  once wired, green-loop will resubmit automatically).
- Do **not** push to master8/dev or change the tracker — this only puts the task on the review board.
