#!/usr/bin/env python3
"""Controlled operator workflows for the Axxon One MCP server.

Each workflow follows the plan/apply/verify/rollback pattern. Planning never calls
the server. Apply requires a known plan_id, a matching confirmation token, and an
explicitly enabled registry (off by default). Every action is recorded in an
in-memory audit log. Workflows are kept small and reuse the verified ChangeConfig
shapes from ``axxon_config_mutation_smoke.py``.
"""

from __future__ import annotations

import base64
import datetime as dt
import os as _os
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


def prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        out["properties"] = properties
    return out


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def prop_int(prop_id: str, value: int) -> dict[str, Any]:
    return {"id": prop_id, "value_int32": value}


def _short_stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%H%M%S%f")[:-3]


PNG_1X1_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
PNG_1X1_SIZE = len(base64.b64decode(PNG_1X1_B64))
ARCHIVE_MAINTENANCE_APPROVE_ENV = "AXXON_ARCHIVE_MAINTENANCE_APPROVE"


def _normalize_map_marker(raw: dict[str, Any]) -> dict[str, Any]:
    marker = dict(raw)
    component_name = str(
        marker.pop("component_name", "")
        or marker.pop("access_point", "")
        or marker.pop("ap", "")
        or marker.pop("marker_id", "")
        or marker.pop("id", "")
    )
    marker.pop("marker_type", None)
    marker.pop("type", None)
    if component_name:
        marker["component_name"] = component_name
    marker.setdefault("position", {"x": 0.5, "y": 0.5})
    marker.setdefault("display_title", False)
    if not any(key.endswith("_marker") for key in marker):
        marker["camera_marker"] = {"video_on": False}
    marker.setdefault("icon_scale", 1.0)
    return marker


def _build_temp_camera_payload(host_uid: str, display_name: str, display_id: str) -> dict[str, Any]:
    return {
        "added": [
            {
                "uid": host_uid,
                "units": [
                    {
                        "type": "DeviceIpint",
                        "properties": [
                            prop_string(
                                "vendor",
                                "Virtual",
                                properties=[prop_string("model", "Virtual several streams", properties=[])],
                            ),
                            prop_string("display_name", display_name, properties=[]),
                            prop_bool("blockingConfiguration", False),
                            prop_string("display_id", display_id, properties=[]),
                        ],
                        "units": [],
                    }
                ],
            }
        ]
    }


def _build_temp_camera_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    stamp = _short_stamp()
    display_name = f"codex-temp-camera-{hint}-{stamp}"
    display_id = "9" + stamp[-3:]
    payload = _build_temp_camera_payload(host_uid, display_name, display_id)
    return {
        "workflow": "temp_camera",
        "risk": "mutation",
        "intent": "create a temporary virtual camera, then remove it",
        "steps": [
            {"operation": "add", "unit_type": "DeviceIpint", "payload": payload},
        ],
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "After apply, every created UID is recorded and removed during rollback.",
        },
        "expected": {"display_name": display_name, "display_id": display_id},
        "confirmation_token": f"CONFIRM-temp_camera",
        "rollback_confirmation_token": f"CONFIRM-temp_camera-rollback",
    }


def _build_temp_archive_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    stamp = _short_stamp()
    display_name = f"codex-temp-archive-{hint}-{stamp}"
    payload = {
        "added": [
            {
                "uid": host_uid,
                "units": [
                    {
                        "type": "MultimediaStorage",
                        "properties": [
                            prop_string("display_name", display_name),
                            prop_string("color", "Gray"),
                            prop_string("storage_type", "object"),
                            prop_int("day_depth", 0),
                        ],
                        "units": [],
                    }
                ],
            }
        ]
    }
    return {
        "workflow": "temp_archive",
        "risk": "mutation",
        "intent": "create a temporary disabled-color object archive, then remove it",
        "steps": [{"operation": "add", "unit_type": "MultimediaStorage", "payload": payload}],
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "Every UID created during apply is recorded and removed during rollback.",
        },
        "expected": {"display_name": display_name},
        "confirmation_token": "CONFIRM-temp_archive",
        "rollback_confirmation_token": "CONFIRM-temp_archive-rollback",
    }


def _property_node_id(prop: dict[str, Any]) -> str:
    return str(prop.get("id") or prop.get("property_id") or prop.get("propertyId") or prop.get("name") or "")


def _full_parameter_properties(params: dict[str, Any]) -> list[dict[str, Any]]:
    raw = params.get("properties")
    if raw is None:
        raw = params.get("parameter_tree")
    if raw is None:
        raw = params.get("parameters")
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = raw.get("properties") if isinstance(raw.get("properties"), list) else [raw]
    if not isinstance(raw, list):
        return []
    return [dict(prop) for prop in raw if isinstance(prop, dict)]


