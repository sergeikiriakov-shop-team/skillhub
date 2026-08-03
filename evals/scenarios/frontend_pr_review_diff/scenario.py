"""frontend-pr-review-refined STRICT diff-review scenario — a real security bug + a real logic bug
buried among smaller issues, to see whether the risk pass (Step 3) actually catches them and the
report follows the mandated ranked/blocking format (Step 4-5).
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
    name="frontend_pr_review_diff",
    task_group="frontend-pr-review",
    description=(
        "frontend-pr-review-refined over a small React diff carrying a real XSS "
        "(dangerouslySetInnerHTML on unescaped comment text), a hardcoded live Stripe secret key, "
        "a useEffect missing the userId dependency (stale profile), and a dropped key prop — mixed "
        "severities to test whether the risk pass (Step 3) and the ranked report (Step 4-5) work."
    ),
    task=(
        "You are running the `frontend-pr-review-refined` skill on the following PR diff for "
        "`src/components/CommentList.tsx`. Review it and write your findings to "
        "{WORKSPACE}/review.md using the skill's report format (Verdict, Blocking / Non-blocking / "
        "Nits, each with file:line + why + fix).\n\n"
        "```diff\n" + DIFF_TEXT + "\n```"
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote review.md", lambda ctx: ctx.file("review.md") is not None),
        Check(
            "flags the dangerouslySetInnerHTML / XSS issue",
            lambda ctx: any(k in _review(ctx) for k in ("dangerouslysetinnerhtml", "xss")),
        ),
        Check(
            "marks a real security issue as blocking",
            lambda ctx: "blocking" in _review(ctx) and any(k in _review(ctx) for k in ("dangerouslysetinnerhtml", "xss", "secret", "stripe", "key")),
        ),
        Check(
            "flags the hardcoded/committed live secret key",
            lambda ctx: any(k in _review(ctx) for k in ("secret", "stripe", "sk_live", "api key", "hardcoded")),
        ),
        Check("flags the missing key prop", lambda ctx: "key" in _review(ctx) and any(k in _review(ctx) for k in ("prop", "list", "map"))),
        Check(
            "flags the useEffect missing the userId dependency",
            lambda ctx: "useeffect" in _review(ctx) and any(k in _review(ctx) for k in ("dependency", "dep array", "deps", "stale")),
        ),
        Check(
            "gives file:line style references",
            lambda ctx: "commentlist.tsx" in _review(ctx) and any(c.isdigit() for c in _review(ctx)),
        ),
        Check(
            "gives an overall verdict",
            lambda ctx: any(k in _review(ctx) for k in ("request changes", "verdict", "approve", "comment")),
        ),
        Check(
            "uses the blocking/non-blocking/nit structure",
            lambda ctx: "blocking" in _review(ctx) and any(k in _review(ctx) for k in ("non-blocking", "nit")),
        ),
    ],
)
