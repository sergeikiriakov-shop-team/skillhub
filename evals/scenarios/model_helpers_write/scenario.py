"""model-helpers scenario — a blind bulk update + a recon insert, hitting the skill's
own two hard-rule traps: passing an extra table-name argument to updateInCollection
(causes an array_chunk fatal) and trusting insert_id after a recon insert (always 0;
must use $db->lastInsertID('table') instead).
"""

import re

from evals.harness import Check, Scenario


def _code(ctx) -> str:
    return ctx.file("solution.php") or ""


def _code_lower(ctx) -> str:
    return _code(ctx).lower()


def _update_call_first_arg_is_array(ctx) -> bool:
    m = re.search(r"updateincollection\s*\(\s*", _code_lower(ctx))
    if not m:
        return False
    rest = _code_lower(ctx)[m.end():m.end() + 10]
    return rest.startswith("[") or rest.startswith("array(")


scenario = Scenario(
    name="model_helpers_write",
    task_group="model-write-helpers",
    description=(
        "model-helpers: write a blind bulk update (no SELECT) and a recon single insert "
        "that must return the new row's real id. Discriminates on the skill's own two named "
        "gotchas: no extra table-name argument to updateInCollection (array_chunk fatal), and "
        "lastInsertID instead of trusting insert_id on a recon connection (always 0)."
    ),
    task=(
        "You are applying the `model-helpers` skill. Write two PHP functions:\n\n"
        "1. `markShipmentsDispatched(array $shipmentIds): void` — blind-update all "
        "`ShipmentModel` rows whose id is in `$shipmentIds` to `status='dispatched'`, "
        "`dispatched_at=NOW()`, WITHOUT loading them first (you already have the ids).\n\n"
        "2. `insertAuditLog(int $shipmentId, string $message): int` — insert ONE new row "
        "into `AuditLogModel` recording `$shipmentId` + `$message`, and return the new row's "
        "real id. Note: this write goes through a **recon** connection, where the driver's "
        "own `insert_id` is always 0 regardless of what was actually inserted.\n\n"
        "Write the complete PHP to {WORKSPACE}/solution.php."
    ),
    routes=[],
    workspace_seed={},
    checks=[
        Check("wrote solution.php", lambda ctx: ctx.file("solution.php") is not None),
        Check(
            "uses updateInCollection for the blind update (no SELECT/loaded object)",
            lambda ctx: "updateincollection(" in _code_lower(ctx),
        ),
        Check(
            "does NOT pass an extra table-name argument to updateInCollection (array_chunk fatal trap)",
            lambda ctx: _update_call_first_arg_is_array(ctx),
        ),
        Check(
            "gets the new insert id via lastInsertID, not the driver's own insert_id",
            lambda ctx: "lastinsertid(" in _code_lower(ctx) and "->insert_id" not in _code_lower(ctx),
        ),
        Check(
            "checks PEAR::isError after a DB call",
            lambda ctx: "pear::iserror(" in _code_lower(ctx),
        ),
        Check(
            "never falls back to raw INSERT/UPDATE SQL",
            lambda ctx: not any(k in _code_lower(ctx) for k in ("insert into", "update ") ) or ("::batchinsert(" in _code_lower(ctx) or "::updateincollection(" in _code_lower(ctx)),
        ),
        Check(
            "does not do a SELECT before the blind update (that would defeat the point of updateInCollection)",
            lambda ctx: "select " not in _code_lower(ctx).split("function insertauditlog")[0],
        ),
    ],
)
