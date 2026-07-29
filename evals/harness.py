"""The skill-sandbox harness: scenarios, effectiveness checks, scorecards and A/B — stdlib only.

Model (domain-neutral):
  * A ``Scenario`` declares the fake service's canned ``routes``, the files to seed into a temp
    ``workspace``, the ``task`` to hand the skill, and ``checks`` that assert *effectiveness*.
  * The **live Claude Code session is the runner** (no API key / headless): guided by the
    ``sandbox-eval`` skill it executes the skill under test against the fake service + workspace.
  * Afterwards this harness reads what happened — the fake service's recorded ``calls.jsonl`` and
    the resulting workspace — and scores the checks. Run two skill versions over one scenario to
    get an A/B scorecard.

CLI:
    python -m evals.harness setup   <scenario> --run-dir DIR --workspace DIR
    python -m evals.harness check   <scenario> --run-dir DIR --workspace DIR --label green-loop
    python -m evals.harness compare --run-dir DIR
    python -m evals.harness notebook <scenario> --run-dir DIR --workspace DIR  # emit trial.ipynb + trial.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


# --------------------------------------------------------------------------- model


@dataclass
class TrialContext:
    """What a check inspects after the skill ran: the recorded calls and the workspace."""

    run_dir: Path
    workspace: Path
    calls: list[dict]

    def called(self, method: str, path_regex: str) -> bool:
        """Did the skill hit the fake service with this method + path (regex, ignoring query)?"""
        return any(
            c["method"].upper() == method.upper()
            and re.search(path_regex, c["path"].split("?")[0])
            for c in self.calls
        )

    def request_bodies(self, method: str, path_regex: str) -> list[str]:
        return [
            c.get("body", "")
            for c in self.calls
            if c["method"].upper() == method.upper()
            and re.search(path_regex, c["path"].split("?")[0])
        ]

    def file(self, rel: str) -> str | None:
        p = self.workspace / rel
        return p.read_text(encoding="utf-8") if p.exists() else None


@dataclass
class Check:
    """One effectiveness assertion. ``predicate`` returns True when the skill did the right thing."""

    name: str
    predicate: Callable[[TrialContext], bool]


@dataclass
class Scenario:
    name: str
    description: str
    # The instruction handed to the skill under test (uses {FAKE_URL} / {WORKSPACE} placeholders).
    task: str
    # Canned fake-service responses: {method, path_regex, status, json}.
    routes: list[dict] = field(default_factory=list)
    # Files seeded into the temp workspace before the run: {relative_path: content}.
    workspace_seed: dict[str, str] = field(default_factory=dict)
    checks: list[Check] = field(default_factory=list)
    # The skill / family this scenario exercises (groups trials on the SkillHub frontend).
    task_group: str = ""


@dataclass
class TrialResult:
    scenario: str
    label: str
    passed: list[str]
    failed: list[str]

    @property
    def score(self) -> str:
        total = len(self.passed) + len(self.failed)
        return f"{len(self.passed)}/{total}"


# --------------------------------------------------------------------------- loading / running


def load_scenario(name: str) -> Scenario:
    path = SCENARIOS_DIR / name / "scenario.py"
    if not path.exists():
        raise SystemExit(f"scenario not found: {path}")
    spec = importlib.util.spec_from_file_location(f"scenario_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    scenario = getattr(module, "scenario", None)
    # Duck-type, not isinstance: under `python -m evals.harness` this module runs as `__main__`
    # while scenario.py imports `evals.harness` (a second identity), so the two `Scenario` classes
    # differ. Validate by shape instead.
    if scenario is None or not all(hasattr(scenario, a) for a in ("name", "routes", "checks")):
        raise SystemExit(f"{path} must define a module-level `scenario = Scenario(...)`")
    return scenario


def load_calls(run_dir: Path) -> list[dict]:
    calls_file = run_dir / "calls.jsonl"
    if not calls_file.exists():
        return []
    return [json.loads(line) for line in calls_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def setup(scenario: Scenario, run_dir: Path, workspace: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    (run_dir / "routes.json").write_text(json.dumps(scenario.routes, indent=2), encoding="utf-8")
    for rel, content in scenario.workspace_seed.items():
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"seeded {len(scenario.workspace_seed)} file(s) into {workspace}")
    print(f"routes -> {run_dir / 'routes.json'}")
    print("next: start the fake service, then run the skill against it with the task below.")
    print("--- TASK ---")
    print(scenario.task)


def check(scenario: Scenario, run_dir: Path, workspace: Path, label: str) -> TrialResult:
    ctx = TrialContext(run_dir=run_dir, workspace=workspace, calls=load_calls(run_dir))
    passed, failed = [], []
    for c in scenario.checks:
        try:
            ok = bool(c.predicate(ctx))
        except Exception:  # a throwing check counts as failed, never crashes the run
            ok = False
        (passed if ok else failed).append(c.name)
    result = TrialResult(scenario=scenario.name, label=label, passed=passed, failed=failed)
    (run_dir / f"result-{label}.json").write_text(
        json.dumps({"scenario": result.scenario, "label": label, "passed": passed, "failed": failed}, indent=2),
        encoding="utf-8",
    )
    print(f"\n{scenario.name} · {label}: {result.score}")
    for name in passed:
        print(f"  ✓ {name}")
    for name in failed:
        print(f"  ✗ {name}")
    return result


def compare(run_dir: Path) -> None:
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(run_dir.glob("result-*.json"))]
    if not results:
        raise SystemExit("no result-*.json in run dir — run `check` for each skill version first")
    names = sorted({n for r in results for n in r["passed"] + r["failed"]})
    labels = [r["label"] for r in results]
    width = max(len(n) for n in names)
    print("check".ljust(width), *[f"| {lbl}" for lbl in labels])
    for n in names:
        cells = ["✓" if n in r["passed"] else "✗" for r in results]
        print(n.ljust(width), *[f"| {c}" for c in cells])
    print("score".ljust(width), *[f"| {len(r['passed'])}/{len(r['passed']) + len(r['failed'])}" for r in results])


# --------------------------------------------------------------------------- notebook (the run record)


def _md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def _code(source: str, stdout: str = "") -> dict:
    outputs = [{"output_type": "stream", "name": "stdout", "text": stdout}] if stdout else []
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": outputs, "source": source}


def _ab_matrix_text(results: list[dict]) -> str:
    if not results:
        return "(no results)"
    names = sorted({n for r in results for n in r["passed"] + r["failed"]})
    labels = [r["label"] for r in results]
    width = max([len(n) for n in names] + [len("check")])
    lines = ["check".ljust(width) + "".join(f" | {lbl}" for lbl in labels)]
    for n in names:
        cells = ["OK" if n in r["passed"] else "--" for r in results]
        lines.append(n.ljust(width) + "".join(f" | {c}" for c in cells))
    lines.append(
        "score".ljust(width)
        + "".join(f" | {len(r['passed'])}/{len(r['passed']) + len(r['failed'])}" for r in results)
    )
    return "\n".join(lines)


def emit_notebook(scenario: Scenario, run_dir: Path, workspace: Path, created_at: str) -> dict:
    """Build a Jupyter notebook (.ipynb, nbformat 4.5) that *is* the trial's run record, plus a
    compact ``trial.json`` for the store. Pure stdlib ``json`` — no Jupyter runtime needed to
    produce it. The notebook holds: the task, the fake-service routes, the recorded call trace, each
    skill version's scorecard + the plan it produced, and the A/B matrix."""
    calls = load_calls(run_dir)
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(run_dir.glob("result-*.json"))]

    cells: list[dict] = []
    cells.append(
        _md(
            f"# Skill trial — {scenario.name}\n\n"
            f"- **Task group:** {scenario.task_group or '(none)'}\n"
            f"- **Scenario:** {scenario.description}\n"
            f"- **Created:** {created_at}\n\n"
            f"> Sandbox trial: the live Claude Code ran the skill against a *fake service* + a temp "
            f"workspace. This notebook is the run record — nothing here touched a real system."
        )
    )
    cells.append(_md("## Task handed to the skill\n\n" + scenario.task))
    cells.append(
        _code(
            "# Fake service — canned routes (routes.json)\n" + json.dumps(scenario.routes, indent=2)
        )
    )
    trace = "\n".join(f"{c['method']:6} {c['path']}" + (f"  body={c['body']}" if c.get("body") else "") for c in calls)
    cells.append(
        _md("## Recorded calls — what the skill actually did\n\n" + f"{len(calls)} request(s) hit the fake service.")
    )
    cells.append(_code("# calls.jsonl (recorded by the fake service)", trace or "(no calls recorded)"))

    entries = []
    for r in results:
        label = r["label"]
        total = len(r["passed"]) + len(r["failed"])
        score = f"{len(r['passed'])}/{total}"
        lines = [f"## Result — `{label}` · {score}", ""]
        for n in r["passed"]:
            lines.append(f"- ✅ {n}")
        for n in r["failed"]:
            lines.append(f"- ❌ {n}")
        cells.append(_md("\n".join(lines)))
        # Prefer a per-label snapshot the runner saved (artifact-<label>.md); else the workspace plan.
        artifact = run_dir / f"artifact-{label}.md"
        if artifact.exists():
            cells.append(_code(f"# artifact-{label}.md — the plan this version produced\n" + artifact.read_text(encoding="utf-8")))
        elif (workspace / "plan.md").exists():
            cells.append(_code("# plan.md — the plan this version produced\n" + (workspace / "plan.md").read_text(encoding="utf-8")))
        entries.append(
            {
                "label": label,
                "skill_name": scenario.task_group or label,
                "skill_version": label,
                "passed": r["passed"],
                "failed": r["failed"],
                "score": score,
            }
        )

    cells.append(_md("## A/B scorecard"))
    cells.append(_code("# compare()", _ab_matrix_text(results)))

    notebook = {
        "cells": cells,
        "metadata": {
            "skillhub_trial": {
                "scenario": scenario.name,
                "task_group": scenario.task_group,
                "created_at": created_at,
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (run_dir / "trial.ipynb").write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
    (run_dir / "trial.json").write_text(
        json.dumps(
            {
                "scenario": scenario.name,
                "task_group": scenario.task_group,
                "created_at": created_at,
                "entries": entries,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {run_dir / 'trial.ipynb'} ({len(cells)} cells) and {run_dir / 'trial.json'}")
    return notebook


# --------------------------------------------------------------------------- CLI


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill-sandbox harness.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("setup", "check"):
        p = sub.add_parser(cmd)
        p.add_argument("scenario")
        p.add_argument("--run-dir", required=True)
        p.add_argument("--workspace", required=True)
        if cmd == "check":
            p.add_argument("--label", required=True)
    pc = sub.add_parser("compare")
    pc.add_argument("--run-dir", required=True)
    pn = sub.add_parser("notebook")
    pn.add_argument("scenario")
    pn.add_argument("--run-dir", required=True)
    pn.add_argument("--workspace", required=True)
    pn.add_argument("--created-at", default="", help="ISO timestamp; pass one for a reproducible record")

    args = parser.parse_args()
    if args.cmd == "setup":
        setup(load_scenario(args.scenario), Path(args.run_dir), Path(args.workspace))
    elif args.cmd == "check":
        check(load_scenario(args.scenario), Path(args.run_dir), Path(args.workspace), args.label)
    elif args.cmd == "compare":
        compare(Path(args.run_dir))
    elif args.cmd == "notebook":
        created_at = args.created_at
        if not created_at:
            from datetime import datetime, timezone

            created_at = datetime.now(timezone.utc).isoformat()
        emit_notebook(load_scenario(args.scenario), Path(args.run_dir), Path(args.workspace), created_at)


if __name__ == "__main__":
    main()
