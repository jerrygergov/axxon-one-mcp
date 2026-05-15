#!/usr/bin/env python3
"""Live smoke harness for MCP Phase 3 operator workflows.

Cycles each requested workflow through plan -> apply -> verify -> rollback ->
post-verify on the connected Axxon server. Workflows that need fixtures the
stand does not have return ``status: gap`` and are reported as such.

The harness is read-only by default; pass ``--enable-live`` to actually call
apply/rollback. Without it, only the typed plans are returned.

Examples:
    python axxon_mcp_operator_smoke.py --enable-live
    python axxon_mcp_operator_smoke.py --enable-live --workflow temp_device_template
    python axxon_mcp_operator_smoke.py --enable-live --workflow external_event_inject \\
        --access-point hosts/Server/DetectorEx.1/EventSupplier
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args
import axxon_mcp_operator as op


def discover_inventory(client: AxxonApiClient, tls_cn: str) -> dict[str, str]:
    """Pull the first camera UID, a video source AP, and any vmda sub-unit."""
    client.authenticate_grpc()
    domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
    config_pb2 = client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
    domain = client.common_stubs()["domain"]
    config_stub = client.common_stubs()["config"]
    out = {"camera_uid": "", "video_source_ap": "", "vmda_source_ap": "", "detector_ex": ""}
    for page in domain.ListCameras(domain_pb2.ListCamerasRequest(page_size=100), timeout=client.config.timeout):
        for cam in client.message_to_dict(page).get("items", []):
            ap = cam.get("access_point") or ""
            if not out["camera_uid"] and ap:
                out["camera_uid"] = ap.split("/SourceEndpoint")[0]
                if "video:" in ap:
                    out["video_source_ap"] = ap
    if out["camera_uid"]:
        resp = config_stub.ListUnits(
            config_pb2.ListUnitsRequest(unit_uids=[out["camera_uid"]]),
            timeout=client.config.timeout,
        )
        for unit in client.message_to_dict(resp).get("units") or []:
            for sub in unit.get("units") or []:
                if "vmda" in sub.get("type", "").lower() and not out["vmda_source_ap"]:
                    out["vmda_source_ap"] = sub.get("uid", "")
    out["detector_ex"] = f"hosts/{tls_cn}/DetectorEx.1/EventSupplier"
    return out


def cycle(registry: op.OperatorRegistry, workflow: str, params: dict[str, Any], enabled: bool) -> dict[str, Any]:
    plan = registry.plan(workflow, params)
    if plan.get("status") == "gap":
        return {"workflow": workflow, "result": "gap", "message": plan.get("message")}
    if not enabled:
        return {"workflow": workflow, "result": "plan_only", "plan_id": plan["plan_id"]}
    pid = plan["plan_id"]
    applied = registry.apply(pid, plan["confirmation_token"])
    if applied.get("status") == "error":
        return {"workflow": workflow, "plan_id": pid, "applied": "error", "error": applied}
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
        "rolled_removed": rolled.get("removed_uids"),
        "rolled_failed": rolled.get("failed"),
        "post_verify_still_present": post.get("still_present"),
    }


def build_workflow_params(workflow: str, args: argparse.Namespace, inv: dict[str, str]) -> dict[str, Any]:
    if workflow == "temp_camera":
        return {"display_name_hint": args.hint}
    if workflow == "temp_archive":
        return {"display_name_hint": args.hint}
    if workflow == "temp_av_detector":
        params = {"display_name_hint": args.hint, "video_source_ap": args.video_source_ap or inv["video_source_ap"]}
        if args.detector:
            params["detector"] = args.detector
        return params
    if workflow == "temp_appdata_detector":
        params = {
            "display_name_hint": args.hint,
            "video_source_ap": args.video_source_ap or inv["video_source_ap"],
            "vmda_source_ap": args.vmda_source_ap or inv["vmda_source_ap"],
        }
        if args.detector:
            params["detector"] = args.detector
        return params
    if workflow == "temp_device_template":
        return {"display_name_hint": args.hint, "camera_uid": args.camera_uid or inv["camera_uid"]}
    if workflow == "external_event_inject":
        return {"access_point": args.access_point or inv["detector_ex"], "event_type": args.event_type}
    if workflow == "temp_macro":
        return {"display_name_hint": args.hint}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser)
    parser.add_argument("--enable-live", action="store_true", help="actually call apply/verify/rollback; otherwise plan-only")
    parser.add_argument("--workflow", action="append", help="restrict to specific workflow(s); repeatable; default: all")
    parser.add_argument("--hint", default="smoke", help="display_name_hint passed to workflows that support it")
    parser.add_argument("--detector", default="", help="detector kind override; if empty, each workflow uses its own default (MotionDetection for temp_av_detector, MoveInZone for temp_appdata_detector)")
    parser.add_argument("--video-source-ap", default="", help="override discovered video_source_ap")
    parser.add_argument("--vmda-source-ap", default="", help="override discovered vmda_source_ap")
    parser.add_argument("--camera-uid", default="", help="override discovered camera_uid for temp_device_template")
    parser.add_argument("--access-point", default="", help="override DetectorEx access_point for external_event_inject")
    parser.add_argument("--event-type", default="operator_smoke", help="eventType for external_event_inject")
    args = parser.parse_args()

    cfg = config_from_args(args)
    api = AxxonApiClient(cfg)

    inv = discover_inventory(api, cfg.tls_cn)
    print("# inventory")
    print(json.dumps(inv, indent=2))

    registry = op.OperatorRegistry(
        client_factory=lambda: op.AxxonOperatorClient(api),
        host=f"hosts/{cfg.tls_cn}",
        enabled=args.enable_live,
    )

    workflows = args.workflow or registry.known_workflows()
    results = [cycle(registry, w, build_workflow_params(w, args, inv), args.enable_live) for w in workflows]

    print("\n# results")
    print(json.dumps(results, indent=2, default=str))
    print("\n# audit log")
    for entry in registry.audit_log():
        print(" ", json.dumps(entry, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
