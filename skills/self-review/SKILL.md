---
name: self-review
description: >
  Use to review your OWN finished change before anyone else sees it, with the review skill the team
  configured centrally in SkillHub. Triggers on "саморевью", "self-review", "проверь мой код перед
  ревью", "review my own diff", or right before `submit-for-review` / a push. It reads the team's
  self-review policy from the `skillhub` MCP (`get_self_review_policy`), fetches THAT skill
  (`get_skill`), applies it to your actual diff, and posts the findings back with
  `submit_self_review` — so the result is visible on the SkillHub review board and attaches to the
  peer review of the same task. Not a substitute for the lead's review, and it never fixes the code
  on its own unless you ask.
---

# Self-review — review your own change with the team's skill

The **skill that reviews you is chosen server-side**, not by you: an admin points each lane at a
catalog skill, so every developer's self-review runs the same way and the results are comparable.
Requires the `skillhub` MCP connected (see `connect-skillhub`); you post as your verified identity.

## 1. Read the policy
`get_self_review_policy()` → lanes (`default`, `backend`, `frontend`), each with the configured
`skill` and a `required` flag.
- Pick the lane from what the diff actually touches: PHP/SQL/backend → `backend`; React/JS/CSS/`.tpl`
  → `frontend`; mixed or unclear → run the lane that matches the bulk of the diff, and mention the
  rest in the summary.
- **Lane not configured** (`skill: null`): stop and tell the user an admin must set it
  (`PUT /api/self-reviews/policy`, or the Reviews page as admin). Do NOT silently substitute a skill
  of your own choosing — that defeats the point of a team-wide setting.

## 2. Fetch the reviewing skill
`get_skill(<skill id or name from the policy>)` → its `skill_md`. **Apply it as the instructions for
this review.** If it names subagents/tools you have (e.g. a PR-review orchestrator), follow it as
written; the point is that your self-review is done by the team's chosen method, not your default one.

## 3. Gather what to review
One git command at a time, no `cd`:
- **branch** — `git rev-parse --abbrev-ref HEAD` (should be the task branch `<id>/<slug>`).
- **repo** — `git remote get-url origin`, verbatim (ssh or https, either is fine). Pass it: findings
  deep-link to their line in this repo, and the team works in more than one, so without it every
  finding is just text.
- **commit_shas** — `git log --format=%H origin/master8..HEAD` (fall back to `git log --format=%H -n 20 HEAD`).
- **the diff** — `git diff origin/master8...HEAD` (same fallback). This is what the skill reviews.
- **task_ref** — the issue_logs id/link, from the branch name or the user.

If the working tree is dirty, say so and review the committed diff plus the uncommitted changes,
noting which is which.

## 4. Review and record findings
Produce findings in the shape SkillHub stores them, one per issue:
- `severity` — `blocker` (must not ship) · `major` (must fix) · `minor` · `nit`
- `title` — one line, the claim itself
- `file` + `line` — where, when you can localize it
- `detail` — why it is wrong / what breaks
- `suggestion` — the concrete fix

Be honest: a self-review that always comes back clean is worthless. If you find nothing, say what you
actually checked in the summary so the lead can judge the coverage. Do not invent findings either —
`nit`-only output is a legitimate result.

## 5. Post it
`submit_self_review(task_ref, findings, branch, commit_shas, repo, lane, model=<the model you ran
as>, summary=<what you covered and concluded>)`.
- Omit `verdict` — the service derives it: any `blocker`/`major` → `changes_needed`, else `pass`.
- Omit `skill` — the service records the lane's configured skill. Pass it ONLY if you deliberately
  applied a different one, so the record stays truthful.
- It attaches to your open peer review of the same task automatically (and to a later one when you
  run `submit-for-review`), appearing in its thread.
- Report back: the self-review id, the verdict, and the findings by severity.

## After
- **`changes_needed`** — fix the blockers/majors first, then re-run this skill so the board shows the
  clean pass. Fix the code only if the user asks; by default you report.
- **`pass`** — the task is ready for `submit-for-review`. When the policy is `required`, submitting
  without a self-review is rejected (409), so run this first.

## Once the findings are fixed — say what you did
After committing the fixes, call
`record_self_review_fixes(self_review_id, fixes=[{finding_index, commit_sha, note}, …])`.
- `finding_index` is the 0-based position in the findings you posted, so the note lands on the right
  point. `commit_sha` is the commit that closes it; omit it when the answer is not code (a test run,
  a deliberate non-issue) and say so in `note`.
- This is **additive**: it never edits the verdict, the severities or the findings. The record must
  keep showing what the skill originally caught — the value is in reading the before and the after
  together, and a review that quietly rewrites itself is worth nothing to whoever reads it later.
- Only report what you actually did. A fix **with a commit** counts as closed; a fix with only a
  note reads as an *answer* ("not addressed, because…") and is not counted as fixed — which is the
  honest split, so use it rather than inventing a commit. If a finding is simply still open, leave
  it without a fix at all: "3 of 9 fixed in code" is useful, a full green board that isn't true is
  worse than nothing.
- Re-running the whole self-review afterwards is the other half: fixes show *what you did*, a fresh
  run shows *whether it worked*.
