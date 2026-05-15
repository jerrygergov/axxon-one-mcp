#!/usr/bin/env python3
"""Read-only smoke covering Integration APIs 3.0 topics that did not previously have a matrix row.

Topics:
- Legacy HTTP camera statistics (`GET /statistics/{videoSourceId}`)
- gRPC GroupManager.ListGroups (camera/device groups)
- gRPC LogicService.GetActiveAlerts / BatchGetActiveAlerts (alerts lifecycle read side)
- gRPC AuthenticationService.RenewSession / RenewSession2 / CloseSession (bearer token lifecycle)
- gRPC TimeZoneManager.GetTimeZone / BatchGetZones (time sync)
- gRPC ArchiveService.GetCalendar (archive calendar)
- REST `/v1/security/users:self` (current Web-Client user)

Detector mask (5.6.5 in the PDF) is intentionally not exercised separately: it is a
`VisualElement` sub-unit under a detector and is mutated via `ChangeConfig`, which is
already covered by `axxon_config_mutation_smoke.py`.

Every call is read-only or auth-renew-only. CloseSession is exercised on a separate
client instance to avoid invalidating the smoke's own bearer token.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def first_camera_ap(api: AxxonApiClient) -> str:
    api.authenticate_grpc()
    domain_pb2 = api.import_module("axxonsoft.bl.domain.Domain_pb2")
    domain = api.common_stubs()["domain"]
    for page in domain.ListCameras(domain_pb2.ListCamerasRequest(page_size=10), timeout=api.config.timeout):
        for cam in api.message_to_dict(page).get("items", []):
            ap = cam.get("access_point", "")
            if ap:
                return ap
    return ""


def first_storage_source(api: AxxonApiClient) -> str:
    api.authenticate_grpc()
    domain_pb2 = api.import_module("axxonsoft.bl.domain.Domain_pb2")
    domain = api.common_stubs()["domain"]
    for page in domain.ListComponents(domain_pb2.ListComponentsRequest(page_size=500), timeout=api.config.timeout):
        for c in api.message_to_dict(page).get("items", []):
            ap = c.get("access_point", "")
            if "MultimediaStorage" in ap and "/Sources/" in ap:
                return ap
    return ""


def topic(name: str, response: dict[str, Any]) -> dict[str, Any]:
    return {"topic": name, "status": response.get("status"), "ok": response.get("status") == 200}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser)
    args = parser.parse_args()
    cfg = config_from_args(args)
    api = AxxonApiClient(cfg)
    api.authenticate_http_grpc()

    cam_ap = first_camera_ap(api)
    storage_src = first_storage_source(api)
    results: list[dict[str, Any]] = []

    if cam_ap:
        # Legacy /statistics expects the bare three-component video source id (no 'hosts/' prefix).
        legacy_id = cam_ap.removeprefix("hosts/")
        results.append(topic("legacy_http_camera_statistics", api.http_request("GET", f"/statistics/{legacy_id}", None, bearer=True)))
        results.append({
            "topic": "grpc_get_active_alerts",
            **{"status": api.http_grpc("axxonsoft.bl.logic.LogicService.GetActiveAlerts", {"camera_ap": cam_ap}).get("status")},
        })

    results.append({
        "topic": "grpc_group_manager_list_groups",
        "status": api.http_grpc("axxonsoft.bl.groups.GroupManager.ListGroups", {"view": "VIEW_MODE_TREE"}).get("status"),
    })
    results.append({
        "topic": "grpc_batch_get_active_alerts",
        "status": api.http_grpc(
            "axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts", {"nodes": [f"hosts/{cfg.tls_cn}"]}
        ).get("status"),
    })
    results.append({
        "topic": "grpc_time_zone_get",
        "status": api.http_grpc("axxonsoft.bl.tz.TimeZoneManager.GetTimeZone", {}).get("status"),
    })
    results.append({
        "topic": "grpc_time_zones_batch_get",
        "status": api.http_grpc("axxonsoft.bl.tz.TimeZoneManager.BatchGetZones", {}).get("status"),
    })
    if storage_src:
        results.append({
            "topic": "grpc_archive_get_calendar",
            "status": api.http_grpc(
                "axxonsoft.bl.archive.ArchiveService.GetCalendar", {"access_point": storage_src}
            ).get("status"),
        })

    results.append(topic("rest_current_user", api.http_request("GET", "/v1/security/users:self", None, bearer=True)))

    # Token lifecycle on an isolated session so we do not invalidate this script's own bearer.
    side = AxxonApiClient(cfg)
    side.authenticate_http_grpc()
    results.append({
        "topic": "grpc_auth_renew_session",
        "status": side.http_grpc("axxonsoft.bl.auth.AuthenticationService.RenewSession", {}).get("status"),
    })
    results.append({
        "topic": "grpc_auth_renew_session2",
        "status": side.http_grpc("axxonsoft.bl.auth.AuthenticationService.RenewSession2", {}).get("status"),
    })
    results.append({
        "topic": "grpc_auth_close_session",
        "status": side.http_grpc("axxonsoft.bl.auth.AuthenticationService.CloseSession", {}).get("status"),
    })

    summary = {"camera_ap": cam_ap, "storage_source": storage_src, "results": results}
    print(json.dumps(summary, indent=2, default=str))
    return 0 if all(r.get("status") == 200 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