def _merge_detector_properties(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reserved = {"display_name", "input"}
    merged = list(base)
    merged.extend(dict(prop) for prop in extra if _property_node_id(prop) not in reserved)
    return merged


def _detector_extension_properties(params: dict[str, Any]) -> list[dict[str, Any]]:
    reserved = {"display_name", "input"}
    return [prop for prop in _full_parameter_properties(params) if _property_node_id(prop) not in reserved]


def _schema_source(params: dict[str, Any]) -> Any:
    return params.get("schema_source") or params.get("schema_provenance") or "operator-local-payload"


def _payload_unit_properties(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload["added"][0]["units"][0]["properties"]


def _find_property(properties: list[dict[str, Any]], prop_id: str) -> dict[str, Any] | None:
    for prop in properties:
        if _property_node_id(prop) == prop_id:
            return prop
    return None


def _property_string_value(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    return str(prop.get("value_string") or prop.get("value") or "")


def _created_unit_uid_for_step(plan: dict[str, Any], created_uids: list[str], created_kinds: list[str], step_index: int) -> str:
    unit_uids = [uid for uid, kind in zip(created_uids, created_kinds) if kind == "unit"]
    unit_add_index = 0
    for idx, step in enumerate(plan.get("steps") or []):
        if step.get("operation") != "add":
            continue
        if idx == step_index:
            return unit_uids[unit_add_index] if unit_add_index < len(unit_uids) else ""
        unit_add_index += 1
    return ""


def _detector_checks_for_plan(client: Any, plan: dict[str, Any], created_uids: list[str], created_kinds: list[str]) -> dict[str, bool] | None:
    workflow = plan.get("workflow")
    if workflow not in {"create_av_detector_full", "create_appdata_detector_full"}:
        return None
    expected = plan.get("expected") or {}
    target_type = "AppDataDetector" if workflow == "create_appdata_detector_full" else "AVDetector"
    target_unit: dict[str, Any] | None = None
    for uid, kind in zip(created_uids, created_kinds):
        if kind != "unit":
            continue
        payload = client.read_unit(uid)
        for unit in payload.get("units") or []:
            if unit.get("type") == target_type:
                target_unit = unit
                break
        if target_unit is not None:
            break
    checks = {
        "display_name": False,
        "detector": False,
        "video_source_ap": False,
    }
    if target_unit is None:
        if target_type == "AppDataDetector":
            checks["vmda_source_ap"] = False
        return checks
    properties = target_unit.get("properties") or []
    display_prop = _find_property(properties, "display_name")
    input_prop = _find_property(properties, "input")
    input_properties = input_prop.get("properties") if isinstance(input_prop, dict) else []
    if not isinstance(input_properties, list):
        input_properties = []
    camera_ref = _find_property(input_properties, "camera_ref")
    camera_ref_properties = camera_ref.get("properties") if isinstance(camera_ref, dict) else []
    if not isinstance(camera_ref_properties, list):
        camera_ref_properties = []
    streaming_id = _find_property(camera_ref_properties, "streaming_id")
    detector_prop = _find_property(input_properties, "detector")
    checks["display_name"] = _property_string_value(display_prop) == str(expected.get("display_name") or "")
    checks["detector"] = _property_string_value(detector_prop) == str(expected.get("detector") or "")
    checks["video_source_ap"] = _property_string_value(camera_ref) == str(expected.get("video_source_ap") or "")
    if target_type == "AppDataDetector":
        expected_vmda = str(expected.get("vmda_source_ap") or "")
        actual_vmda = _property_string_value(streaming_id)
        if expected_vmda == "<chain-created from step 0>":
            chained_uid = _created_unit_uid_for_step(plan, created_uids, created_kinds, 0)
            expected_vmda = f"{chained_uid}/SourceEndpoint.vmda" if chained_uid else ""
        checks["vmda_source_ap"] = actual_vmda == expected_vmda
    return checks


def _infer_parent_uid(uid: str, fallback: str) -> str:
    if "/" in uid:
        return uid.rsplit("/", 1)[0]
    return fallback


def _snapshot_unit_from_read(payload: dict[str, Any], target_uid: str, fallback_parent_uid: str) -> dict[str, Any] | None:
    units = payload.get("units") or []
    if not units:
        return None
    raw_unit = dict(units[0])
    unit = {
        "uid": target_uid,
        "type": raw_unit.get("type", ""),
        "properties": list(raw_unit.get("properties") or []),
        "units": list(raw_unit.get("units") or []),
    }
    parent_uid = str(raw_unit.get("parent_uid") or raw_unit.get("parentUid") or "").strip()
    if not parent_uid:
        parent_uid = _infer_parent_uid(target_uid, fallback_parent_uid)
    return {
        "target_uid": target_uid,
        "parent_uid": parent_uid,
        "unit": unit,
    }


def _restore_payload_for_snapshot(snapshot: dict[str, Any], *, target_present: bool) -> dict[str, Any]:
    unit = dict(snapshot["unit"])
    uid = str(snapshot["target_uid"])
    restore_unit = {
        "uid": uid,
        "type": unit.get("type", ""),
        "properties": list(unit.get("properties") or []),
        "units": list(unit.get("units") or []),
    }
    if target_present:
        return {"changed": [restore_unit]}
    return {"added": [{"uid": snapshot.get("parent_uid") or _infer_parent_uid(uid, ""), "units": [restore_unit]}]}


def _unit_matches_snapshot(unit: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    expected = dict(snapshot.get("unit") or {})
    expected_parent_uid = str(snapshot.get("parent_uid") or "").strip()
    actual_parent_uid = str(unit.get("parent_uid") or unit.get("parentUid") or "").strip()
    if not actual_parent_uid:
        target_uid = str(unit.get("uid") or snapshot.get("target_uid") or expected.get("uid") or "")
        actual_parent_uid = _infer_parent_uid(target_uid, expected_parent_uid)
    if expected_parent_uid and actual_parent_uid != expected_parent_uid:
        return False
    return (
        unit.get("type", "") == expected.get("type", "")
        and list(unit.get("properties") or []) == list(expected.get("properties") or [])
        and list(unit.get("units") or []) == list(expected.get("units") or [])
    )


def _property_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def _requested_property_checks(actual_properties: list[dict[str, Any]], requested_properties: list[dict[str, Any]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for requested in requested_properties:
        prop_id = _property_node_id(requested)
        actual = _find_property(actual_properties, prop_id)
        checks[prop_id] = bool(actual and _property_matches(actual, requested))
    return checks


def _property_child_nodes(prop: dict[str, Any]) -> list[dict[str, Any]]:
    raw = prop.get("properties")
    if raw is None:
        raw = prop.get("parameter_tree")
    if raw is None:
        raw = prop.get("parameters")
    if isinstance(raw, dict):
        raw = raw.get("properties") if isinstance(raw.get("properties"), list) else [raw]
    if not isinstance(raw, list):
        return []
    return [child for child in raw if isinstance(child, dict)]


def _descriptor_property_ids(descriptor: Any) -> set[str]:
    if isinstance(descriptor, dict):
        raw = descriptor.get("properties") or descriptor.get("parameter_tree") or descriptor.get("parameters") or []
    else:
        raw = descriptor
    if isinstance(raw, dict):
        raw = raw.get("properties") if isinstance(raw.get("properties"), list) else [raw]
    if not isinstance(raw, list):
        return set()
    return set(_property_paths([prop for prop in raw if isinstance(prop, dict)]))


def _noop_archive_volume_id(volume_id: str) -> bool:
    return volume_id.startswith("codex-nonexistent-")


def _safe_volume_ids(params: dict[str, Any]) -> set[str]:
    raw = params.get("safe_volume_ids") or params.get("safe_volumes") or params.get("fixture_volume_ids") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def _has_safe_volume_declaration(params: dict[str, Any], real_volume_ids: list[str]) -> bool:
    safe_ids = _safe_volume_ids(params)
    return bool(real_volume_ids) and all(volume_id in safe_ids for volume_id in real_volume_ids)


def _av_detector_payload(
    host_uid: str,
    display_name: str,
    video_source_ap: str,
    detector_kind: str,
    properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_properties = [
        prop_string("display_name", display_name),
        prop_string(
            "input",
            "Video",
            properties=[
                prop_string(
                    "camera_ref",
                    video_source_ap,
                    properties=[prop_string("streaming_id", video_source_ap)],
                ),
                prop_string("detector", detector_kind),
            ],
        ),
    ]
    return {
        "added": [
            {
                "uid": host_uid,
                "units": [
                    {
                        "type": "AVDetector",
                        "properties": _merge_detector_properties(base_properties, properties or []),
                        "units": [],
                    }
                ],
            }
        ]
    }


def _build_temp_av_detector_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Temp AVDetector requires a real video source AP, which the caller must supply."""
    video_source_ap = str(params.get("video_source_ap") or "").strip()
    if not video_source_ap:
        return {
            "status": "gap",
            "workflow": "temp_av_detector",
            "message": "temp_av_detector requires params.video_source_ap (e.g. hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0)",
        }
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    detector_kind = str(params.get("detector") or "MotionDetection").strip() or "MotionDetection"
    stamp = _short_stamp()
    display_name = f"codex-temp-{detector_kind}-{hint}-{stamp}"
    payload = _av_detector_payload(host_uid, display_name, video_source_ap, detector_kind)
    return {
        "workflow": "temp_av_detector",
        "risk": "mutation",
        "intent": f"create a temporary {detector_kind} AVDetector bound to the given video source, then remove it",
        "steps": [{"operation": "add", "unit_type": "AVDetector", "payload": payload}],
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "Every UID created during apply is recorded and removed during rollback.",
        },
        "expected": {"display_name": display_name, "detector": detector_kind, "video_source_ap": video_source_ap},
        "confirmation_token": "CONFIRM-temp_av_detector",
        "rollback_confirmation_token": "CONFIRM-temp_av_detector-rollback",
    }


def _appdata_payload(
    host_uid: str,
    display_name: str,
    video_source_ap: str,
    vmda_source_ap: str,
    detector_kind: str,
    properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_properties = [
        prop_string("display_name", display_name),
        prop_string(
            "input",
            "TargetList",
            properties=[
                prop_string(
                    "camera_ref",
                    video_source_ap,
                    properties=[prop_string("streaming_id", vmda_source_ap)],
                ),
                prop_string("detector", detector_kind),
            ],
        ),
    ]
    return {
        "added": [
            {
                "uid": host_uid,
                "units": [
                    {
                        "type": "AppDataDetector",
                        "properties": _merge_detector_properties(base_properties, properties or []),
                        "units": [],
                    }
                ],
            }
        ]
    }


def _scene_avdetector_payload(host_uid: str, display_name: str, video_source_ap: str) -> dict[str, Any]:
    return _av_detector_payload(host_uid, display_name, video_source_ap, "SceneDescription")


def _build_temp_appdata_detector_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Temp AppDataDetector. Requires a video source AP; if vmda is missing, chain-creates a SceneDescription AVDetector first."""
    video_source_ap = str(params.get("video_source_ap") or "").strip()
    vmda_source_ap = str(params.get("vmda_source_ap") or "").strip()
    if not video_source_ap:
        return {
            "status": "gap",
            "workflow": "temp_appdata_detector",
            "message": "temp_appdata_detector requires params.video_source_ap (e.g. hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0); vmda_source_ap is optional and will be chain-created from a SceneDescription AVDetector if missing",
        }
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    detector_kind = str(params.get("detector") or "MoveInZone").strip() or "MoveInZone"
    stamp = _short_stamp()
    appdata_name = f"codex-temp-appdata-{detector_kind}-{hint}-{stamp}"
    steps: list[dict[str, Any]] = []
    if not vmda_source_ap:
        scene_name = f"codex-temp-scene-for-{hint}-{stamp}"
        steps.append({
            "operation": "add",
            "unit_type": "AVDetector",
            "payload": _scene_avdetector_payload(host_uid, scene_name, video_source_ap),
        })
        appdata_step = {
            "operation": "add",
            "unit_type": "AppDataDetector",
            "resolve_vmda_from_step": 0,
            "appdata_template": {
                "host_uid": host_uid,
                "display_name": appdata_name,
                "video_source_ap": video_source_ap,
                "detector_kind": detector_kind,
            },
            "payload": None,
        }
        steps.append(appdata_step)
    else:
        steps.append({
            "operation": "add",
            "unit_type": "AppDataDetector",
            "payload": _appdata_payload(host_uid, appdata_name, video_source_ap, vmda_source_ap, detector_kind),
        })
    return {
        "workflow": "temp_appdata_detector",
        "risk": "mutation",
        "intent": f"create a temporary {detector_kind} AppDataDetector bound to a vmda source (chain-creating a SceneDescription AVDetector if no vmda source provided), then remove it",
        "steps": steps,
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "Every UID created during apply is recorded and removed during rollback in reverse order.",
        },
        "expected": {
            "display_name": appdata_name,
            "detector": detector_kind,
            "video_source_ap": video_source_ap,
            "vmda_source_ap": vmda_source_ap or "<chain-created from step 0>",
        },
        "confirmation_token": "CONFIRM-temp_appdata_detector",
        "rollback_confirmation_token": "CONFIRM-temp_appdata_detector-rollback",
    }


def _build_create_av_detector_full_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent AVDetector creation using caller-supplied detector parameter properties."""
    display_name = str(params.get("display_name") or params.get("name") or "").strip()
    if not display_name:
        return {
            "status": "gap",
            "workflow": "create_av_detector_full",
            "message": "create_av_detector_full requires params.display_name (or params.name)",
        }
    video_source_ap = str(params.get("video_source_ap") or "").strip()
    if not video_source_ap:
        return {
            "status": "gap",
            "workflow": "create_av_detector_full",
            "message": "create_av_detector_full requires params.video_source_ap",
        }
    detector_kind = str(params.get("detector") or "MotionDetection").strip() or "MotionDetection"
    extra_properties = _detector_extension_properties(params)
    payload = _av_detector_payload(host_uid, display_name, video_source_ap, detector_kind, extra_properties)
    detector_properties = _payload_unit_properties(payload)
    return {
        "workflow": "create_av_detector_full",
        "persistent": True,
        "caller_owns_lifecycle": True,
        "risk": "mutation",
        "intent": f"create a persistent {detector_kind} AVDetector bound to the given video source",
        "steps": [{"operation": "add", "unit_type": "AVDetector", "payload": payload}],
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "Persistent: rollback removes created detector units in reverse order if caller explicitly invokes.",
        },
        "expected": {
            "display_name": display_name,
            "detector": detector_kind,
            "video_source_ap": video_source_ap,
        },
        "source_bindings": {"video_source_ap": video_source_ap},
        "schema_source": _schema_source(params),
        "diff": {"added": [{"unit_type": "AVDetector", "properties": detector_properties}]},
        "confirmation_token": "CONFIRM-create_av_detector_full",
        "rollback_confirmation_token": "CONFIRM-create_av_detector_full-rollback",
    }


def _build_create_appdata_detector_full_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent AppDataDetector creation with optional chain-created SceneDescription VMDA source."""
    display_name = str(params.get("display_name") or params.get("name") or "").strip()
    if not display_name:
        return {
            "status": "gap",
            "workflow": "create_appdata_detector_full",
            "message": "create_appdata_detector_full requires params.display_name (or params.name)",
        }
    video_source_ap = str(params.get("video_source_ap") or "").strip()
    if not video_source_ap:
        return {
            "status": "gap",
            "workflow": "create_appdata_detector_full",
            "message": "create_appdata_detector_full requires params.video_source_ap",
        }
    vmda_source_ap = str(params.get("vmda_source_ap") or "").strip()
    detector_kind = str(params.get("detector") or "MoveInZone").strip() or "MoveInZone"
    extra_properties = _detector_extension_properties(params)
    steps: list[dict[str, Any]] = []
    diff_added: list[dict[str, Any]] = []
    expected_vmda_source_ap = vmda_source_ap or "<chain-created from step 0>"
    if not vmda_source_ap:
        scene_display_name = str(params.get("scene_display_name") or f"{display_name}-SceneDescription").strip()
        scene_payload = _scene_avdetector_payload(host_uid, scene_display_name, video_source_ap)
        scene_properties = _payload_unit_properties(scene_payload)
        steps.append({
            "operation": "add",
            "unit_type": "AVDetector",
            "payload": scene_payload,
        })
        diff_added.append({"unit_type": "AVDetector", "properties": scene_properties})
        steps.append({
            "operation": "add",
            "unit_type": "AppDataDetector",
            "resolve_vmda_from_step": 0,
            "appdata_template": {
                "host_uid": host_uid,
                "display_name": display_name,
                "video_source_ap": video_source_ap,
                "detector_kind": detector_kind,
                "properties": extra_properties,
            },
            "payload": None,
        })
    else:
        payload = _appdata_payload(host_uid, display_name, video_source_ap, vmda_source_ap, detector_kind, extra_properties)
        steps.append({"operation": "add", "unit_type": "AppDataDetector", "payload": payload})
    appdata_diff_payload = _appdata_payload(
        host_uid,
        display_name,
        video_source_ap,
        expected_vmda_source_ap,
        detector_kind,
        extra_properties,
    )
    diff_added.append({"unit_type": "AppDataDetector", "properties": _payload_unit_properties(appdata_diff_payload)})
    return {
        "workflow": "create_appdata_detector_full",
        "persistent": True,
        "caller_owns_lifecycle": True,
        "risk": "mutation",
        "intent": f"create a persistent {detector_kind} AppDataDetector bound to a vmda source",
        "steps": steps,
        "rollback": {
            "strategy": "remove_created_uids",
            "description": "Persistent: rollback removes created detector units in reverse order if caller explicitly invokes.",
        },
        "expected": {
            "display_name": display_name,
            "detector": detector_kind,
            "video_source_ap": video_source_ap,
            "vmda_source_ap": expected_vmda_source_ap,
        },
        "source_bindings": {
            "video_source_ap": video_source_ap,
            "vmda_source_ap": expected_vmda_source_ap,
        },
        "schema_source": _schema_source(params),
        "diff": {"added": diff_added},
        "confirmation_token": "CONFIRM-create_appdata_detector_full",
        "rollback_confirmation_token": "CONFIRM-create_appdata_detector_full-rollback",
    }


def prop_double(prop_id: str, value: float) -> dict[str, Any]:
    return {"id": prop_id, "value_double": value}


def _build_temp_device_template_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Temp device template requires an existing camera UID to attach to."""
    camera_uid = str(params.get("camera_uid") or "").strip()
    if not camera_uid:
        return {
            "status": "gap",
            "workflow": "temp_device_template",
            "message": "temp_device_template requires params.camera_uid (e.g. hosts/Server/DeviceIpint.1)",
        }
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    stamp = _short_stamp()
    template_id = f"codex-{uuid.uuid4()}"
    template_name = f"codex-template-{hint}-{stamp}"
    template_body = {
        "id": template_id,
        "name": template_name,
        "unit": {
            "uid": camera_uid,
            "type": "DeviceIpint",
            "properties": [
                prop_double("geoLocationLatitude", 35.0),
                prop_double("geoLocationLongitude", 45.0),
            ],
            "units": [],
            "opaque_params": [{"id": "color", "value_string": "#00bcd4", "properties": []}],
        },
    }
    payload = {"created": [template_body]}
    return {
        "workflow": "temp_device_template",
        "risk": "mutation",
        "intent": f"create a temporary device template attached to {camera_uid}, then remove it",
        "steps": [{"operation": "add_template", "unit_type": "DeviceTemplate", "payload": payload, "template_id": template_id}],
        "rollback": {
            "strategy": "remove_created_template_ids",
            "description": "The template ID created during apply is removed during rollback.",
        },
        "expected": {"template_id": template_id, "template_name": template_name, "camera_uid": camera_uid},
        "confirmation_token": "CONFIRM-temp_device_template",
        "rollback_confirmation_token": "CONFIRM-temp_device_template-rollback",
    }


def _build_external_event_inject_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """External event injection via /v1/detectors/external:raiseOccasionalEvent."""
    access_point = str(params.get("access_point") or "").strip()
    if not access_point:
        return {
            "status": "gap",
            "workflow": "external_event_inject",
            "message": "external_event_inject requires params.access_point (e.g. hosts/Server/DetectorEx.1/EventSupplier)",
        }
    event_type = str(params.get("event_type") or "test").strip() or "test"
    stamp = _short_stamp()
    event_id = f"codex-{uuid.uuid4()}"
    timestamp = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    body = {
        "accessPoint": access_point,
        "eventType": event_type,
        "timestamp": timestamp,
        "data": {"codex_marker": f"codex-event-{stamp}", "source": "operator-workflow"},
        "eventId": event_id,
        "eventState": "HAPPENED",
    }
    return {
        "workflow": "external_event_inject",
        "risk": "mutation",
        "intent": f"inject a one-shot external event of type {event_type} at {access_point}",
        "steps": [
            {
                "operation": "http_post",
                "path": "/v1/detectors/external:raiseOccasionalEvent",
                "body": body,
            }
        ],
        "rollback": {
            "strategy": "noop",
            "description": "External event injection is one-shot; no server-side state to undo.",
        },
        "expected": {"access_point": access_point, "event_type": event_type, "event_id": event_id},
        "confirmation_token": "CONFIRM-external_event_inject",
        "rollback_confirmation_token": "CONFIRM-external_event_inject-rollback",
    }


def _build_temp_macro_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Disabled, empty, temporary LogicService macro. Self-contained: no fixture needed."""
    hint = str(params.get("display_name_hint") or "smoke").strip() or "smoke"
    stamp = _short_stamp()
    macro_id = str(uuid.uuid4())
    macro_name = f"codex-temp-macro-{hint}-{stamp}"
    payload = {
        "added_macros": [
            {
                "guid": macro_id,
                "name": macro_name,
                "mode": {"enabled": False, "is_add_to_menu": False, "common": {}},
            }
        ]
    }
    return {
        "workflow": "temp_macro",
        "risk": "mutation",
        "intent": "create a disabled empty LogicService macro, then remove it",
        "steps": [{"operation": "add_macro", "unit_type": "Macro", "payload": payload, "macro_id": macro_id}],
        "rollback": {
            "strategy": "remove_created_macro_ids",
            "description": "The macro GUID created during apply is removed during rollback via ChangeMacros.removed_macros.",
        },
        "expected": {"macro_id": macro_id, "macro_name": macro_name},
        "confirmation_token": "CONFIRM-temp_macro",
        "rollback_confirmation_token": "CONFIRM-temp_macro-rollback",
    }


def _build_create_camera_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent camera. Caller owns lifecycle. Optional ip/login/password for IP cameras; Virtual model otherwise."""
    name = str(params.get("display_name") or params.get("name") or "").strip()
    if not name:
        return {
            "status": "gap",
            "workflow": "create_camera",
            "message": "create_camera requires params.display_name (or params.name)",
        }
    vendor = str(params.get("vendor") or "Virtual").strip() or "Virtual"
    model = str(params.get("model") or "Virtual several streams").strip() or "Virtual several streams"
    display_id = str(params.get("display_id") or "").strip() or ("8" + _short_stamp()[-3:])
    ip = str(params.get("ip") or "").strip()
    login = str(params.get("login") or "").strip()
    password = str(params.get("password") or "").strip()
    props = [
        prop_string("vendor", vendor, properties=[prop_string("model", model, properties=[])]),
        prop_string("display_name", name, properties=[]),
        prop_bool("blockingConfiguration", False),
        prop_string("display_id", display_id, properties=[]),
    ]
    if ip:
        props.append(prop_string("ip", ip))
    if login:
        props.append(prop_string("credentials", "default", properties=[
            prop_string("login", login),
            prop_string("password", password),
        ]))
    payload = {"added": [{"uid": host_uid, "units": [{"type": "DeviceIpint", "properties": props, "units": []}]}]}
    return {
        "workflow": "create_camera",
        "persistent": True,
        "risk": "mutation",
        "intent": f"create a persistent camera {name} ({vendor}/{model})",
        "steps": [{"operation": "add", "unit_type": "DeviceIpint", "payload": payload}],
        "rollback": {"strategy": "remove_created_uids", "description": "Persistent: rollback only if caller explicitly invokes."},
        "expected": {"display_name": name, "vendor": vendor, "model": model, "display_id": display_id},
        "confirmation_token": "CONFIRM-create_camera",
        "rollback_confirmation_token": "CONFIRM-create_camera-rollback",
    }


def _build_create_macro_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent macro. Caller may supply name/enabled/conditions/actions."""
    name = str(params.get("name") or params.get("display_name") or "").strip()
    if not name:
        return {
            "status": "gap",
            "workflow": "create_macro",
            "message": "create_macro requires params.name",
        }
    enabled = bool(params.get("enabled", False))
    macro_id = str(params.get("guid") or uuid.uuid4())
    macro: dict[str, Any] = {
        "guid": macro_id,
        "name": name,
        "mode": {"enabled": enabled, "is_add_to_menu": False, "common": {}},
    }
    if params.get("conditions"):
        macro["conditions"] = list(params["conditions"])
    if params.get("actions"):
        macro["actions"] = list(params["actions"])
    payload = {"added_macros": [macro]}
    return {
        "workflow": "create_macro",
        "persistent": True,
        "risk": "mutation",
        "intent": f"create a persistent macro {name} (enabled={enabled})",
        "steps": [{"operation": "add_macro", "unit_type": "Macro", "payload": payload, "macro_id": macro_id}],
        "rollback": {"strategy": "remove_created_macro_ids", "description": "Persistent: rollback only if caller explicitly invokes."},
        "expected": {"macro_id": macro_id, "name": name, "enabled": enabled},
        "confirmation_token": "CONFIRM-create_macro",
        "rollback_confirmation_token": "CONFIRM-create_macro-rollback",
    }


def _build_create_layout_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent layout via LayoutManager.Update (created list).

    ``cells`` is a list of either (a) access-point strings — placed in row-major order
    in a uniform grid of ``rows``x``cols``, or (b) dicts with explicit ``position``,
    ``width``, ``height`` floats in [0,1].
    """
    name = str(params.get("name") or params.get("display_name") or "").strip()
    if not name:
        return {
            "status": "gap",
            "workflow": "create_layout",
            "message": "create_layout requires params.name",
        }
    cells = list(params.get("cells") or [])
    layout_id = str(params.get("layout_id") or uuid.uuid4())
    grid_rows = max(1, int(params.get("rows") or 2))
    grid_cols = max(1, int(params.get("cols") or 2))
    cell_w = 1.0 / grid_cols
    cell_h = 1.0 / grid_rows
    cells_payload: dict[str, Any] = {}
    for idx, cell in enumerate(cells):
        if isinstance(cell, str):
            ap = cell
            position = idx
            width = cell_w
            height = cell_h
        else:
            ap = str(cell.get("access_point") or cell.get("camera") or "")
            position = int(cell.get("position", idx))
            width = float(cell.get("width", cell_w))
            height = float(cell.get("height", cell_h))
        if not ap:
            continue
        cells_payload[str(position)] = {
            "position": position,
            "dimensions": {"width": width, "height": height},
            "right_spring": 1.0,
            "bottom_spring": 1.0,
            "items": [{"access_point": ap}],
        }
    body = {
        "id": layout_id,
        "display_name": name,
        "is_user_defined": True,
        "is_for_alarm": False,
        "cells": cells_payload,
    }
    payload = {"created": [body]}
    return {
        "workflow": "create_layout",
        "persistent": True,
        "caller_owns_lifecycle": True,
        "risk": "mutation",
        "intent": f"create a persistent layout {name} ({grid_rows}x{grid_cols}, {len(cells_payload)} cells)",
        "steps": [{"operation": "add_layout", "unit_type": "Layout", "payload": payload, "layout_id": layout_id}],
        "rollback": {"strategy": "remove_created_layout_ids", "description": "Persistent: rollback only if caller explicitly invokes."},
        "expected": {"layout_id": layout_id, "name": name, "cell_count": len(cells_payload)},
        "confirmation_token": "CONFIRM-create_layout",
        "rollback_confirmation_token": "CONFIRM-create_layout-rollback",
    }


def _build_update_layout_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    layout_id = str(params.get("layout_id") or "").strip()
    if not layout_id:
        return {
            "status": "gap",
            "workflow": "update_layout",
            "message": "update_layout requires params.layout_id",
        }
    etag = str(params.get("etag") or "")
    body = dict(params.get("body") or {})
    updated_entry: dict[str, Any] = {"meta": {"layout_id": layout_id, "etag": etag}, "body": body}
    return {
        "workflow": "update_layout",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update layout {layout_id} (etag={etag[:8] or 'none'})",
        "steps": [{"operation": "update_layout", "payload": {"updated": [updated_entry]}, "layout_id": layout_id}],
        "rollback": {
            "strategy": "restore_layout_snapshot",
            "description": "Pre-apply snapshot captured via BatchGetLayouts; rollback re-applies.",
        },
        "expected": {"layout_id": layout_id, "body_keys": sorted(body.keys())},
        "confirmation_token": "CONFIRM-update_layout",
        "rollback_confirmation_token": "CONFIRM-update_layout-rollback",
    }


def _build_delete_layout_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    layout_id = str(params.get("layout_id") or "").strip()
    if not layout_id:
        return {
            "status": "gap",
            "workflow": "delete_layout",
            "message": "delete_layout requires params.layout_id",
        }
    return {
        "workflow": "delete_layout",
        "persistent": True,
        "risk": "mutation",
        "intent": f"delete layout {layout_id}",
        "steps": [{"operation": "update_layout", "payload": {"removed_layouts": [layout_id]}, "layout_id": layout_id}],
        "rollback": {
            "strategy": "restore_layout_snapshot",
            "description": "Pre-apply snapshot re-adds via created[].",
        },
        "expected": {"layout_id": layout_id},
        "confirmation_token": "CONFIRM-delete_layout",
        "rollback_confirmation_token": "CONFIRM-delete_layout-rollback",
    }


def _build_set_unit_properties_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Edit properties on an existing unit via ChangeConfig.changed[]. Covers detector parameter changes."""
    uid = str(params.get("uid") or "").strip()
    properties = list(params.get("properties") or [])
    if not uid or not properties:
        return {
            "status": "gap",
            "workflow": "set_unit_properties",
            "message": "set_unit_properties requires params.uid and a non-empty params.properties list",
        }
    payload = {"changed": [{"uid": uid, "properties": properties}]}
    return {
        "workflow": "set_unit_properties",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update properties on {uid} (no rollback unless caller invokes)",
        "steps": [{"operation": "change_unit", "unit_type": "any", "payload": payload, "target_uid": uid}],
        "rollback": {"strategy": "noop", "description": "Property changes are not auto-reverted; caller must supply previous values."},
        "expected": {"uid": uid, "property_count": len(properties)},
        "confirmation_token": "CONFIRM-set_unit_properties",
        "rollback_confirmation_token": "CONFIRM-set_unit_properties-rollback",
    }


def _property_paths(properties: list[dict[str, Any]], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for prop in properties:
        prop_id = _property_node_id(prop)
        if not prop_id:
            continue
        path = f"{prefix}.{prop_id}" if prefix else prop_id
        paths.append(path)
        paths.extend(_property_paths(_property_child_nodes(prop), path))
    return paths


def _build_detector_snapshot_change_plan(
    workflow: str,
    uid: str,
    properties: list[dict[str, Any]],
    *,
    target_role: str,
) -> dict[str, Any]:
    if not uid or not properties:
        return {
            "status": "gap",
            "workflow": workflow,
            "message": f"{workflow} requires params.uid and a non-empty params.properties list",
        }
    payload = {"changed": [{"uid": uid, "properties": properties}]}
    return {
        "workflow": workflow,
        "persistent": True,
        "risk": "mutation",
        "intent": f"update {target_role} properties on {uid}",
        "steps": [{
            "operation": "change_detector_snapshot_unit",
            "unit_type": "any",
            "payload": payload,
            "target_uid": uid,
            "target_role": target_role,
        }],
        "rollback": {
            "strategy": "restore_detector_snapshot",
            "description": "Pre-apply unit snapshot is captured via read_unit and restored during rollback.",
        },
        "snapshot_capture": {
            "source": "read_unit",
            "snapshot_key": f"unit:{uid}",
            "target_uid": uid,
            "target_role": target_role,
        },
        "expected": {"uid": uid, "property_count": len(properties), "target_role": target_role},
        "diff": {
            "changed": [{
                "target_uid": uid,
                "target_role": target_role,
                "property_paths": _property_paths(properties),
                "before": "<captured during apply>",
                "after": properties,
            }]
        },
        "confirmation_token": f"CONFIRM-{workflow}",
        "rollback_confirmation_token": f"CONFIRM-{workflow}-rollback",
    }


def _build_update_detector_parameters_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Reversible detector parameter update; captures the target snapshot during apply."""
    uid = str(params.get("uid") or params.get("detector_uid") or "").strip()
    properties = list(params.get("properties") or [])
    return _build_detector_snapshot_change_plan(
        "update_detector_parameters",
        uid,
        properties,
        target_role="detector",
    )


def _build_update_detector_visual_element_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Reversible detector visual-element update; captures the element snapshot during apply."""
    uid = str(params.get("visual_element_uid") or params.get("uid") or "").strip()
    properties = list(params.get("properties") or [])
    return _build_detector_snapshot_change_plan(
        "update_detector_visual_element",
        uid,
        properties,
        target_role="visual_element",
    )


def _build_delete_detector_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Reversible detector delete; captures the target unit during apply and re-adds on rollback."""
    uid = str(params.get("uid") or params.get("detector_uid") or "").strip()
    if not uid:
        return {
            "status": "gap",
            "workflow": "delete_detector",
            "message": "delete_detector requires params.uid",
        }
    parent_uid = str(params.get("parent_uid") or "").strip()
    snapshot_capture: dict[str, Any] = {
        "source": "read_unit",
        "snapshot_key": f"unit:{uid}",
        "target_uid": uid,
        "target_role": "detector",
    }
    if parent_uid:
        snapshot_capture["parent_uid"] = parent_uid
    return {
        "workflow": "delete_detector",
        "persistent": True,
        "risk": "mutation",
        "intent": f"delete detector {uid}",
        "steps": [{
            "operation": "remove_detector_snapshot_unit",
            "target_uid": uid,
            "payload": {"removed": [{"uid": uid}]},
        }],
        "rollback": {
            "strategy": "restore_detector_snapshot",
            "description": "Pre-apply detector snapshot is captured via read_unit and re-added during rollback.",
        },
        "snapshot_capture": snapshot_capture,
        "expected": {"uid": uid, "deleted": True},
        "diff": {
            "removed": [{
                "target_uid": uid,
                "delete": True,
                "before": "<captured during apply>",
            }]
        },
        "confirmation_token": "CONFIRM-delete_detector",
        "rollback_confirmation_token": "CONFIRM-delete_detector-rollback",
    }


def _build_archive_policy_update_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Reversible archive policy update using only descriptor-declared property IDs."""
    uid = str(params.get("uid") or params.get("archive_uid") or "").strip()
    properties = list(params.get("properties") or [])
    if not uid or not properties:
        return {
            "status": "gap",
            "workflow": "archive_policy_update",
            "message": "archive_policy_update requires params.uid and a non-empty params.properties list",
        }
    descriptor = params.get("descriptor") or params.get("archive_descriptor") or params.get("property_descriptor")
    descriptor_ids = _descriptor_property_ids(descriptor)
    if not descriptor_ids:
        return {
            "status": "gap",
            "workflow": "archive_policy_update",
            "message": "archive_policy_update requires descriptor-backed archive policy properties",
        }
    requested_ids = _property_paths(properties)
    missing = [prop_id for prop_id in requested_ids if prop_id not in descriptor_ids]
    if missing:
        return {
            "status": "gap",
            "workflow": "archive_policy_update",
            "message": f"archive_policy_update refuses non descriptor-backed properties: {', '.join(missing)}",
        }
    payload = {"changed": [{"uid": uid, "properties": properties}]}
    return {
        "workflow": "archive_policy_update",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update archive policy properties on {uid}",
        "steps": [{
            "operation": "change_archive_policy_snapshot_unit",
            "unit_type": "MultimediaStorage",
            "payload": payload,
            "target_uid": uid,
        }],
        "rollback": {
            "strategy": "restore_archive_policy_snapshot",
            "description": "Pre-apply archive unit snapshot is captured via read_unit and restored during rollback.",
        },
        "snapshot_capture": {
            "source": "read_unit",
            "snapshot_key": f"unit:{uid}",
            "target_uid": uid,
            "target_role": "archive_policy",
        },
        "expected": {"uid": uid, "property_count": len(properties), "target_role": "archive_policy"},
        "diff": {
            "changed": [{
                "target_uid": uid,
                "target_role": "archive_policy",
                "property_paths": requested_ids,
                "before": "<captured during apply>",
                "after": properties,
                "descriptor_property_ids": sorted(descriptor_ids),
            }]
        },
        "confirmation_token": "CONFIRM-archive_policy_update",
        "rollback_confirmation_token": "CONFIRM-archive_policy_update-rollback",
    }


def _build_archive_maintenance_plan(workflow: str, params: dict[str, Any], *, operation: str) -> dict[str, Any]:
    access_point = str(params.get("access_point") or "").strip()
    volume_ids = [str(item).strip() for item in list(params.get("volume_ids") or []) if str(item).strip()]
    if not access_point or not volume_ids:
        return {
            "status": "gap",
            "workflow": workflow,
            "message": f"{workflow} requires params.access_point and a non-empty params.volume_ids list",
        }
    real_volume_ids = [volume_id for volume_id in volume_ids if not _noop_archive_volume_id(volume_id)]
    if real_volume_ids and not _has_safe_volume_declaration(params, real_volume_ids):
        return {
            "status": "gap",
            "workflow": workflow,
            "message": f"{workflow} refuses real archive volume ids without a fixture/safe-volume declaration",
            "real_volume_ids": real_volume_ids,
        }
    step: dict[str, Any] = {
        "operation": operation,
        "access_point": access_point,
        "volume_ids": volume_ids,
    }
    if operation == "archive_reindex":
        step["full"] = bool(params.get("full", True))
    rollback_strategy = "archive_cancel_reindex" if operation == "archive_reindex" else "noop"
    return {
        "workflow": workflow,
        "persistent": True,
        "risk": "archive_maintenance",
        "intent": f"run archive maintenance {workflow} on {access_point}",
        "archive_maintenance": True,
        "maintenance_approval_env": ARCHIVE_MAINTENANCE_APPROVE_ENV,
        "noop_volume_only": not real_volume_ids,
        "steps": [step],
        "rollback": {
            "strategy": rollback_strategy,
            "description": "Reindex rollback cancels the started reindex; other archive maintenance rollbacks are no-ops.",
        },
        "expected": {
            "access_point": access_point,
            "volume_ids": volume_ids,
            "noop_volume_only": not real_volume_ids,
        },
        "confirmation_token": f"CONFIRM-{workflow}",
        "rollback_confirmation_token": f"CONFIRM-{workflow}-rollback",
    }


def _build_archive_format_volume_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    return _build_archive_maintenance_plan("archive_format_volume", params, operation="archive_format_volume")


def _build_archive_reindex_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    return _build_archive_maintenance_plan("archive_reindex", params, operation="archive_reindex")


def _build_archive_cancel_reindex_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    return _build_archive_maintenance_plan("archive_cancel_reindex", params, operation="archive_cancel_reindex")


def _build_temp_wall_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Ephemeral videowall registration with explicit unregister rollback."""
    name = str(params.get("name") or f"codex-wall-{uuid.uuid4().hex[:8]}")
    display_name = str(params.get("display_name") or name)
    host_name = str(params.get("host_name") or f"codex-host-{uuid.uuid4().hex[:6]}")
    pid = int(params.get("pid") or _os.getpid())
    ppid = int(params.get("ppid") or 1)
    data_b64 = str(params.get("data_b64") or "")
    return {
        "workflow": "temp_wall",
        "persistent": False,
        "risk": "mutation",
        "intent": f"register ephemeral videowall {name} ({display_name})",
        "steps": [
            {
                "operation": "register_wall",
                "params": {
                    "host_name": host_name,
                    "pid": pid,
                    "ppid": ppid,
                    "name": name,
                    "display_name": display_name,
                    "data_b64": data_b64,
                },
            }
        ],
        "rollback": {"strategy": "unregister_wall", "description": "Calls UnregisterWall(cookie)."},
        "expected": {"name": name, "display_name": display_name},
        "confirmation_token": "CONFIRM-temp_wall",
        "rollback_confirmation_token": "CONFIRM-temp_wall-rollback",
    }


def _build_videowall_register_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent videowall registration; caller retains cookie."""
    name = str(params.get("name") or "").strip()
    if not name:
        return {
            "status": "gap",
            "workflow": "videowall_register",
            "message": "videowall_register requires params.name",
        }
    display_name = str(params.get("display_name") or name)
    host_name = str(params.get("host_name") or f"codex-host-{uuid.uuid4().hex[:6]}")
    pid = int(params.get("pid") or _os.getpid())
    ppid = int(params.get("ppid") or 1)
    data_b64 = str(params.get("data_b64") or "")
    return {
        "workflow": "videowall_register",
        "persistent": True,
        "risk": "mutation",
        "intent": f"register persistent videowall {name} ({display_name})",
        "steps": [
            {
                "operation": "register_wall",
                "params": {
                    "host_name": host_name,
                    "pid": pid,
                    "ppid": ppid,
                    "name": name,
                    "display_name": display_name,
                    "data_b64": data_b64,
                },
            }
        ],
        "rollback": {
            "strategy": "unregister_wall",
            "description": "Persistent: caller invokes rollback to unregister.",
        },
        "expected": {"name": name, "display_name": display_name},
        "confirmation_token": "CONFIRM-videowall_register",
        "rollback_confirmation_token": "CONFIRM-videowall_register-rollback",
    }


def _build_videowall_change_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    cookie = str(params.get("cookie") or "").strip()
    if not cookie:
        return {
            "status": "gap",
            "workflow": "videowall_change",
            "message": "videowall_change requires params.cookie",
        }
    data_b64 = str(params.get("data_b64") or "")
    seq_number = int(params.get("seq_number") or 0)
    return {
        "workflow": "videowall_change",
        "persistent": True,
        "risk": "mutation",
        "intent": f"change videowall data (cookie supplied, seq={seq_number})",
        "steps": [
            {
                "operation": "change_wall",
                "params": {"cookie": cookie, "data_b64": data_b64, "seq_number": seq_number},
            }
        ],
        "rollback": {"strategy": "noop", "description": "ChangeWall is a state push; no auto-revert."},
        "expected": {"cookie_present": True, "seq_number": seq_number},
        "confirmation_token": "CONFIRM-videowall_change",
        "rollback_confirmation_token": "CONFIRM-videowall_change-rollback",
    }


def _build_videowall_set_control_data_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    wall_id = str(params.get("wall_id") or "").strip()
    if not wall_id:
        return {
            "status": "gap",
            "workflow": "videowall_set_control_data",
            "message": "videowall_set_control_data requires params.wall_id",
        }
    data_b64 = str(params.get("data_b64") or "")
    seq_number = int(params.get("seq_number") or 0)
    return {
        "workflow": "videowall_set_control_data",
        "persistent": True,
        "risk": "mutation",
        "intent": f"push control data to wall {wall_id} (seq={seq_number})",
        "steps": [
            {
                "operation": "set_control_data",
                "params": {"wall_id": wall_id, "data_b64": data_b64, "seq_number": seq_number},
            }
        ],
        "rollback": {"strategy": "noop", "description": "Control data is a push; no auto-revert."},
        "expected": {"wall_id": wall_id, "seq_number": seq_number},
        "confirmation_token": "CONFIRM-videowall_set_control_data",
        "rollback_confirmation_token": "CONFIRM-videowall_set_control_data-rollback",
    }


def _build_videowall_unregister_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    cookie = str(params.get("cookie") or "").strip()
    if not cookie:
        return {
            "status": "gap",
            "workflow": "videowall_unregister",
            "message": "videowall_unregister requires params.cookie",
        }
    return {
        "workflow": "videowall_unregister",
        "persistent": True,
        "risk": "mutation",
        "intent": "unregister wall (cookie supplied)",
        "steps": [{"operation": "unregister_wall", "params": {"cookie": cookie}}],
        "rollback": {"strategy": "noop", "description": "Unregister is terminal."},
        "expected": {"cookie_present": True},
        "confirmation_token": "CONFIRM-videowall_unregister",
        "rollback_confirmation_token": "CONFIRM-videowall_unregister-rollback",
    }


def _build_create_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "").strip()
    if not name:
        return {"status": "gap", "workflow": "create_map", "message": "create_map requires params.name"}
    map_type = str(params.get("type") or "MAP_TYPE_RASTER")
    map_id = str(params.get("map_id") or uuid.uuid4())
    map_body = dict(params.get("map") or {})
    map_body.setdefault("name", name)
    map_body.setdefault("type", map_type)
    map_body.setdefault("position", {"x": 0.0, "y": 0.0})
    map_body.setdefault("zoom", int(params.get("zoom") or 1))
    map_body.setdefault(
        "image_meta",
        {
            "file_name": "codex-map.png",
            "mime_type": "image/png",
            "size": {"width": 1.0, "height": 1.0},
            "name": "codex-map.png",
            "size_bytes": PNG_1X1_SIZE,
        },
    )
    new_map = {
        "id": map_id,
        "map": map_body,
        "image_data": str(params.get("image_data_b64") or PNG_1X1_B64),
    }
    markers = [_normalize_map_marker(marker) for marker in list(params.get("markers") or [])]
    if markers:
        new_map["markers"] = markers
    return {
        "workflow": "create_map",
        "persistent": True,
        "caller_owns_lifecycle": True,
        "risk": "mutation",
        "intent": f"create persistent map {name} (type={map_type})",
        "steps": [{"operation": "change_maps", "payload": {"created": [new_map]}, "map_id": map_id}],
        "rollback": {"strategy": "change_maps_removed", "description": "Rollback removes the added map by id."},
        "expected": {"map_id": map_id, "name": name, "type": map_type},
        "confirmation_token": "CONFIRM-create_map",
        "rollback_confirmation_token": "CONFIRM-create_map-rollback",
    }


def _build_update_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {"status": "gap", "workflow": "update_map", "message": "update_map requires params.map_id"}
    etag = str(params.get("etag") or "")
    patch = dict(params.get("map") or params.get("patch") or {})
    return {
        "workflow": "update_map",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update map {map_id} (etag={etag[:8] or 'none'})",
        "steps": [{"operation": "change_maps", "payload": {"updated": [{"map_id": map_id, "etag": etag, "map": patch}]}, "map_id": map_id}],
        "rollback": {
            "strategy": "restore_map_snapshot",
            "description": "Pre-apply snapshot captured; rollback re-applies it via changed[].",
        },
        "expected": {"map_id": map_id, "patch_keys": sorted(patch.keys())},
        "confirmation_token": "CONFIRM-update_map",
        "rollback_confirmation_token": "CONFIRM-update_map-rollback",
    }


def _build_delete_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {"status": "gap", "workflow": "delete_map", "message": "delete_map requires params.map_id"}
    return {
        "workflow": "delete_map",
        "persistent": True,
        "risk": "mutation",
        "intent": f"delete map {map_id}",
        "steps": [{"operation": "change_maps", "payload": {"removed": [map_id]}, "map_id": map_id}],
        "rollback": {
            "strategy": "restore_map_snapshot",
            "description": "Pre-apply snapshot re-adds the map via added[].",
        },
        "expected": {"map_id": map_id},
        "confirmation_token": "CONFIRM-delete_map",
        "rollback_confirmation_token": "CONFIRM-delete_map-rollback",
    }


def _build_update_markers_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {
            "status": "gap",
            "workflow": "update_markers",
            "message": "update_markers requires params.map_id",
        }
    markers = [_normalize_map_marker(marker) for marker in list(params.get("markers") or [])]
    return {
        "workflow": "update_markers",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update markers on map {map_id} ({len(markers)} markers)",
        "steps": [{"operation": "update_markers", "params": {"map_id": map_id, "markers": markers}, "map_id": map_id}],
        "rollback": {
            "strategy": "restore_markers_snapshot",
            "description": "Pre-apply snapshot captured via GetMarkers; rollback re-applies.",
        },
        "expected": {"map_id": map_id, "marker_count": len(markers)},
        "confirmation_token": "CONFIRM-update_markers",
        "rollback_confirmation_token": "CONFIRM-update_markers-rollback",
    }


WORKFLOWS: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {
    "temp_camera": _build_temp_camera_plan,
    "temp_archive": _build_temp_archive_plan,
    "temp_av_detector": _build_temp_av_detector_plan,
    "temp_appdata_detector": _build_temp_appdata_detector_plan,
    "create_av_detector_full": _build_create_av_detector_full_plan,
    "create_appdata_detector_full": _build_create_appdata_detector_full_plan,
    "temp_device_template": _build_temp_device_template_plan,
    "external_event_inject": _build_external_event_inject_plan,
    "temp_macro": _build_temp_macro_plan,
    "create_camera": _build_create_camera_plan,
    "create_macro": _build_create_macro_plan,
    "create_layout": _build_create_layout_plan,
    "update_layout": _build_update_layout_plan,
    "delete_layout": _build_delete_layout_plan,
    "set_unit_properties": _build_set_unit_properties_plan,
    "update_detector_parameters": _build_update_detector_parameters_plan,
    "update_detector_visual_element": _build_update_detector_visual_element_plan,
    "delete_detector": _build_delete_detector_plan,
    "archive_policy_update": _build_archive_policy_update_plan,
    "archive_format_volume": _build_archive_format_volume_plan,
    "archive_reindex": _build_archive_reindex_plan,
    "archive_cancel_reindex": _build_archive_cancel_reindex_plan,
    "temp_wall": _build_temp_wall_plan,
    "videowall_register": _build_videowall_register_plan,
    "videowall_change": _build_videowall_change_plan,
    "videowall_set_control_data": _build_videowall_set_control_data_plan,
    "videowall_unregister": _build_videowall_unregister_plan,
    "create_map": _build_create_map_plan,
    "update_map": _build_update_map_plan,
    "delete_map": _build_delete_map_plan,
    "update_markers": _build_update_markers_plan,
}


class AxxonOperatorClient:
    """Adapter that fulfills the OperatorRegistry transport contract.

    Wraps ``AxxonApiClient`` and routes ``ChangeConfig``/``ListUnits`` through the
    authenticated direct gRPC channel. Direct gRPC is preferred over HTTP /grpc
    because some demo stands expose only the gRPC port. Authentication is lazy.
    """

    def __init__(self, api_client: Any) -> None:
        self._client = api_client
        self._authed = False

    def _ensure_auth(self) -> None:
        if not self._authed:
            self._client.authenticate_grpc()
            self._authed = True

    def _config_stub(self) -> Any:
        return self._client.common_stubs()["config"]

    def _config_pb2(self) -> Any:
        return self._client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")

    def change_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        from google.protobuf import json_format

        self._ensure_auth()
        pb2 = self._config_pb2()
        request = pb2.ChangeConfigRequest()
        json_format.ParseDict(payload, request, ignore_unknown_fields=True)
        response = self._config_stub().ChangeConfig(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    def read_unit(self, uid: str) -> dict[str, Any]:
        self._ensure_auth()
        pb2 = self._config_pb2()
        request = pb2.ListUnitsRequest(unit_uids=[uid])
        response = self._config_stub().ListUnits(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    def change_templates(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._client.authenticate_http_grpc()
        response = self._client.http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeTemplates", payload)
        if response.get("status") != 200:
            return {"failed": True, "failed_reason": [response.get("body")]}
        return response.get("body") or {}

    def read_template(self, template_id: str) -> dict[str, Any]:
        self._client.authenticate_http_grpc()
        response = self._client.http_grpc(
            "axxonsoft.bl.config.ConfigurationService.BatchGetTemplates",
            {"items": [{"id": template_id}]},
        )
        if response.get("status") != 200:
            return {"items": []}
        return response.get("body") or {}

    def wait_for_component(self, access_point: str, timeout_seconds: float = 10.0) -> bool:
        """Poll DomainService.ListComponents until ``access_point`` appears or timeout."""
        import time

        self._ensure_auth()
        domain_pb2 = self._client.import_module("axxonsoft.bl.domain.Domain_pb2")
        domain_stub = self._client.common_stubs()["domain"]
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while time.monotonic() < deadline:
            for page in domain_stub.ListComponents(
                domain_pb2.ListComponentsRequest(page_size=500), timeout=self._client.config.timeout
            ):
                for item in self._client.message_to_dict(page).get("items", []):
                    if item.get("access_point") == access_point:
                        return True
            time.sleep(0.5)
        return False

    def _logic_stub(self) -> Any:
        return self._client.stub_from_proto("axxonsoft/bl/logic/LogicService.proto", "LogicService")

    def _logic_pb2(self) -> Any:
        return self._client.import_module("axxonsoft.bl.logic.LogicService_pb2")

    def change_macros(self, payload: dict[str, Any]) -> dict[str, Any]:
        from google.protobuf import json_format

        self._ensure_auth()
        pb2 = self._logic_pb2()
        request = pb2.ChangeMacrosRequest()
        json_format.ParseDict(payload, request, ignore_unknown_fields=True)
        response = self._logic_stub().ChangeMacros(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    def read_macro(self, macro_id: str) -> dict[str, Any]:
        self._ensure_auth()
        pb2 = self._logic_pb2()
        request = pb2.BatchGetMacrosRequest(macros_ids=[macro_id])
        response = self._logic_stub().BatchGetMacros(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    def _layout_stub(self) -> Any:
        return self._client.stub_from_proto("axxonsoft/bl/layout/LayoutManager.proto", "LayoutManager")

    def _layout_pb2(self) -> Any:
        return self._client.import_module("axxonsoft.bl.layout.LayoutManager_pb2")

    def change_layouts(self, payload: dict[str, Any]) -> dict[str, Any]:
        from google.protobuf import json_format

        self._ensure_auth()
        pb2 = self._layout_pb2()
        request = pb2.UpdateRequest()
        json_format.ParseDict(payload, request, ignore_unknown_fields=True)
        response = self._layout_stub().Update(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    def read_layout(self, layout_id: str) -> dict[str, Any]:
        self._ensure_auth()
        pb2 = self._layout_pb2()
        request = pb2.BatchGetLayoutsRequest(items=[pb2.BatchGetLayoutsRequest.Locator(layout_id=layout_id)])
        response = self._layout_stub().BatchGetLayouts(request, timeout=self._client.config.timeout)
        return self._client.message_to_dict(response)

    # --- Phase 5D transport extensions ---

    def change_maps_via_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.change_maps(payload)

    def update_markers_via_api(self, map_id: str, markers: list[dict[str, Any]]) -> dict[str, Any]:
        return self._client.update_markers(map_id, markers)

    def register_wall_via_api(self, **kwargs) -> dict[str, Any]:
        return self._client.register_wall(**kwargs)

    def change_wall_via_api(self, *, cookie: str, data_bytes: bytes, seq_number: int) -> dict[str, Any]:
        return self._client.change_wall(cookie=cookie, data_bytes=data_bytes, seq_number=seq_number)

    def set_control_data_via_api(self, *, wall_id: str, seq_number: int, data_bytes: bytes) -> dict[str, Any]:
        return self._client.set_control_data(wall_id=wall_id, seq_number=seq_number, data_bytes=data_bytes)

    def unregister_wall_via_api(self, cookie: str) -> dict[str, Any]:
        return self._client.unregister_wall(cookie)

    def update_layout_via_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.Update",
            payload,
        )

    def batch_get_maps_via_api(self, map_ids: list[str]) -> dict[str, Any]:
        return self._client.batch_get_maps(map_ids)

    def batch_get_layouts_via_api(self, items: list[dict[str, str]]) -> dict[str, Any]:
        return self._client.batch_get_layouts(items)

    def get_markers_via_api(self, map_id: str) -> dict[str, Any]:
        return self._client.get_markers(map_id)

    def archive_format_volumes_via_api(self, access_point: str, volume_ids: list[str]) -> dict[str, Any]:
        return self._client.archive_format_volumes(access_point, volume_ids)

    def archive_reindex_via_api(self, access_point: str, volume_ids: list[str], *, full: bool = True) -> dict[str, Any]:
        return self._client.archive_reindex(access_point, volume_ids, full=full)

    def archive_cancel_reindex_via_api(self, access_point: str, volume_ids: list[str]) -> dict[str, Any]:
        return self._client.archive_cancel_reindex(access_point, volume_ids)

    def http_post_bearer(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        self._client.authenticate_http_grpc()
        return self._client.http_request("POST", path, body, bearer=True)


@dataclass
class OperatorRegistry:
    """Stateful registry for typed plan/apply/verify/rollback operations.

    The ``client_factory`` returns a transport object exposing ``change_config(payload)``
    and ``read_unit(uid)``. The registry is read-only when ``enabled`` is False; in that
    case ``apply`` and ``rollback`` are rejected even with a known plan_id.
    """

    client_factory: Callable[[], Any]
    host: str = "hosts/Server"
    enabled: bool = True
    _plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    _state: dict[str, dict[str, Any]] = field(default_factory=dict)
    _log: list[dict[str, Any]] = field(default_factory=list)
    _client: Any | None = None

    def ensure_client(self) -> Any:
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def known_workflows(self) -> list[str]:
        return sorted(WORKFLOWS.keys())

    def plan(self, workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        if workflow not in WORKFLOWS:
            gap = {
                "status": "gap",
                "message": f"unknown workflow: {workflow}",
                "known_workflows": self.known_workflows(),
            }
            self._record("plan", workflow=workflow, status="gap")
            return gap
        plan_body = WORKFLOWS[workflow](self.host, params)
        # Builders may return a "gap" record (e.g. missing required fixture parameter).
        if plan_body.get("status") == "gap":
            self._record("plan", workflow=workflow, status="gap")
            return plan_body
        plan_id = f"plan-{uuid.uuid4()}"
        record = {"plan_id": plan_id, "status": "planned", **plan_body}
        self._plans[plan_id] = record
        self._state[plan_id] = {"status": "planned", "created_uids": []}
        self._record("plan", workflow=workflow, plan_id=plan_id)
        return record

    def apply(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plans.get(plan_id)
        if plan is None:
            self._record("apply", plan_id=plan_id, status="rejected", reason="unknown_plan")
            return {"status": "rejected", "message": "unknown plan_id", "plan_id": plan_id}
        if not self.enabled:
            self._record("apply", plan_id=plan_id, status="rejected", reason="disabled")
            return {
                "status": "rejected",
                "message": "operator mutations are disabled; start the MCP server with --enable-operator",
                "plan_id": plan_id,
            }
        if confirmation != plan.get("confirmation_token"):
            self._record("apply", plan_id=plan_id, status="rejected", reason="bad_confirmation")
            return {
                "status": "rejected",
                "message": "confirmation token does not match the plan",
                "plan_id": plan_id,
            }
        if plan.get("archive_maintenance") and _os.environ.get(ARCHIVE_MAINTENANCE_APPROVE_ENV) != "1":
            self._record("apply", plan_id=plan_id, status="rejected", reason="archive_maintenance_env_gate")
            return {
                "status": "rejected",
                "message": f"archive maintenance requires {ARCHIVE_MAINTENANCE_APPROVE_ENV}=1 at apply time",
                "plan_id": plan_id,
            }
        client = self.ensure_client()
        created_uids: list[str] = []
        created_kinds: list[str] = []  # parallel to created_uids: "unit", "template", or "macro"
        step_results: list[list[str]] = []  # uids created by each step (for inter-step dependency resolution)
        wall_cookies: list[str] = []
        wall_seq_numbers: list[int] = []
        snapshots: list[dict[str, Any]] = []

        def store_apply_state(status: str) -> None:
            self._state[plan_id] = {
                "status": status,
                "created_uids": list(created_uids),
                "created_kinds": list(created_kinds),
                "wall_cookies": list(wall_cookies),
                "wall_seq_numbers": list(wall_seq_numbers),
                "snapshots": list(snapshots),
            }

        def capture_snapshot(target_uid: str) -> dict[str, Any] | None:
            capture = plan.get("snapshot_capture") or {}
            parent_uid = str(capture.get("parent_uid") or "").strip() or _infer_parent_uid(target_uid, self.host)
            snapshot = _snapshot_unit_from_read(client.read_unit(target_uid), target_uid, parent_uid)
            if snapshot is not None:
                snapshots.append(snapshot)
            return snapshot

        for step in plan.get("steps", []):
            op = step.get("operation")
            if op == "add":
                resolve_idx = step.get("resolve_vmda_from_step")
                if resolve_idx is not None and step.get("payload") is None:
                    prior_uids = step_results[resolve_idx]
                    if not prior_uids:
                        store_apply_state("error")
                        self._record("apply", plan_id=plan_id, status="error", reason="prior_step_no_uid")
                        return {
                            "status": "error",
                            "message": f"step depends on step {resolve_idx} which produced no UID",
                            "plan_id": plan_id,
                        }
                    vmda_ap = f"{prior_uids[0]}/SourceEndpoint.vmda"
                    if hasattr(client, "wait_for_component"):
                        client.wait_for_component(vmda_ap, timeout_seconds=10.0)
                    tmpl = step["appdata_template"]
                    step_payload = _appdata_payload(
                        tmpl["host_uid"],
                        tmpl["display_name"],
                        tmpl["video_source_ap"],
                        vmda_ap,
                        tmpl["detector_kind"],
                        tmpl.get("properties"),
                    )
                else:
                    step_payload = step["payload"]
                response = client.change_config(step_payload)
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_config_failed")
                    return {
                        "status": "error",
                        "message": "ChangeConfig reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                added = response.get("added", [])
                step_results.append(list(added))
                created_uids.extend(added)
                created_kinds.extend(["unit"] * len(added))
            elif op == "add_template":
                response = client.change_templates(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_templates_failed")
                    return {
                        "status": "error",
                        "message": "ChangeTemplates reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                created = response.get("created") or [step["template_id"]]
                step_results.append(list(created))
                created_uids.extend(created)
                created_kinds.extend(["template"] * len(created))
            elif op == "add_macro":
                response = client.change_macros(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_macros_failed")
                    return {
                        "status": "error",
                        "message": "ChangeMacros reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                created = response.get("created_macro_ids") or [step["macro_id"]]
                step_results.append(list(created))
                created_uids.extend(created)
                created_kinds.extend(["macro"] * len(created))
            elif op == "change_unit":
                response = client.change_config(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_config_failed")
                    return {
                        "status": "error",
                        "message": "ChangeConfig (change_unit) reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                step_results.append([step.get("target_uid", "")])
                # No new UID created; do not record for rollback.
            elif op in {"change_detector_snapshot_unit", "change_archive_policy_snapshot_unit"}:
                target_uid = str(step.get("target_uid") or "")
                if not capture_snapshot(target_uid):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="snapshot_missing")
                    return {"status": "error", "message": "target unit snapshot was not found", "plan_id": plan_id}
                response = client.change_config(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_config_failed")
                    return {
                        "status": "error",
                        "message": "ChangeConfig (snapshot update) reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                step_results.append([target_uid])
            elif op == "remove_detector_snapshot_unit":
                target_uid = str(step.get("target_uid") or "")
                if not capture_snapshot(target_uid):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="snapshot_missing")
                    return {"status": "error", "message": "target unit snapshot was not found", "plan_id": plan_id}
                response = client.change_config(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_config_failed")
                    return {
                        "status": "error",
                        "message": "ChangeConfig (detector delete) reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                step_results.append([target_uid])
            elif op == "add_layout":
                response = client.change_layouts(step["payload"])
                if response.get("failed"):
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_layouts_failed")
                    return {
                        "status": "error",
                        "message": "ChangeLayouts reported failures during apply",
                        "plan_id": plan_id,
                        "failed": response.get("failed", []),
                    }
                # LayoutManager.Update does not echo IDs; trust the client-generated layout_id.
                created = [step["layout_id"]]
                step_results.append(list(created))
                created_uids.extend(created)
                created_kinds.extend(["layout"] * len(created))
            elif op == "http_post":
                response = client.http_post_bearer(step["path"], step["body"])
                if response.get("status") and response["status"] >= 400:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="http_post_failed")
                    return {
                        "status": "error",
                        "message": f"http_post returned status {response['status']}",
                        "plan_id": plan_id,
                    }
                step_results.append([])
            elif op == "register_wall":
                p = step["params"]
                data_bytes = base64.b64decode(p.get("data_b64") or "") if p.get("data_b64") else b""
                response = client.register_wall_via_api(
                    host_name=p["host_name"],
                    pid=p["pid"],
                    ppid=p["ppid"],
                    name=p["name"],
                    display_name=p["display_name"],
                    data_bytes=data_bytes,
                )
                body = response.get("body") if isinstance(response, dict) else {}
                cookie = (body or {}).get("cookie") or ""
                wall_id = (body or {}).get("wall_id") or ""
                if response.get("status") != 200 or not cookie:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="register_wall_failed")
                    return {"status": "error", "message": "RegisterWall failed", "plan_id": plan_id}
                step_results.append([cookie, wall_id])
                if wall_id:
                    created_uids.append(wall_id)
                    created_kinds.append("wall")
                wall_cookies.append(cookie)
                wall_seq_numbers.append(int(body.get("seq_number") or 0))
            elif op == "change_wall":
                p = step["params"]
                response = client.change_wall_via_api(
                    cookie=p["cookie"],
                    data_bytes=base64.b64decode(p.get("data_b64") or ""),
                    seq_number=p["seq_number"],
                )
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_wall_failed")
                    return {"status": "error", "message": "ChangeWall failed", "plan_id": plan_id}
                body = response.get("body") if isinstance(response, dict) else {}
                if (body or {}).get("new_seq_number") is not None:
                    wall_seq_numbers.append(int((body or {}).get("new_seq_number") or 0))
                step_results.append([])
            elif op == "set_control_data":
                p = step["params"]
                response = client.set_control_data_via_api(
                    wall_id=p["wall_id"],
                    seq_number=p["seq_number"],
                    data_bytes=base64.b64decode(p.get("data_b64") or ""),
                )
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="set_control_data_failed")
                    return {"status": "error", "message": "SetControlData failed", "plan_id": plan_id}
                body = response.get("body") if isinstance(response, dict) else {}
                if (body or {}).get("new_seq_number") is not None:
                    wall_seq_numbers.append(int((body or {}).get("new_seq_number") or 0))
                step_results.append([])
            elif op == "unregister_wall":
                p = step["params"]
                response = client.unregister_wall_via_api(p["cookie"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="unregister_wall_failed")
                    return {"status": "error", "message": "UnregisterWall failed", "plan_id": plan_id}
                step_results.append([])
            elif op == "change_maps":
                response = client.change_maps_via_api(step["payload"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="change_maps_failed")
                    return {"status": "error", "message": "ChangeMaps failed", "plan_id": plan_id}
                map_id = step.get("map_id") or ""
                if "created" in step["payload"] and map_id:
                    created_uids.append(map_id)
                    created_kinds.append("map")
                step_results.append([map_id] if map_id else [])
            elif op == "update_markers":
                p = step["params"]
                response = client.update_markers_via_api(p["map_id"], p["markers"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="update_markers_failed")
                    return {"status": "error", "message": "UpdateMarkers failed", "plan_id": plan_id}
                step_results.append([])
            elif op == "update_layout":
                response = client.update_layout_via_api(step["payload"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="update_layout_failed")
                    return {"status": "error", "message": "LayoutManager.Update failed", "plan_id": plan_id}
                layout_id = step.get("layout_id") or ""
                step_results.append([layout_id] if layout_id else [])
            elif op == "archive_format_volume":
                response = client.archive_format_volumes_via_api(step["access_point"], step["volume_ids"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="archive_format_volume_failed")
                    return {"status": "error", "message": "archive format volume failed", "plan_id": plan_id}
                step_results.append([])
            elif op == "archive_reindex":
                response = client.archive_reindex_via_api(
                    step["access_point"],
                    step["volume_ids"],
                    full=bool(step.get("full", True)),
                )
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="archive_reindex_failed")
                    return {"status": "error", "message": "archive reindex failed", "plan_id": plan_id}
                step_results.append([])
            elif op == "archive_cancel_reindex":
                response = client.archive_cancel_reindex_via_api(step["access_point"], step["volume_ids"])
                if response.get("status") != 200:
                    store_apply_state("error")
                    self._record("apply", plan_id=plan_id, status="error", reason="archive_cancel_reindex_failed")
                    return {"status": "error", "message": "archive cancel reindex failed", "plan_id": plan_id}
                step_results.append([])
        store_apply_state("applied")
        self._record("apply", plan_id=plan_id, status="applied", created_count=len(created_uids))
        result = {"status": "applied", "plan_id": plan_id, "created_uids": created_uids}
        if wall_seq_numbers:
            result["wall_seq_numbers"] = list(wall_seq_numbers)
        if snapshots:
            result["snapshots"] = list(snapshots)
        return result

    def verify(self, plan_id: str) -> dict[str, Any]:
        plan = self._plans.get(plan_id)
        if plan is None:
            return {"status": "rejected", "message": "unknown plan_id", "plan_id": plan_id}
        client = self.ensure_client()
        state = self._state.get(plan_id, {})
        state_status = state.get("status")
        created_uids = state.get("created_uids", [])
        created_kinds = state.get("created_kinds", ["unit"] * len(created_uids))
        still_present = []
        for uid, kind in zip(created_uids, created_kinds):
            if kind == "template":
                payload = client.read_template(uid) if hasattr(client, "read_template") else {"items": []}
                if payload.get("items"):
                    still_present.append(uid)
            elif kind == "macro":
                payload = client.read_macro(uid) if hasattr(client, "read_macro") else {"items": []}
                if payload.get("items"):
                    still_present.append(uid)
            elif kind == "layout":
                payload = client.read_layout(uid) if hasattr(client, "read_layout") else {"items": []}
                if payload.get("items"):
                    still_present.append(uid)
            else:
                payload = client.read_unit(uid)
                units = payload.get("units") or []
                if units:
                    still_present.append(uid)
        if state_status in {"applied", "rolled_back"}:
            status = "verified"
        elif state_status == "error":
            status = "error"
        else:
            status = "planned"
        result = {
            "status": status,
            "plan_id": plan_id,
            "created_uids": list(created_uids),
            "still_present": still_present,
        }
        workflow = plan.get("workflow")
        if workflow in {"update_detector_parameters", "update_detector_visual_element", "delete_detector", "archive_policy_update"}:
            target_uid = str((plan.get("expected") or {}).get("uid") or "")
            payload = client.read_unit(target_uid)
            units = payload.get("units") or []
            target_present = bool(units)
            result["target"] = {"uid": target_uid, "still_present": target_present}
            snapshots = list(state.get("snapshots", []))
            snapshot = next((snap for snap in snapshots if str(snap.get("target_uid") or "") == target_uid), None)
            if state_status == "rolled_back":
                snapshot_restored = bool(snapshot and units and _unit_matches_snapshot(units[0], snapshot))
                result["snapshot_restored"] = snapshot_restored
                result["status"] = "verified" if snapshot_restored else "error"
                return result
            if state_status == "error" and snapshot is not None:
                result["snapshot_restored"] = bool(units and _unit_matches_snapshot(units[0], snapshot))
            if workflow == "delete_detector":
                if state_status == "applied":
                    result["status"] = "verified" if not target_present else "error"
                return result
            requested_properties = []
            for step in plan.get("steps") or []:
                if step.get("operation") in {"change_detector_snapshot_unit", "change_archive_policy_snapshot_unit"}:
                    changed = (step.get("payload") or {}).get("changed") or []
                    requested_properties = list((changed[0] if changed else {}).get("properties") or [])
                    break
            actual_properties = list((units[0] if units else {}).get("properties") or [])
            property_checks = _requested_property_checks(actual_properties, requested_properties)
            result["property_checks"] = property_checks
            if state_status == "applied":
                result["status"] = "verified" if target_present and all(property_checks.values()) else "error"
            return result
        detector_checks = None
        if state_status != "rolled_back":
            detector_checks = _detector_checks_for_plan(client, plan, list(created_uids), list(created_kinds))
        if detector_checks is not None:
            result["detector_checks"] = detector_checks
            if state_status == "applied" and not all(detector_checks.values()):
                result["status"] = "error"
        return result

    def rollback(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plans.get(plan_id)
        if plan is None:
            self._record("rollback", plan_id=plan_id, status="rejected", reason="unknown_plan")
            return {"status": "rejected", "message": "unknown plan_id", "plan_id": plan_id}
        if not self.enabled:
            self._record("rollback", plan_id=plan_id, status="rejected", reason="disabled")
            return {
                "status": "rejected",
                "message": "operator mutations are disabled; start the MCP server with --enable-operator",
                "plan_id": plan_id,
            }
        if confirmation != plan.get("rollback_confirmation_token"):
            self._record("rollback", plan_id=plan_id, status="rejected", reason="bad_confirmation")
            return {
                "status": "rejected",
                "message": "rollback confirmation token does not match the plan",
                "plan_id": plan_id,
            }
        client = self.ensure_client()
        state = self._state.get(plan_id, {})
        created_uids = list(state.get("created_uids", []))
        created_kinds = list(state.get("created_kinds", ["unit"] * len(created_uids)))
        snapshots = list(state.get("snapshots", []))
        rollback_strategy = (plan.get("rollback") or {}).get("strategy")
        if rollback_strategy in {"restore_detector_snapshot", "restore_archive_policy_snapshot"}:
            restored: list[str] = []
            failed: list[dict[str, Any]] = []
            for snapshot in reversed(snapshots):
                target_uid = str(snapshot.get("target_uid") or "")
                target_present = bool((client.read_unit(target_uid).get("units") or []))
                response = client.change_config(_restore_payload_for_snapshot(snapshot, target_present=target_present))
                if response.get("failed"):
                    failed.append({"uid": target_uid, "reason": response.get("failed_reason", []) or response.get("failed", [])})
                    continue
                restored.append(target_uid)
            rollback_status = "error" if failed else "rolled_back"
            self._state[plan_id] = {
                "status": rollback_status,
                "created_uids": list(created_uids),
                "created_kinds": list(created_kinds),
                "snapshots": snapshots,
                "restored_uids": list(restored),
                "failed": list(failed),
            }
            self._record("rollback", plan_id=plan_id, status=rollback_status, restored_count=len(restored), failed_count=len(failed))
            return {
                "status": rollback_status,
                "plan_id": plan_id,
                "restored_uids": restored,
                "failed": failed,
            }
        if rollback_strategy == "archive_cancel_reindex":
            failed: list[dict[str, Any]] = []
            cancelled: list[str] = []
            if state.get("status") == "applied":
                for step in plan.get("steps") or []:
                    if step.get("operation") != "archive_reindex":
                        continue
                    response = client.archive_cancel_reindex_via_api(step["access_point"], step["volume_ids"])
                    if response.get("status") != 200:
                        failed.append({"access_point": step["access_point"], "volume_ids": step["volume_ids"]})
                        continue
                    cancelled.extend(list(step["volume_ids"]))
            rollback_status = "error" if failed else "rolled_back"
            self._state[plan_id] = {
                "status": rollback_status,
                "created_uids": list(created_uids),
                "created_kinds": list(created_kinds),
                "cancelled_volume_ids": list(cancelled),
                "failed": list(failed),
            }
            self._record("rollback", plan_id=plan_id, status=rollback_status, cancelled_count=len(cancelled), failed_count=len(failed))
            return {
                "status": rollback_status,
                "plan_id": plan_id,
                "cancelled_volume_ids": cancelled,
                "failed": failed,
            }
        wall_uids = [uid for uid, kind in zip(created_uids, created_kinds) if kind == "wall"]
        wall_cookie_by_uid = dict(zip(wall_uids, state.get("wall_cookies", [])))
        removed: list[str] = []
        failed: list[dict[str, Any]] = []
        for uid, kind in reversed(list(zip(created_uids, created_kinds))):
            if kind == "template":
                response = client.change_templates({"removed": [uid]})
            elif kind == "macro":
                response = client.change_macros({"removed_macros": [uid]})
            elif kind == "layout":
                response = client.change_layouts({"removed": [uid]})
            elif kind == "map":
                response = client.change_maps_via_api({"removed": [uid]})
            elif kind == "wall":
                cookie = wall_cookie_by_uid.get(uid, "")
                response = client.unregister_wall_via_api(cookie) if cookie else {"failed": True, "failed_reason": ["missing_cookie"]}
            else:
                response = client.change_config({"removed": [{"uid": uid}]})
            if response.get("failed"):
                failed.append({"uid": uid, "reason": response.get("failed_reason", [])})
                continue
            removed.append(uid)
        remaining_pairs = [(uid, kind) for uid, kind in zip(created_uids, created_kinds) if uid not in removed]
        self._state[plan_id] = {
            "status": "rolled_back",
            "created_uids": [p[0] for p in remaining_pairs],
            "created_kinds": [p[1] for p in remaining_pairs],
        }
        self._record("rollback", plan_id=plan_id, status="rolled_back", removed_count=len(removed))
        return {
            "status": "rolled_back",
            "plan_id": plan_id,
            "removed_uids": removed,
            "failed": failed,
        }

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._log)

    def _record(self, action: str, **fields: Any) -> None:
        entry = {"action": action, "timestamp": dt.datetime.now(dt.UTC).isoformat()}
        entry.update(fields)
        self._log.append(entry)
