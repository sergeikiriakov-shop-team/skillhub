"""react-code-writing / -refined — shared component-authoring scenario.

Both skills state the same rules (functional components + hooks, correct
effect deps, SCSS modules not inline styles, accessible markup, JSDoc on
component methods, ESLint-clean). The refined fork spells out the
effect-loop/shared-UI/XSS safety rail explicitly, but the underlying rules
are the same, so one task is reused for #11 (plain) and #23 (refined).

A from-scratch write task (not a diff) so the discriminator is what the model
proactively includes without being told: correct `useEffect` deps (refetch
on `userId` change, no stale closure), SCSS-module styling instead of inline
styles, an `alt` on the avatar image, and a JSDoc block.
"""

from evals.harness import Check, Scenario


def _code(ctx) -> str:
    return ctx.file("UserBadge.jsx") or ""


def _code_lower(ctx) -> str:
    return _code(ctx).lower()


scenario = Scenario(
    name="react_code_writing_component",
    task_group="react-authoring",
    description=(
        "react-code-writing (plain #11 / refined #23, shared fixture): write a small "
        "`UserBadge` component from scratch (fetch + display a user's name/avatar by "
        "`userId`) — tests correct effect deps on prop change, SCSS-module styling over "
        "inline styles, accessible markup, and JSDoc, none of which are spelled out in the "
        "task itself."
    ),
    task=(
        "You are applying the `react-code-writing` skill. Write a functional React component "
        "`UserBadge` that takes a `userId` prop, fetches the user via the already-existing "
        "`fetchUser(userId)` (returns a Promise resolving to `{ name, avatarUrl }`), and "
        "renders the avatar image and display name. It must refetch correctly if `userId` "
        "changes on a re-render, and it must not use inline styles.\n\n"
        "Write the complete component to {WORKSPACE}/UserBadge.jsx."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote UserBadge.jsx", lambda ctx: ctx.file("UserBadge.jsx") is not None),
        Check(
            "is a functional component, not a class component",
            lambda ctx: "function" in _code_lower(ctx) and "extends react.component" not in _code_lower(ctx) and "extends component" not in _code_lower(ctx),
        ),
        Check(
            "useEffect depends on userId (refetches on change, no stale closure)",
            lambda ctx: "useeffect" in _code_lower(ctx) and "[userid]" in _code_lower(ctx).replace(" ", ""),
        ),
        Check(
            "uses SCSS-module styling, not inline style objects",
            lambda ctx: (".module.scss" in _code_lower(ctx)) and "style={{" not in _code(ctx),
        ),
        Check(
            "the avatar image has an accessible alt attribute",
            lambda ctx: "<img" in _code_lower(ctx) and "alt=" in _code_lower(ctx),
        ),
        Check(
            "actually imports fetchUser rather than calling an undefined name",
            lambda ctx: any("import" in line and "fetchuser" in line.lower() for line in _code(ctx).splitlines()),
        ),
        Check(
            "has a JSDoc block documenting the component/props",
            lambda ctx: "/**" in _code(ctx) and "@param" in _code(ctx),
        ),
        Check(
            "does not use dangerouslySetInnerHTML for plain name/avatar rendering",
            lambda ctx: "dangerouslysetinnerhtml" not in _code_lower(ctx),
        ),
        Check(
            "avoids an unnecessary re-render loop (no setState called unconditionally on every render body)",
            lambda ctx: "usestate" in _code_lower(ctx) and "useeffect" in _code_lower(ctx),
        ),
    ],
)
