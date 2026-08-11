"""Department `*-code-style` scenario (shop / backoffice / logistics / wms).

These four skills are thin wrappers over a ~21.7 KB references/php-rules.md that carries **14**
rules — not the 4 of `beliani-code-style`, which is why the existing `beliani_code_style_task`
scenario cannot be reused: that task asks for a `true/false` return, and rule 5 of these skills
forbids exactly that for a new work-performing method.

The task is built so the obvious implementation breaks several rules at once, and so the wording
itself baits the one that is easiest to miss:

- "tell the caller whether it worked" invites a `bool` success flag — **rule 5** says return the
  produced value (or void) and `throw` on failure; `bool` is only for side-effect-free predicates;
- `auction_number` looks unique but is not (the real key is `(auction_number, txnid)`) — **rule 1**,
  the LIMIT-1 trap;
- four updated fields invite a raw `UPDATE … SET` — **rule 3**, go through the model layer;
- a PEAR call invites a skipped or compound error check — **rule 2**, check immediately, alone;
- **rule 10** wants the SQL in a `$q` variable, **rule 13** wants `$dbr` to read and `$db` to write.

A run that satisfies the task literally (returning true/false) fails the rule the skill exists to
enforce, which is the discrimination this scenario is for.
"""

import re

from evals.harness import Check, Scenario

# A raw multi-field write looks like `UPDATE <table> SET` — matched on the statement, not on the
# word "update", which legitimately appears in phpDoc and in updateInCollection().
_RAW_UPDATE = re.compile(r"update\s+[`\"']?\w+[`\"']?\s+set\b", re.IGNORECASE | re.DOTALL)


def _code(ctx) -> str:
    return ctx.file("solution.php") or ""


def _low(ctx) -> str:
    return _code(ctx).lower()


def _executable(ctx) -> str:
    """The code with comments stripped.

    Rules are about what the method DOES, so a rule named in a phpDoc line ("the real key instead
    of LIMIT 1") must not read as a violation of it — checking the raw text punishes explaining
    yourself, which is the opposite of what the skill asks for."""
    without_block = re.sub(r"/\*.*?\*/", "", _code(ctx), flags=re.DOTALL)
    return re.sub(r"//.*", "", without_block)


scenario = Scenario(
    name="department_code_style_task",
    task_group="php-code-style",
    description=(
        "department *-code-style (shop/backoffice/logistics/wms): write a model method over a "
        "non-unique-looking key, updating 4 fields, where the task's own wording baits the bool "
        "success flag rule 5 forbids — tests whether the skill's rules beat the literal request."
    ),
    task=(
        "You are applying this repository's department code-style skill. Read its "
        "`references/php-rules.md` FIRST — it is the spec, and the rules there take precedence "
        "over the phrasing of this request.\n\n"
        "Write a PHP method `markAuctionPaid($auctionNumber, $txnid, $amount, $currency)` on "
        "`AuctionModel` that:\n"
        "1. Looks up the auction row for this payment. Note: `auction_number` is NOT unique on "
        "its own (a re-auction reuses it); the real unique key on the `auction` table is "
        "`(auction_number, txnid)`.\n"
        "2. If the row exists, updates 4 fields on it: `status` (to `'paid'`), `paid_amount`, "
        "`paid_currency`, `paid_at` (now).\n"
        "3. Tells the caller whether the update succeeded, and makes sure a DB failure cannot pass "
        "unnoticed.\n\n"
        "Write the complete method, with phpDoc, to {WORKSPACE}/solution.php."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote solution.php", lambda ctx: _code(ctx) != ""),
        Check("rule 1 — avoids LIMIT 1", lambda ctx: "limit 1" not in _executable(ctx).lower()),
        Check(
            "rule 1 — filters on the real unique key (auction_number AND txnid)",
            lambda ctx: "auction_number" in _low(ctx) and "txnid" in _low(ctx),
        ),
        Check(
            "rule 2 — PEAR::isError checked alone, not folded into a compound condition",
            lambda ctx: "pear::iserror" in _low(ctx)
            and not any(
                bad in _low(ctx)
                for bad in ("iserror($result) &&", "iserror($result) ||", "iserror($row) &&", "iserror($row) ||")
            ),
        ),
        Check(
            "rule 2 — logs the PEAR error via ServerLogs::pearErrorLog",
            lambda ctx: "serverlogs::pearerrorlog" in _low(ctx),
        ),
        Check(
            "rule 3 — the 4-field update goes through the model layer, not a raw UPDATE ... SET",
            lambda ctx: any(k in _code(ctx) for k in ("updateInCollection(", "->fill(", "->save("))
            and _RAW_UPDATE.search(_code(ctx)) is None,
        ),
        Check(
            "rule 5 — does NOT return a bool success flag despite the task asking for one",
            lambda ctx: "return true" not in _low(ctx) and "return false" not in _low(ctx),
        ),
        Check(
            "rule 5 — fails loudly instead: throws on the DB error path",
            lambda ctx: "throw " in _low(ctx),
        ),
        Check(
            "rule 4 — phpDoc carries @param for all four arguments",
            lambda ctx: _low(ctx).count("@param") >= 4,
        ),
        Check(
            "rule 10 — the SQL lives in a $q variable, not inline in the call",
            lambda ctx: "$q =" in _code(ctx) or "$q=" in _code(ctx),
        ),
        Check(
            "rule 13 — the SELECT goes through the read connection ($dbr / $this->dbr)",
            lambda ctx: re.search(r"\$(?:this->)?dbr\b", _executable(ctx)) is not None,
        ),
        Check(
            "names the conflict: says the bool return was dropped because rule 5 forbids it",
            lambda ctx: any(
                k in _low(ctx) for k in ("rule 5", "success flag", "bool flag", "throws instead")
            ),
        ),
    ],
)
