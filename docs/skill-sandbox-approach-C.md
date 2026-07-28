# Skill sandbox — Approach C (hosted, notebook-driven) — design memo

Parked idea for a **v2** of the skill-evaluation sandbox. v1 is the local Python harness in
`evals/` (Approach A). This note captures C so it isn't lost.

## The idea
A **prod-hosted execution container** (on the VPS) holds the fake service, the scenario fixtures
and the checks — driven via a **notebook** — while the skill itself is still executed by the
developer's **local console Claude Code** (no API key / headless; same executor as A).

## Flow (as envisioned)
1. A sandbox orchestrator on the VPS spins a **per-run, ephemeral container** and returns a
   `run_id` + a remote `FAKE_URL`.
2. The developer's local Claude Code executes the target `SKILL.md`, directing the skill's
   **network** calls at that remote `FAKE_URL`.
3. A hosted notebook / endpoint runs the checks against the fake service's recorded calls and
   stores the scorecard centrally — shown in SkillHub and feeding synthesis (accept a synthesized
   "ideal" only if it passes scenarios ≥ the group winner).

## Why it's attractive
- No local setup for developers (no Python/Docker on their side).
- Centralized, shareable scenarios + results; consistent across the team; fits SkillHub's
  "service is the source of truth" model (and its move away from per-dev Docker).
- Natural home for a hosted notebook UX.

## The catch (must be designed around)
The executor (Claude Code) runs on the developer's machine, so **checks only see what is
co-located with the executor**:
- **Network actions** (curl/HTTP → remote `FAKE_URL`) — visible to the prod checker. ✅
- **Local actions** (files, git, php/node, browser) — happen on the dev's machine, invisible to a
  prod-side checker → **split-brain**. ❌

So Approach C, as-is, verifies only the **network-interaction class** of skills. To also verify
file-level effects it would need either (a) the workspace mounted/streamed to the container (agent
editing a remote workspace — un-Claude-Code-like), or (b) a local agent-side reporter that ships
the resulting workspace back to the checker.

## Relationship to v1 (Approach A)
C **reuses A's engine unchanged**: `evals/fake_service.py` (the recording fake) and
`evals/harness.py` (scenarios + checks + scorecard/AB) run the same in a container / on prod.
C adds only: a per-run container orchestrator, remote-URL issuance + auth, result storage, and the
notebook front-end. Nothing about A is throwaway.

## Recommendation
Ship A (local, full-fidelity, zero infra) first; graduate to C when centralized/shared runs are
worth the infra, explicitly scoping C to the network-interaction class (or adding the workspace
round-trip). A middle option is a **local one-off container** (Approach B): same engine, docker
isolation, workspace mounted from the dev's temp dir — co-located, so it keeps full-fidelity checks
without any prod infra.
