"""skill-authoring scenario — author a brand-new SKILL.md (invoice-dispute-log,
backoffice-only), testing the exact frontmatter contract, the fixed 3-section
body shape (no extra top-level sections), the role label for a non-common skill,
and the catalog registration reminder.
"""

from evals.harness import Check, Scenario


def _skill(ctx) -> str:
    return (ctx.file("SKILL.md") or "")


def _skill_lower(ctx) -> str:
    return _skill(ctx).lower()


scenario = Scenario(
    name="skill_authoring_new_skill",
    task_group="skill-authoring",
    description=(
        "skill-authoring: author a brand-new SKILL.md for 'invoice-dispute-log' (backoffice-only, "
        "not common) — tests the frontmatter contract (name=dir, ALWAYS-use description), the "
        "fixed Read first/Workflow/Hard rules body shape with no extra sections, the role label "
        "for a non-common skill, and the catalog.md registration step."
    ),
    task=(
        "You are applying the `skill-authoring` skill. Create a new skill named "
        "`invoice-dispute-log`: used ALWAYS when a customer invoice dispute needs to be logged "
        "and tracked (backoffice department only, not needed by frontend/wms/logistics).\n\n"
        "Write the complete SKILL.md to {WORKSPACE}/SKILL.md."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote SKILL.md", lambda ctx: ctx.file("SKILL.md") is not None),
        Check(
            "frontmatter name equals the skill's own name",
            lambda ctx: "name: invoice-dispute-log" in _skill_lower(ctx) or "name:invoice-dispute-log" in _skill_lower(ctx).replace(" ", ""),
        ),
        Check(
            "description begins with ALWAYS use and states when",
            lambda ctx: "always use" in _skill_lower(ctx),
        ),
        Check(
            "uses the narrowest departments tag (backoffice), not common",
            lambda ctx: "backoffice" in _skill_lower(ctx) and "departments:" in _skill_lower(ctx) and "common" not in _skill_lower(ctx),
        ),
        Check(
            "has exactly the Read first / Workflow / Hard rules body shape",
            lambda ctx: all(h in _skill(ctx) for h in ("## Read first", "## Workflow", "## Hard rules")),
        ),
        Check(
            "adds the primary-role label line since this is a non-common skill",
            lambda ctx: "primary role" in _skill_lower(ctx),
        ),
        Check(
            "no extra top-level sections beyond Read first / Workflow / Hard rules",
            lambda ctx: sum(1 for l in _skill(ctx).splitlines() if l.strip().startswith("## ")) == 3,
        ),
    ],
)
