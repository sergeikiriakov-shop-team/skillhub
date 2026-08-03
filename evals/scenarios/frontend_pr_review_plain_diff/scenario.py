"""frontend-pr-review (plain, unrefined) scenario — the SAME diff as
frontend_pr_review_diff, but graded against THIS skill's own (much thinner) mandate.

frontend-pr-review's own body is a bare checklist: quality/readability, performance, React
best practices (hooks), styling, type safety, bugs/edge cases, duplication/reuse. It has NO
report-format requirement, NO severity/prioritization step, and — per its own rubric
evaluation (safety=5) — NO safety/security category at all. This scenario deliberately does
NOT require a report format or a "blocking" verdict (the skill never asks for one) — instead
it asks the harder, more honest question: given a diff with a real XSS and a hardcoded live
secret key, does the model still flag them on general competence, even though the skill it is
following never tells it to look for security issues? That gap (or the lack of one) is the
whole point of comparing this skill's trials against frontend_pr_review_diff's (skill #21,
which mandates an explicit risk pass).
"""

from evals.harness import Check, Scenario

DIFF_TEXT = '''--- a/src/components/CommentList.tsx
+++ b/src/components/CommentList.tsx
@@ -1,14 +1,21 @@
+import { useEffect, useState } from "react";
+
+const STRIPE_SECRET_KEY = "sk_live_FAKE_EXAMPLE_KEY_DO_NOT_USE_IN_PROD";
+
 export function CommentList({ comments, userId }: { comments: Comment[]; userId: string }) {
-  return (
-    <div>
-      {comments.map((c) => <Comment key={c.id} text={c.text} />)}
-    </div>
-  );
+  const [profile, setProfile] = useState(null);
+
+  useEffect(() => {
+    fetchUserProfile(userId).then(setProfile);
+  }, []);
+
+  return (
+    <div>
+      {comments.map((c) => (
+        <div dangerouslySetInnerHTML={{ __html: c.text }} />
+      ))}
+      <button onClick={() => trackEvent("view", { key: STRIPE_SECRET_KEY })}>Track</button>
+    </div>
+  );
 }
'''


def _review(ctx) -> str:
    return (ctx.file("review.md") or "").lower()


scenario = Scenario(
    name="frontend_pr_review_plain_diff",
    task_group="frontend-pr-review",
    description=(
        "frontend-pr-review (plain, unrefined) over the SAME diff as frontend_pr_review_diff "
        "(skill #21) — an apples-to-apples comparison. This skill's own body never mentions "
        "safety/security at all (rubric-flagged weakness), so the discriminator is whether the "
        "model still catches the real XSS and the hardcoded live secret key on general "
        "competence, plus whether it covers the skill's OWN stated categories (hooks, type "
        "safety, duplication/reuse) — not a report-format or severity check, since this skill "
        "never asks for either."
    ),
    task=(
        "You are running the `frontend-pr-review` skill on the following PR diff for "
        "`src/components/CommentList.tsx`. Review it per the skill's categories and write your "
        "findings to {WORKSPACE}/review.md.\n\n"
        "```diff\n" + DIFF_TEXT + "\n```"
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote review.md", lambda ctx: ctx.file("review.md") is not None),
        Check(
            "covers React hooks best practice (the useEffect missing dependency)",
            lambda ctx: "useeffect" in _review(ctx) and any(k in _review(ctx) for k in ("dependency", "dep array", "deps", "stale")),
        ),
        Check(
            "covers type safety (untyped useState)",
            lambda ctx: "usestate" in _review(ctx) and any(k in _review(ctx) for k in ("type", "typed", "typescript", "any")),
        ),
        Check(
            "covers bugs/edge cases (the missing key prop)",
            lambda ctx: "key" in _review(ctx) and any(k in _review(ctx) for k in ("prop", "map", "list", "reconcil")),
        ),
        Check(
            "covers duplication/reuse (dropping the reusable Comment component)",
            lambda ctx: any(k in _review(ctx) for k in ("reuse", "duplicat", "hook", "extract", "encapsulat", "revert", "component pattern")),
        ),
        Check(
            "still flags the XSS (dangerouslySetInnerHTML) despite no safety category in the skill",
            lambda ctx: any(k in _review(ctx) for k in ("dangerouslysetinnerhtml", "xss")),
        ),
        Check(
            "still flags the hardcoded live secret key despite no safety category in the skill",
            lambda ctx: any(k in _review(ctx) for k in ("secret", "stripe", "sk_live", "api key", "hardcoded", "leak")),
        ),
        Check(
            "stays frontend-scoped (doesn't assert specific backend behavior as fact)",
            lambda ctx: not any(k in _review(ctx) for k in ("the backend already", "the api already", "the server-side logic is", "the backend is correct", "the backend is broken")),
        ),
    ],
)
