"""frontend-code-writing / -refined — shared extraction scenario.

Both skills mandate the same non-React JS conventions (extract legacy .tpl JS
into the matching gulp bundle using the repo's own path map, template
literals over concatenation, event delegation, don't break the shared
surface, escape DOM-inserted data). The refined fork makes the safety rail
(XSS via `.html()`, grep-before-rename) and the pre-ship checklist explicit,
but the underlying rules are identical, so one task is reused for #9 (plain)
and #22 (refined).

The seed snippet bakes in 5 concrete violations: inline `.tpl` JS (must be
extracted to the exact bundle path from the skill's own path map), string
concatenation, a non-delegated handler on rows that get added dynamically,
`.html()` with a server value (XSS per the refined skill's own rail), and a
reused global selector that must NOT be renamed.
"""

from evals.harness import Check, Scenario

INLINE_SNIPPET = '''<!-- templates/mob_1/mobile_pick_41.tpl -->
<script>
$(document).ready(function() {
  $('.row-item').click(function() {
    var id = $(this).data('id');
    $.get('/api/pick/' + id, function(resp) {
      $('#toast').html('Picked item ' + resp.name + ' successfully');
    });
  });
});
</script>
'''


def _code(ctx) -> str:
    return ctx.file("index.js") or ""


def _code_lower(ctx) -> str:
    return _code(ctx).lower()


scenario = Scenario(
    name="frontend_code_writing_extract",
    task_group="frontend-authoring-nonreact",
    description=(
        "frontend-code-writing (plain #9 / refined #22, shared fixture): extract inline jQuery "
        "from a WMS mobile-pick template into the proper gulp bundle, fixing string "
        "concatenation, a non-delegated click handler on dynamically-added rows, and an "
        "unescaped `.html()` call on a server value, WITHOUT renaming the shared "
        "`.row-item`/`#toast` selectors other code depends on."
    ),
    task=(
        "You are applying the `frontend-code-writing` skill. This inline jQuery lives in "
        "`templates/mob_1/mobile_pick_41.tpl` and rows can be added to `.row-item` dynamically "
        "after an AJAX refresh (the click handler currently misses those):\n\n"
        "```html\n" + INLINE_SNIPPET + "\n```\n\n"
        "Extract and fix this per the skill's conventions. Write the resulting JS to "
        "{WORKSPACE}/index.js, with a leading comment stating the exact bundle path it belongs "
        "in (per the repo's WMS/admin path map)."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote index.js", lambda ctx: ctx.file("index.js") is not None),
        Check(
            "names the correct WMS bundle path from the skill's own path map",
            lambda ctx: "js/gulp/pagesjs/pages/wms/pick/41/index.js" in _code_lower(ctx),
        ),
        Check(
            "uses event delegation so dynamically-added rows are covered",
            lambda ctx: ".on(" in _code(ctx) and "row-item" in _code_lower(ctx) and ".click(" not in _code_lower(ctx),
        ),
        Check(
            "prefers a template literal over string concatenation for the URL",
            lambda ctx: "`/api/pick/" in _code(ctx) or "`api/pick/" in _code(ctx),
        ),
        Check(
            "escapes the server value instead of raw .html()",
            lambda ctx: (".text(" in _code(ctx) or "escapeHtml" in _code(ctx)) and ".html(" not in _code_lower(ctx),
        ),
        Check(
            "does not rename/remove the shared .row-item / #toast selectors",
            lambda ctx: "row-item" in _code_lower(ctx) and "#toast" in _code_lower(ctx),
        ),
        Check(
            "guards against a missing/absent element before using it",
            lambda ctx: any(k in _code_lower(ctx) for k in (".length", "if (!$"))
        ),
        Check(
            "comments (if any) are in English, not Russian",
            lambda ctx: not any(ch in _code(ctx) for ch in "абвгдежзийклмнопрстуфхцчшщъыьэюя"),
        ),
    ],
)
