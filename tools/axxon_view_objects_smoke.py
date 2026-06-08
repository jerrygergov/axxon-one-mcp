#!/usr/bin/env python3
"""Live smoke for Phase 5D view-objects tools.

Default mode verifies read-only tools. ``--mutation`` adds two round-trips:

* Wall: ``temp_wall`` -> ``videowall_change`` -> ``videowall_set_control_data`` -> rollback.
* Map: ``create_map`` -> ``update_markers`` -> rollback.

Mutation mode requires ``AXXON_OPERATOR_APPROVE=1``.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_view_objects import AxxonMcpViewObjects  # noqa: E402

# Minimal 1x1 transparent PNG used as a reversible layout-image probe.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da6360000002000154a24d3b0000000049454e44ae426082"
)


def layout_image_roundtrip(client: Any, layout_id: str) -> dict[str, Any]:
    """Upload, list, then remove a throwaway layout image over direct gRPC.

    Proves non-empty ListLayoutImages without leaving residue on the stand.
    """
    import uuid

    image_id = f"codex-5d-img-{uuid.uuid4()}"
    upload = client.upload_layout_image_grpc(layout_id, image_id, TINY_PNG)
    listed = client.list_layout_images_grpc(layout_id)
    present = any(img.get("id") == image_id for img in (listed.get("images") or []))
    client.remove_layout_images_grpc(layout_id, [image_id])
    after = client.list_layout_images_grpc(layout_id)
    gone = all(img.get("id") != image_id for img in (after.get("images") or []))
    return {
        "status": "ok" if (present and gone) else "gap",
        "layout_id": layout_id,
        "uploaded": upload.get("status"),
        "listed_after_upload": present,
        "rolled_back": gone,
    }


def sanitize(obj: Any, host: str) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if "cookie" in str(key).lower():
                out[key] = "<demo-wall-cookie>"
            else:
                out[key] = sanitize(value, host)
        return out
    if isinstance(obj, list):
        return [sanitize(value, host) for value in obj]
    if isinstance(obj, str):
        text = obj.replace(host, "<demo-host>")
        return re.sub(r"cookie=[^,)]*", "cookie=<demo-wall-cookie>", text, flags=re.IGNORECASE)
    return obj


def first_wall_seq(result: dict[str, Any], fallback: int = 0) -> int:
    values = result.get("wall_seq_numbers") or []
    if not values:
        return fallback
    return int(values[0])


def latest_wall_seq(result: dict[str, Any], fallback: int = 0) -> int:
    values = result.get("wall_seq_numbers") or []
    if not values:
        return fallback
    return int(values[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutation", action="store_true")
    args = parser.parse_args()

    vo = AxxonMcpViewObjects()
    vo.connect_axxon_profile("env")
    vo.client.authenticate_http_grpc()
    host = vo.client.config.host

    results: dict[str, object] = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "<demo-host>",
        "reads": {},
    }

    reads: dict[str, object] = {}
    results["reads"] = reads
    reads["list_layouts_meta"] = vo.list_layouts(view="meta", limit=10)
    layout_id = ""
    layout_items = (reads["list_layouts_meta"] or {}).get("items") or []
    if layout_items:
        layout_id = layout_items[0]["layout_id"]
        reads["get_layout"] = vo.get_layout(layout_id)
        reads["list_layout_images"] = vo.list_layout_images(layout_id)
        writable = next(
            (it["layout_id"] for it in layout_items if it.get("has_write_access")),
            layout_id,
        )
        reads["layout_image_roundtrip"] = layout_image_roundtrip(vo.client, writable)

    reads["list_maps"] = vo.list_maps(limit=10)
    map_id = ""
    map_items = (reads["list_maps"] or {}).get("items") or []
    if map_items:
        map_id = map_items[0]["map_id"]
        reads["get_map"] = vo.get_map(map_id)
        reads["get_map_image"] = vo.get_map_image(map_id)
        reads["get_markers"] = vo.get_markers(map_id)

    reads["list_map_providers"] = vo.list_map_providers()
    reads["list_walls"] = vo.list_walls()

    if args.mutation:
        if os.environ.get("AXXON_OPERATOR_APPROVE") != "1":
            results["mutation"] = {"status": "refused", "reason": "operator_env_not_set"}
            print(json.dumps(sanitize(results, host), indent=2, default=str))
            return 1

        from axxon_api_client import AxxonApiClient
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        api: AxxonApiClient = vo.client
        registry = OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(api),
            host=f"hosts/{api.config.tls_cn}",
            enabled=True,
        )

        wall_plan = registry.plan(
            "temp_wall",
            {"name": "codex-5d-wall", "display_name": "Codex 5D Smoke Wall"},
        )
        wall_applied = registry.apply(wall_plan["plan_id"], wall_plan["confirmation_token"])
        wall_state = registry._state.get(wall_plan["plan_id"], {})
        wall_cookie = (wall_state.get("wall_cookies") or [""])[0]
        wall_id = (wall_applied.get("created_uids") or [""])[0]
        wall_seq = first_wall_seq(wall_state)
        if wall_applied.get("status") == "applied" and wall_cookie and wall_id:
            change_plan = registry.plan(
                "videowall_change",
                {
                    "cookie": wall_cookie,
                    "data_b64": base64.b64encode(b"codex-5d-wall-change").decode("ascii"),
                    "seq_number": wall_seq,
                },
            )
            change_applied = registry.apply(change_plan["plan_id"], change_plan["confirmation_token"])
            control_seq = latest_wall_seq(change_applied, fallback=wall_seq + 1)
            control_plan = registry.plan(
                "videowall_set_control_data",
                {
                    "wall_id": wall_id,
                    "data_b64": base64.b64encode(b"codex-5d-control").decode("ascii"),
                    "seq_number": control_seq,
                },
            )
            control_applied = registry.apply(control_plan["plan_id"], control_plan["confirmation_token"])
        else:
            change_plan = {"status": "skipped"}
            change_applied = {"status": "skipped"}
            control_plan = {"status": "skipped"}
            control_applied = {"status": "skipped"}
        wall_rolled = registry.rollback(wall_plan["plan_id"], wall_plan["rollback_confirmation_token"])
        results["mutation_wall"] = {
            "plan_id": wall_plan["plan_id"],
            "apply": wall_applied,
            "change": {"plan": change_plan, "apply": change_applied},
            "control": {"plan": control_plan, "apply": control_applied},
            "rollback": wall_rolled,
        }

        map_plan = registry.plan("create_map", {"name": "codex-5d-test", "type": "MAP_TYPE_RASTER"})
        map_applied = registry.apply(map_plan["plan_id"], map_plan["confirmation_token"])
        created_map_id = map_plan.get("expected", {}).get("map_id", "")
        if map_applied.get("status") == "applied" and created_map_id:
            markers_plan = registry.plan(
                "update_markers",
                {
                    "map_id": created_map_id,
                    "markers": [
                        {
                            "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                            "position": {"x": 0.5, "y": 0.5},
                            "marker_type": "MARKER_TYPE_CAMERA",
                        }
                    ],
                },
            )
            markers_applied = registry.apply(markers_plan["plan_id"], markers_plan["confirmation_token"])
            results["mutation_markers"] = {"plan": markers_plan, "apply": markers_applied}
        map_rolled = registry.rollback(map_plan["plan_id"], map_plan["rollback_confirmation_token"])
        results["mutation_map"] = {
            "plan_id": map_plan["plan_id"],
            "apply": map_applied,
            "rollback": map_rolled,
        }
        results["audit_log"] = registry.audit_log()

    print(json.dumps(sanitize(results, host), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
