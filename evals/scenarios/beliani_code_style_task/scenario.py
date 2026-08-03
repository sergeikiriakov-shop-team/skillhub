"""beliani-code-style / -refined — shared code-writing scenario.

Both skills state the SAME four mandatory rules (avoid LIMIT 1, PEAR::isError
immediately with no compound condition, 3+ field UPDATE through the model
layer, complete non-filler phpDoc). The refined fork adds inline correct/
incorrect examples and a precedence note but no new rule, so this ONE task is
reused for both #3 (plain) and #27 (refined) — an apples-to-apples comparison
of how faithfully each mandate is actually followed, not just read.

The task is designed so a naive/lazy implementation trips at least three of
the four rules: an "auction_number" filter alone looks unique but is NOT (the
real unique key is (auction_number, txnid)) — the classic LIMIT-1 trap; a
4-field update invites a raw UPDATE...SET; and a PEAR call invites a
skipped/compound error check.
"""

from evals.harness import Check, Scenario


def _code(ctx) -> str:
    return (ctx.file("solution.php") or "")


def _code_lower(ctx) -> str:
    return _code(ctx).lower()


scenario = Scenario(
    name="beliani_code_style_task",
    task_group="php-code-style",
    description=(
        "beliani-code-style (plain #3 / refined #27, shared fixture): write a PHP model "
        "method that fetches one auction row and updates 4 fields, over a schema where "
        "auction_number ALONE is not unique (the real unique key is (auction_number, txnid)) "
        "— tests LIMIT-1 avoidance via the real key, PEAR::isError discipline, the 3+ field "
        "model-layer rule, and non-filler phpDoc, in one shot."
    ),
    task=(
        "You are applying the `beliani-code-style` skill. Write a PHP method "
        "`markAuctionPaid($auctionNumber, $txnid, $amount, $currency)` on `AuctionModel` "
        "that:\n"
        "1. Looks up the auction row for this payment via PEAR `$dbr` — note that "
        "`auction_number` is NOT unique by itself (a re-auction can reuse it); the real "
        "unique key on the `auction` table is `(auction_number, txnid)`.\n"
        "2. If found, updates 4 fields on it: `status` (to `'paid'`), `paid_amount`, "
        "`paid_currency`, `paid_at` (now).\n"
        "3. Returns `true` on success, `false` if no matching row was found.\n\n"
        "Write the complete PHP (class method, with phpDoc) to {WORKSPACE}/solution.php."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote solution.php", lambda ctx: ctx.file("solution.php") is not None),
        Check(
            "avoids LIMIT 1",
            lambda ctx: "limit 1" not in _code_lower(ctx),
        ),
        Check(
            "filters the SELECT on the real unique key (auction_number AND txnid together), not auction_number alone",
            lambda ctx: "auction_number" in _code_lower(ctx) and "txnid" in _code_lower(ctx),
        ),
        Check(
            "checks PEAR::isError right after the SQL call, with no compound condition in that if",
            lambda ctx: "pear::iserror" in _code_lower(ctx)
            and not any(bad in _code_lower(ctx) for bad in ("iserror($result) &&", "iserror($result) ||", "!pear::iserror", "iserror($row) &&", "iserror($row) ||")),
        ),
        Check(
            "routes the 4-field update through the model layer, not a raw UPDATE...SET",
            lambda ctx: any(k in _code(ctx) for k in ("::updateInCollection(", "->fill(", "updateInCollection(")) and "set " not in _code_lower(ctx),
        ),
        Check(
            "phpDoc has @param for every argument",
            lambda ctx: _code_lower(ctx).count("@param") >= 4,
        ),
        Check(
            "phpDoc @return describes the role, not a filler restating the signature",
            lambda ctx: "@return bool" in _code_lower(ctx) and "@return bool the" not in _code_lower(ctx).replace("boolean", "bool"),
        ),
        Check(
            "logs the PEAR error via ServerLogs::pearErrorLog with an explicit context",
            lambda ctx: "serverlogs::pearerrorlog" in _code_lower(ctx),
        ),
    ],
)
