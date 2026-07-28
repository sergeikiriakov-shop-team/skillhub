---
name: sandbox-eval
description: >-
  Use to TEST or A/B-COMPARE Claude Code skills in the local sandbox — e.g. an original skill vs a
  SkillHub-refined/synthesized version — by actually running them against fixtures + a fake service
  and scoring effectiveness. Trigger when the user says "test this skill", "прогони скилл в
  песочнице", "сравни green-loop и его refined-версию", "evaluate the skill on stubs", or asks
  whether a refined skill really behaves better. Runs entirely in the current console Claude Code
  (no API key, no headless); the Python harness in `evals/` only stands up the fake environment and
  scores the result.
---

# sandbox-eval — run a skill against fixtures + a fake service and score it

The harness (`evals/`, stdlib-only Python) provides the *stage*: fixtures, a recording fake
service, and effectiveness checks. **You** (this Claude Code session) are the *runner*: you execute
the skill under test against that stage, exactly as a developer would when trying a skill on their
own code. Then the harness scores what actually happened.

## Hard guardrail
During a trial you act **only** within the temp workspace and against the fake service URL. Never
touch real systems: no real git push/deploy, no real MCP/DB, no network beyond `{FAKE_URL}`. The
whole point is a safe, throwaway environment.

## Inputs
- A **scenario** name from `evals/scenarios/` (e.g. `task_fetch_and_plan`).
- One or more **skills under test**, each a `(label, SKILL.md)` — e.g. `("green-loop", <md>)` and
  `("prolo-task-driver", <md>)` for an A/B. Get the `SKILL.md` from the repo, from SkillHub
  (`get_skill` → `skill_md`), or the user pastes it.

## Procedure (repeat per skill version, then compare)
Let `RUN=.sandbox/<scenario>` and, per label, `WS=$RUN/ws-<label>`.

For each `(label, skill_md)`:
1. **Start the fake service** in the background (it truncates its call log on start, so each run is
   isolated): `python -m evals.fake_service --run-dir $RUN --port 0`. Read the printed
   `FAKE_SERVICE_URL=...` (also in `$RUN/url.txt`) → that is `{FAKE_URL}`.
2. **Set up the stage**: `python -m evals.harness setup <scenario> --run-dir $RUN --workspace $WS`.
   It seeds fixtures and prints the `TASK` (with `{FAKE_URL}`/`{WORKSPACE}` placeholders).
3. **Run the skill under test**: follow `skill_md` as if it had just triggered, to accomplish the
   `TASK` — substitute `{FAKE_URL}` and `{WORKSPACE}=$WS`. Use ordinary tools (curl to `{FAKE_URL}`,
   read/write files under `$WS`). Obey the guardrail above.
4. **Score**: `python -m evals.harness check <scenario> --run-dir $RUN --workspace $WS --label <label>`
   → prints a ✓/✗ scorecard and writes `result-<label>.json`.
5. **Stop the fake service** (kill the background process from step 1).

Then **A/B**: `python -m evals.harness compare --run-dir $RUN` → a side-by-side check matrix +
scores. Report which version passed more checks and where they differ; that is the empirical
evidence (complementing the SkillHub rubric score). Optionally record it back to SkillHub as trial
evidence for the task_group (future).

## Notes & honest limits
- Skill execution is non-deterministic; for a firm verdict run each label 2–3× and report the range.
- The sandbox best fits **self-contained** skills (fetch/produce, code-review on a diff, sql against
  a stub). Deeply environment-coupled orchestrators (real git/heap/browser) are only partially
  exercised — that is expected.
- Prefer a fresh `WS` per label so file effects don't leak between versions.

## Add a scenario
Copy `evals/scenarios/task_fetch_and_plan/` to a new folder and edit `scenario.py`: set `routes`
(canned fake responses), `workspace_seed` (seed files), the `task`, and `checks` (each a
`Check(name, predicate(ctx))` asserting on `ctx.called(...)` / `ctx.file(...)`). See `evals/README.md`.
