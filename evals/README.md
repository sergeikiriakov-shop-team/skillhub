# `evals/` — skill-evaluation sandbox (Approach A: local, stdlib-only)

A dependency-free harness to **test and A/B-compare Claude Code skills** by actually running them
against fixtures + a fake service and scoring effectiveness — the empirical complement to the
SkillHub rubric score.

## The model
- **The harness is the stage, not the runner.** It (a) serves canned responses from a
  *recording fake service* and (b) scores *effectiveness checks* against what the skill did.
- **The runner is your live console Claude Code** — no API key, no headless. Guided by the
  `sandbox-eval` skill, it executes the skill under test against the stage, like a developer trying
  a skill on their own code.
- **Domain-neutral.** The fake service and fixtures are generic; scenarios decide what they mean.

Only the Python standard library is used — `python3` is all a developer needs (no `pip`).

## Layout
```
evals/
  fake_service.py   # recording fake HTTP service (canned routes + logs every call)
  harness.py        # Scenario / Check model, setup, check (scorecard), compare (A/B); CLI
  scenarios/<name>/scenario.py   # a scenario: routes + seed files + task + checks
  README.md
  Dockerfile        # OPTIONAL one-off container to run the fake service (no local Python)
```

## Quickstart (A/B two versions of a skill)
Run from the repo root. `RUN=.sandbox/task_fetch_and_plan`.
```bash
# --- version A ---
python -m evals.fake_service --run-dir "$RUN" --port 0 &      # prints FAKE_SERVICE_URL=...
python -m evals.harness setup task_fetch_and_plan --run-dir "$RUN" --workspace "$RUN/ws-A"
#   → then, in Claude Code (sandbox-eval skill): run skill A against the fake URL + ws-A
python -m evals.harness check task_fetch_and_plan --run-dir "$RUN" --workspace "$RUN/ws-A" --label A
kill %1                                                        # stop the fake service

# --- version B: repeat the four steps with --workspace "$RUN/ws-B" --label B ---

python -m evals.harness compare --run-dir "$RUN"              # side-by-side check matrix + scores
```
In practice you don't type this by hand — you ask Claude Code to run the **`sandbox-eval`** skill,
which orchestrates start → run-skill → check → compare and enforces the "only touch the workspace +
fake URL" guardrail.

## Writing a scenario
Copy `scenarios/task_fetch_and_plan/` and edit `scenario.py`:
- `routes`: canned fake responses — `{method, path_regex, status, json}` (first match wins).
- `workspace_seed`: `{relative_path: content}` seeded into the temp workspace before the run.
- `task`: the instruction handed to the skill (use `{FAKE_URL}` / `{WORKSPACE}` placeholders).
- `checks`: a list of `Check(name, predicate)` where `predicate(ctx)` asserts effectiveness via
  `ctx.called(method, path_regex)`, `ctx.request_bodies(...)`, and `ctx.file(rel)`.

## Limits (be honest)
- Skill runs are **non-deterministic** — run 2–3× for a firm verdict.
- Best for **self-contained** skills (fetch/produce, code-review on a diff, SQL against a stub).
  Deeply environment-coupled orchestrators (real git/heap/browser) are only partially exercised.

## Optional: run the fake service in a container
If a developer has no Python but has Docker (co-located, still full-fidelity — the workspace is
mounted from the host temp dir):
```bash
docker build -t skillhub-evals evals
docker run --rm -p 8099:8099 -v "$PWD/.sandbox/task_fetch_and_plan:/run" skillhub-evals \
  --run-dir /run --port 8099
```
The hosted/centralized variant (a per-run container on the VPS + a notebook UI) is sketched in
`docs/skill-sandbox-approach-C.md` — a future v2 that reuses this same engine.
