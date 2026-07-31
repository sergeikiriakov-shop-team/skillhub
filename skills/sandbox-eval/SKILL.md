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
- A **scenario** name from `evals/scenarios/` (e.g. `task_fetch_and_plan`, `green_loop_understand`).
- One or more **skills under test**, each a `(label, SKILL.md)` — e.g. `("green-loop", <md>)` and
  `("prolo-task-driver", <md>)` for an A/B. Get the `SKILL.md` from the repo, from SkillHub
  (`get_skill` → `skill_md`), or the user pastes it.
- Optional: a **`skill_id`** on SkillHub to attach the result to, and a **`regenerate`** flag.

## Reuse vs. regenerate (check SkillHub first)
Each skill has ONE stored trial notebook on SkillHub. Before running, if you have a `skill_id`,
call `get_skill_notebook(skill_id)`. If it returns a notebook that is **not `stale`** and the user
did **not** ask to regenerate, **reuse it** — show its scorecard and stop; don't re-run. Regenerate
(run the trial below) when: the user asked to, no notebook exists, or `stale` is true (the skill
changed since the last run).

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
4b. **Snapshot the artifact** so the notebook shows what each version produced: copy the key output
    file to `$RUN/artifact-<label>.md` (e.g. `cp $WS/plan.md $RUN/artifact-<label>.md`).
5. **Stop the fake service** (kill the background process from step 1).

Then **A/B**: `python -m evals.harness compare --run-dir $RUN` → a side-by-side check matrix + scores.
Report which version passed more checks and where they differ; that is the empirical evidence
(complementing the SkillHub rubric score).

## Grade the RESULT with the judge panel (the per-model quality score)
The scorecard above is the **objective gate** — did the run do the required mechanics (a quantitative
pass/fail). The **headline per-model number is a QUALITY grade of the artifact the run produced**,
scoring the same rubric criteria against the RESULT, not against the SKILL.md in the abstract. The
judging strategy is server-side (one algorithm for everyone) — fetch it once with `get_rubric`, fields
`result_judge_*`: the `result_judge_dimensions`, the `result_judge_panel` (`judges` + `aggregate:
median`), and `result_judge_protocol`.

1. **Run the panel, BLIND.** For each judge model in `result_judge_panel.judges`, spawn a subagent set
   to that model (a `Task`/subagent with a model override — you are one session, the panel is several)
   and hand it: the task's ground truth (what a correct result must contain, incl. the traps), the
   `result_judge_dimensions`, and the artifact(s) **labelled A/B/… WITHOUT revealing which skill/model
   produced which**. Ask each judge for a 0–10 score per dimension + an `overall` + a one-line note per
   artifact, as JSON. Diverse judges + median mean one weak or self-preferring judge cannot swing it.
2. **Aggregate = median.** `result_grade` = the median of the panel's `overall`s; each dimension = the
   median across judges. Keep every judge's vote.
3. **Effectiveness = `result_grade`/10, CAPPED by the objective pass-rate** — a run that skipped required
   mechanics can't score above what it actually did (checks = the gate). The server computes this from
   the summary; you just supply the grade + the checks.

Faithfulness: judge the artifact the run ACTUALLY produced (copy it from `$WS`), keep each model's
output **verbatim** in the notebook, and record the judge as the model that graded — never touch up a
plan or invent a vote.

## Record it to SkillHub (one notebook per skill × model)
1. **Emit the run record**: `python -m evals.harness notebook <scenario> --run-dir $RUN --workspace $WS --model <executing-model-id>`
   → writes `$RUN/trial.ipynb` (the notebook) + `$RUN/trial.json` (the scorecard). Pass the **executing
   model id** (the model that RAN the skill, self-reported) so the trial is stored per model.
2. **Store it** so it shows on the skill's page: `submit_skill_notebook(skill_id, model="<executing-model-id>",
   notebook=<trial.ipynb JSON>, summary=<summary>, scenario="<scenario>", task_group="<group>")`. Build
   `summary` from `trial.json` (its `entries` = the objective scorecard) PLUS the panel result:
   `result_grade` (0–10 median), `dimensions` ({dim: median}), `panel` ([{judge, overall, dimensions,
   note}, …]) and `result_judge_version` (from the rubric). The skill page then shows the **grade** as the
   per-model headline, the **mechanics scorecard** as the gate, and the **panel breakdown** (weakest
   dimension flagged). This upserts the one notebook for that (skill, model); regenerating overwrites it;
   the server snapshots the tested version so the UI flags it `stale` once the skill changes. Requires a
   contributor+ role (`authenticate`).

## Docker option (no local Python)
Same steps in a container: `docker build -t skillhub-evals evals`, then run each `python -m evals.*`
command as `docker run --rm -v "$RUN:/run" skillhub-evals evals.<module> ... --run-dir /run`. Run the
fake service with `--host 0.0.0.0 --port 8099 -p 8099:8099` and curl the published port from the host.

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
