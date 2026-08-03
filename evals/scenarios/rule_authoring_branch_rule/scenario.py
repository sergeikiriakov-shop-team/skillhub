"""rule-authoring scenario — a branch-naming/no-direct-commit rule that has a REAL
documented exception (an emergency hotfix), testing whether the model correctly
avoids "Never" for a rule that has one (per the skill's own hard rule: "Use Never
only for a hard rule with no local exception") and still pairs every prohibition
with its replacement.
"""

from evals.harness import Check, Scenario


def _rule(ctx) -> str:
    return (ctx.file("rule.md") or "").lower()


scenario = Scenario(
    name="rule_authoring_branch_rule",
    task_group="rule-authoring",
    description=(
        "rule-authoring: write a branch-naming / no-direct-commit-to-master8 rule with a real "
        "documented exception (an approved emergency hotfix) — tests the rule-shape template, "
        "imperative language, the Never-only-with-no-exception discipline, and pairing every "
        "prohibition with its replacement."
    ),
    task=(
        "You are applying the `rule-authoring` skill. Write a rule for `AGENTS.md`: task work "
        "must happen on a branch named `<task-id>/<slug>` off `master8`; committing directly to "
        "`master8` or `dev` is forbidden EXCEPT for an emergency hotfix that has been explicitly "
        "approved by a lead, which may be pushed directly to `master8` with a follow-up task "
        "created to backfill the normal branch/PR trail.\n\n"
        "Write the rule to {WORKSPACE}/rule.md."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote rule.md", lambda ctx: ctx.file("rule.md") is not None),
        Check("labels a Core rule section", lambda ctx: "core rule" in _rule(ctx)),
        Check(
            "has an Exceptions section documenting the hotfix carve-out",
            lambda ctx: "exceptions" in _rule(ctx) and "hotfix" in _rule(ctx),
        ),
        Check("has a Validation section", lambda ctx: "validation" in _rule(ctx)),
        Check(
            "uses direct imperative language",
            lambda ctx: any(k in _rule(ctx) for k in ("do not", "never", "use ", "prefer", "stop and ask")),
        ),
        Check(
            "pairs the prohibition with its replacement (do not/never X; use Y)",
            lambda ctx: ("do not" in _rule(ctx) or "never" in _rule(ctx)) and "branch" in _rule(ctx),
        ),
        Check(
            "places the rule at the universal AGENTS.md layer, not a department overlay or skill",
            lambda ctx: "agents.md" in _rule(ctx),
        ),
    ],
)
