"""Phase 7 live verification: assemble_recipe -> validate_recipe -> apply -> rollback.

Drives the translator against the demo stand for ephemeral (reversible) recipes only.
Each recipe step is planned and applied through the existing OperatorRegistry, verified,
then rolled back and verified absent. Persistent/destructive recipes are not applied here.

Run with credentials from env (AXXON_HOST/AXXON_USERNAME/AXXON_PASSWORD/AXXON_TLS_CN/AXXON_CA).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import axxon_mcp_operator as op
from axxon_api_client import AxxonApiClient, add_common_args, config_from_args
from axxon_mcp_operator_smoke import discover_inventory
from axxon_mcp_translator import AxxonMcpTranslator

# Reversible recipes: intent text plus context supplying live fixture values. Each is applied
# then immediately rolled back. Persistent workflows are reversible via remove_created_uids.
EPHEMERAL_RECIPES = [
    ("add a camera for phase7 testing", lambda inv: {"display_name": "phase7-recipe-cam"}),
    ("create a macro for phase7 testing", lambda inv: {"name": "phase7-recipe-macro"}),
    ("inject an external alarm event", lambda inv: {"access_point": inv["detector_ex"], "event_type": "phase7_recipe"}),
]


def run_step(registry: op.OperatorRegistry, workflow: str, params: dict[str, Any]) -> dict[str, Any]:
    """Plan, apply, verify, rollback, and re-verify a single workflow step."""
    plan = registry.plan(workflow, params)
    if plan.get("status") == "gap":
        return {"workflow": workflow, "result": "gap", "message": plan.get("message")}
    pid = plan["plan_id"]
    applied = registry.apply(pid, plan["confirmation_token"])
    if applied.get("status") != "applied":
        return {"workflow": workflow, "plan_id": pid, "applied": applied.get("status"), "error": applied}
    pre = registry.verify(pid)
    rolled = registry.rollback(pid, plan["rollback_confirmation_token"])
    post = registry.verify(pid)
    return {
        "workflow": workflow,
        "plan_id": pid,
        "applied": applied.get("status"),
        "created": applied.get("created_uids"),
        "pre_verify_still_present": pre.get("still_present"),
        "rolled": rolled.get("status"),
        "post_verify_still_present": post.get("still_present"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser)
    args = parser.parse_args()

    cfg = config_from_args(args)
    api = AxxonApiClient(cfg)
    inv = discover_inventory(api, cfg.tls_cn)

    def make_operator() -> op.OperatorRegistry:
        return op.OperatorRegistry(
            client_factory=lambda: op.AxxonOperatorClient(api),
            host=f"hosts/{cfg.tls_cn}",
            enabled=True,
        )

    registry = make_operator()
    translator = AxxonMcpTranslator(operator_factory=make_operator)

    results = []
    for intent_text, ctx_builder in EPHEMERAL_RECIPES:
        recipe = translator.assemble_recipe(intent_text, ctx_builder(inv))
        steps = recipe.get("steps", [])
        validation = translator.validate_recipe(steps)
        explained = translator.explain_recipe(steps)
        applied_steps = [run_step(registry, s["workflow"], s["params"]) for s in steps]
        results.append({
            "intent_text": intent_text,
            "assembled_workflows": [s["workflow"] for s in steps],
            "validation_valid": validation.get("valid"),
            "validation_risk_classes": validation.get("risk_classes"),
            "explain_has_text": bool(explained if isinstance(explained, str) else explained.get("text")),
            "applied_steps": applied_steps,
        })

    print(json.dumps({"inventory": inv, "recipes": results}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
