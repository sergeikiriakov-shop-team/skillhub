# Sandbox trials on the frontend (+ notebook contents) — design memo

Next feature for the skill-evaluation sandbox (`evals/`, Approach A). Goal: surface trial runs in
the SkillHub dashboard — the **scorecard / A-B** *and* the **contents of the notebook** that was run
for each trial. This is the "display layer" that Approach C sketched, done incrementally on top of
the local harness. The runner stays the developer's live Claude Code.

## Pieces

### 1. The trial artifact = a notebook
Extend the harness so each trial emits a **notebook** (`.ipynb`) that *is* the run record — cells:
- scenario + task (markdown),
- fixtures / fake-service routes (markdown/code),
- the agent's actions/trace against the fake service (markdown),
- the scorecard output, and the A-B matrix (outputs).

Plus a compact `trial.json`: `{scenario, entries:[{label, skill_name, skill_version, passed[],
failed[], score}], task_group, created_at}`. (Simplest: `evals/harness.py` generates the `.ipynb`
from its own setup/check/compare outputs — nbformat JSON is easy to build with stdlib `json`; no
Jupyter runtime needed to *produce* it.)

### 2. Store in SkillHub (new `trials` context)
- Model `Trial`: `id, scenario, skill_name, skill_version/label, task_group, scores(JSONB),
  notebook(JSONB = ipynb cells), created_by, created_at`.
- Endpoints: `POST /api/trials` (contributor+), `GET /api/trials?skill=&task_group=`,
  `GET /api/trials/{id}`. MCP tools `submit_trial` / `list_trials` so the `sandbox-eval` skill
  pushes the record right after a run (same pattern as recommendations).
- Build this the DDD/DI way (Protocol repo + service + container provider) — it's a fresh context,
  so it's a clean place to apply the template from [[skillhub-di-ddd-refactor]].

### 3. Frontend — a "Trials" view
- A **Trials** page (nav entry): list trials (filter by skill / task_group), each showing the
  scorecard + A-B matrix and the rendered **notebook contents**.
- Also surface trials on the **skill detail** page ("Sandbox trials") and, ideally, gate synthesis
  acceptance on trial evidence (an "ideal" must pass scenarios ≥ the group winner).
- **Notebook rendering (safety):** store the notebook as structured cells (JSON), render in React —
  markdown cells via the existing markdown path, code cells as `<pre>`, outputs as text/`<pre>`.
  Do NOT inject raw notebook HTML (XSS). If a richer render is needed later, pre-sanitize server-side.

## Notes / caveats
- Reuses the `evals/` engine + the `sandbox-eval` skill unchanged for the *run*; this adds only the
  emit-notebook step + the store + the view. See [[skillhub-skill-sandbox]].
- Trials are **evidence**, not proof (skill runs are non-deterministic) — store N runs / show the
  range. Env-coupled orchestrators are only partially exercised.
- Approach C (hosted per-run container + a live hosted notebook UI) remains the heavier v2; this
  memo is the lighter "store the produced notebook + render it read-only" path that fits the
  existing read-only dashboard.
