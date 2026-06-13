#!/usr/bin/env python3
"""Task-first detector playbooks for Axxon One MCP.

This module is an orchestration layer only. It uses detector_archive for
read-only descriptor/catalog data and operator workflows for all mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import os as _os
from pathlib import Path
import re
from typing import Any, Callable
import uuid


APPROVAL_ENV = "AXXON_DETECTOR_PLAYBOOKS_APPROVE"
CONFIRMATION_TOKEN = "CONFIRM-detector-playbooks"
ROLLBACK_CONFIRMATION_TOKEN = "CONFIRM-detector-playbooks-rollback"
PLAN_PREFIX = "detector-playbook-plan-"
TRACKLET_LIMIT_CAP = 25
GEOMETRY_VALUE_KINDS = (
    "value_rectangle",
    "value_polyline",
    "value_mask",
    "value_simple_polygon",
)
SUPPORTED_FALLBACK_LOCAL = {
    "AVDetector": ("MotionDetection", "SceneDescription", "NeuroTracker"),
    "AppDataDetector": ("MoveInZone", "OneLineCrossing", "LongInZone", "LostObject", "AbandonedObject"),
}
FIXTURE_NEEDED_FAMILIES = [
    {
        "family": "GlobalTracker profiles",
        "status": "fixture-needed",
        "service": "GlobalTrackerService",
        "rpcs": [
            "ChangeGlobalTrackerProfiles",
            "ChangeProfiles",
            "ClearProfiles",
            "BindGlobalTrackProfile",
            "GetGlobalTrackBestVisibilityPositions",
        ],
        "required_fixtures": [
            "non-production global-tracker profile fixtures",
            "privacy-reviewed image/profile inputs",
        ],
    },
    {
        "family": "RealtimeRecognizerExternal",
        "status": "fixture-needed",
        "service": "RealtimeRecognizerExternalService",
        "rpcs": ["RealtimeRecognizerExternalService.GetData"],
        "required_fixtures": ["configured external recognizer data source"],
    },
    {
        "family": "TagAndTrack",
        "status": "fixture-needed",
        "service": "TagAndTrackService",
        "rpcs": [
            "TagAndTrackService.ListTrackers",
            "TagAndTrackService.SetMode",
            "TagAndTrackService.FollowTrack",
            "TagAndTrackService.MoveToCoords",
        ],
        "required_fixtures": ["configured Tag&Track component", "non-production PTZ fixture"],
    },
]


INTENT_SPECS: dict[str, dict[str, Any]] = {
    "create_av_detector": {
        "workflow": "create_av_detector_full",
        "required": ["display_name", "video_source_ap"],
        "optional": ["detector_kind", "properties", "schema_source"],
        "description": "Create a persistent AVDetector bound to a video source.",
    },
    "create_appdata_detector": {
        "workflow": "create_appdata_detector_full",
        "required": ["display_name", "video_source_ap"],
        "optional": ["detector_kind", "vmda_source_ap", "properties", "schema_source", "scene_display_name"],
        "description": "Create a persistent AppDataDetector, chain-creating SceneDescription VMDA when needed.",
    },
    "update_detector_parameters": {
        "workflow": "update_detector_parameters",
        "required": ["detector_uid", "properties"],
        "optional": ["descriptor", "schema_source"],
        "description": "Update descriptor-backed detector properties via snapshot-backed operator workflow.",
    },
    "update_detector_geometry": {
        "workflow": "update_detector_visual_element",
        "required": ["visual_element_uid or visual_element_path", "property_path", "value_kind", "value"],
        "optional": ["detector_uid", "unit_type", "detector_kind", "visual_elements"],
        "description": "Update descriptor-backed VisualElement geometry using typed value fields.",
    },
    "delete_detector": {
        "workflow": "delete_detector",
        "required": ["detector_uid"],
        "optional": ["parent_uid"],
        "description": "Delete a detector with snapshot-backed rollback.",
    },
    "raise_external_event": {
        "workflow": "external_event_inject",
        "required": ["access_point"],
        "optional": ["event_type"],
        "description": "Raise a one-shot external detector event.",
    },
    "raise_periodical_external_event": {
        "workflow": "raise_periodical_event",
        "required": ["access_point"],
        "optional": ["event_type", "tracklets"],
        "description": "Raise a bounded periodical target-list event without raw media/vectors.",
    },
    "preflight_vmda_appdata": {
        "required": ["video_source_ap"],
        "optional": ["vmda_source_ap", "detector_kind"],
        "description": "Read-only AppData/VMDA source preflight and SceneDescription chain guidance.",
    },
    "metadata_vmda_heatmap_guidance": {
        "required": [],
        "optional": ["access_point", "camera_id", "time_range"],
        "description": "Read-only next-tool guidance for metadata, VMDA, and heatmap workflows.",
    },
    "global_tracker_profile": {
        "required": ["fixture"],
        "optional": ["profile_id"],
        "description": "Fixture-gated GlobalTracker profile workflow guidance.",
    },
    "realtime_recognizer_external": {
        "required": ["fixture"],
        "optional": ["source"],
        "description": "Fixture-gated RealtimeRecognizerExternal guidance.",
    },
    "tag_and_track": {
        "required": ["fixture"],
        "optional": ["tracker_id", "mode", "target"],
        "description": "Fixture-gated TagAndTrack guidance.",
    },
}


_PUBLIC_TOKEN_KEYS = {"confirmationtoken", "rollbackconfirmationtoken"}
_PUBLIC_TOKENS = {CONFIRMATION_TOKEN, ROLLBACK_CONFIRMATION_TOKEN}
_SAFE_SENSITIVE_LOOKING_KEYS = {"passwordpresent", "cookiepresent", "tokenpresent", "credentialspresent"}
_SENSITIVE_KEY_TOKENS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "cookie",
    "sessionid",
    "authorization",
    "bearer",
    "certificate",
    "privatekey",
    "serial",
    "license",
    "ticket",
    "credential",
    "rawmedia",
    "mediabytes",
    "rawmetadata",
    "metadatapayload",
    "biometric",
    "embedding",
    "vector",
    "imagebytes",
    "framebytes",
)
_SENSITIVE_EXACT_KEYS = {"ca"}
_BEARER_RE = re.compile(r"\bBearer\s+[^,\s;]+", re.IGNORECASE)
_OPERATOR_PLAN_RE = re.compile(r"\boperator-plan-[A-Za-z0-9_.:-]+")
_NON_PUBLIC_CONFIRM_RE = re.compile(r"\bCONFIRM-(?!detector-playbooks(?:-rollback)?\b)[A-Za-z0-9_.:-]+")
_SECRET_ASSIGN_RE = re.compile(
    r"(?P<key>password|passwd|pwd|secret|token|cookie|ticket|license|authorization)\s*[:=]\s*[^,\s;}]+",
    re.IGNORECASE,
)


def _default_detector_archive() -> Any:
    from axxon_mcp_detector_archive import AxxonMcpDetectorArchive

    return AxxonMcpDetectorArchive()


def _default_operator() -> Any:
    from axxon_api_client import AxxonApiClient, AxxonClientConfig
    from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

    config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])
    return OperatorRegistry(
        client_factory=lambda: AxxonOperatorClient(AxxonApiClient(config)),
        host=f"hosts/{config.tls_cn}",
        enabled=True,
    )


def _normalized_key(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def _sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    if normalized in _SAFE_SENSITIVE_LOOKING_KEYS:
        return False
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def _redact_text(value: str) -> str:
    text = _BEARER_RE.sub("Bearer <redacted>", value)
    text = _OPERATOR_PLAN_RE.sub("<redacted-operator-plan>", text)
    text = _NON_PUBLIC_CONFIRM_RE.sub("<redacted-confirmation>", text)
    text = _SECRET_ASSIGN_RE.sub(lambda m: f"{m.group('key')}=<redacted>", text)
    if "SHOULD_NOT_LEAK" in text:
        return "<redacted>"
    return text


def sanitize_public(value: Any, key: Any = "") -> Any:
    normalized = _normalized_key(key)
    if normalized in _PUBLIC_TOKEN_KEYS and isinstance(value, str) and value in _PUBLIC_TOKENS:
        return value
    if _sensitive_key(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {item_key: sanitize_public(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_public(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_public(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _remove_operator_internals(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in {"planid", "confirmationtoken", "rollbackconfirmationtoken"}:
                continue
            out[key] = _remove_operator_internals(item)
        return out
    if isinstance(value, list):
        return [_remove_operator_internals(item) for item in value]
    return value


def _sort_shape_fields(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    return value


def _normalized_visual_elements(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        copied["shape_fields"] = _sort_shape_fields(copied.get("shape_fields", []))
        props = []
        for prop in copied.get("properties") or []:
            if isinstance(prop, dict):
                props.append(dict(prop))
        copied["properties"] = props
        out.append(copied)
    return sanitize_public(out)


def _intent_params(intent: str) -> tuple[list[str], list[str]]:
    spec = INTENT_SPECS.get(intent, {})
    required = list(spec.get("required", []))
    optional = list(spec.get("optional", []))
    return required, optional


def _value_from_params(params: dict[str, Any], value_kind: str) -> Any:
    if "value" in params:
        return params["value"]
    return params.get(value_kind)


def _property_id(value: dict[str, Any]) -> str:
    for field_name in ("id", "property_id", "propertyId", "path", "name"):
        item = value.get(field_name)
        if isinstance(item, str) and item:
            return item.split(".")[-1].split("/")[-1]
    return ""


def _property_path(value: dict[str, Any]) -> str:
    for field_name in ("path", "id", "property_id", "propertyId", "name"):
        item = value.get(field_name)
        if isinstance(item, str) and item:
            return item
    return ""


def _visual_matches(visual: dict[str, Any], uid: str, path: str) -> bool:
    if uid and uid in {str(visual.get("uid") or ""), str(visual.get("id") or "")}:
        return True
    if path and path in {str(visual.get("path") or ""), str(visual.get("name") or "")}:
        return True
    return False


def _property_matches(prop: dict[str, Any], path: str) -> bool:
    return path in {_property_path(prop), _property_id(prop), str(prop.get("name") or "")}


def _sanitize_tracklet(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_tracklet(item)
            for key, item in value.items()
            if not _sensitive_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_tracklet(item) for item in value]
    return value


def _rollback_classification(operator_plan: dict[str, Any]) -> str:
    strategy = str((operator_plan.get("rollback") or {}).get("strategy") or "")
    if strategy == "noop":
        return "noop"
    if strategy:
        return "rollbackable"
    return "unknown"


def _operator_status(value: str) -> str:
    if value in {"planned", "applied", "verified", "rolled_back", "error", "rejected"}:
        return value
    if value == "fixture-needed":
        return value
    return value or "unknown"


@dataclass
class AxxonMcpDetectorPlaybooks:
    detector_archive: Any | None = None
    operator: Any | None = None
    environ: dict[str, str] | None = None
    detector_archive_factory: Callable[[], Any] = _default_detector_archive
    operator_factory: Callable[[], Any] = _default_operator
    _plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    _audit: list[dict[str, Any]] = field(default_factory=list)

    def _archive(self) -> Any:
        if self.detector_archive is None:
            self.detector_archive = self.detector_archive_factory()
        return self.detector_archive

    def _operator(self) -> Any:
        if self.operator is None:
            self.operator = self.operator_factory()
        return self.operator

    def _env(self) -> dict[str, str]:
        return _os.environ if self.environ is None else self.environ

    def _gate(self) -> dict[str, Any]:
        return {
            "approval_env": APPROVAL_ENV,
            "confirmation_token": CONFIRMATION_TOKEN,
            "rollback_confirmation_token": ROLLBACK_CONFIRMATION_TOKEN,
        }

    def _record(
        self,
        action: str,
        *,
        plan_id: str = "",
        intent: str = "",
        status: str = "",
        reason: str = "",
    ) -> None:
        entry = {
            "seq": len(self._audit) + 1,
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "action": action,
            "plan_id": plan_id,
            "intent": intent,
            "status": status,
            "reason": reason,
        }
        self._audit.append(sanitize_public(entry))

    def detector_playbooks_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            result = {
                "connected": False,
                "status": "gap",
                "profile_name": profile,
                "message": "Only the env profile is supported for detector playbooks.",
                "mode": "detector-playbooks",
                **self._gate(),
            }
            return sanitize_public(result)
        connected = self._archive().detector_archive_connect_axxon_profile("env")
        result = {
            "connected": bool(connected.get("connected", False)),
            "status": connected.get("status", "ok" if connected.get("connected", False) else "gap"),
            "profile_name": connected.get("profile_name", profile),
            "profile": connected.get("profile", {}),
            "mode": "detector-playbooks",
            **self._gate(),
        }
        return sanitize_public(result)

    def list_detector_playbooks(self, include_live: bool = True) -> dict[str, Any]:
        result = {
            "status": "ok",
            "tool": "list_detector_playbooks",
            "include_live": bool(include_live),
            "intents": {
                name: {
                    "required": list(spec.get("required", [])),
                    "optional": list(spec.get("optional", [])),
                    "operator_workflow": spec.get("workflow", ""),
                    "description": spec.get("description", ""),
                }
                for name, spec in INTENT_SPECS.items()
            },
            "geometry_value_kind_policy": {
                "descriptor_backed_only": True,
                "accepted_value_kinds": list(GEOMETRY_VALUE_KINDS),
                "notes": [
                    "Geometry updates use VisualElement descriptors and the exact value_* field declared by the descriptor.",
                    "Unknown or mismatched value kinds are rejected before an operator plan is created.",
                ],
            },
            "gate": self._gate(),
            "detector_family_matrix": self._detector_family_matrix(include_live=include_live),
        }
        return sanitize_public(result)

    def detector_playbook_parameter_schema(
        self,
        unit_type: str,
        detector_kind: str,
        intent: str = "",
    ) -> dict[str, Any]:
        base = self._archive().detector_parameter_schema(unit_type, detector_kind)
        required, optional = _intent_params(intent)
        visual_elements = _normalized_visual_elements(base.get("visual_elements"))
        result = {
            "status": base.get("status", "ok"),
            "tool": "detector_playbook_parameter_schema",
            "unit_type": unit_type,
            "detector_kind": detector_kind,
            "intent": intent,
            "playbook_required_params": required,
            "playbook_optional_params": optional,
            "base_schema": base,
            "schema": base.get("schema", {}),
            "visual_elements": visual_elements,
            "geometry_value_kinds": list(GEOMETRY_VALUE_KINDS),
            "detector_family_matrix": self._detector_family_matrix(include_live=False),
        }
        return sanitize_public(result)

    def plan_detector_playbook(self, intent: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        if intent not in INTENT_SPECS:
            result = {
                "status": "gap",
                "intent": intent,
                "message": f"Unknown detector playbook intent: {intent}",
                "known_intents": sorted(INTENT_SPECS),
            }
            self._record("plan", intent=intent, status="gap", reason="unknown_intent")
            return sanitize_public(result)

        if intent in {"preflight_vmda_appdata", "metadata_vmda_heatmap_guidance"}:
            return self._plan_guidance(intent, params)
        if intent in {"global_tracker_profile", "realtime_recognizer_external", "tag_and_track"}:
            return self._plan_fixture_needed(intent)
        if intent == "update_detector_geometry":
            return self._plan_update_detector_geometry(params)
        return self._plan_operator_backed(intent, params)

    def apply_detector_playbook_plan(self, playbook_plan_id: str, confirmation: str) -> dict[str, Any]:
        record = self._plans.get(playbook_plan_id)
        if record is None:
            self._record("apply", plan_id=playbook_plan_id, status="rejected", reason="unknown_plan")
            return sanitize_public({"status": "rejected", "message": "unknown playbook_plan_id", "playbook_plan_id": playbook_plan_id})
        if not record.get("apply_ready"):
            self._record("apply", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="not_apply_ready")
            return {
                "status": "rejected",
                "message": "detector playbook plan is not apply-ready",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            }
        if self._env().get(APPROVAL_ENV) != "1":
            self._record("apply", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="env_gate")
            return {
                "status": "rejected",
                "message": f"detector playbooks require {APPROVAL_ENV}=1 at apply time",
                "playbook_plan_id": playbook_plan_id,
            }
        if confirmation != CONFIRMATION_TOKEN:
            self._record("apply", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="bad_confirmation")
            return {
                "status": "rejected",
                "message": "confirmation token does not match detector playbooks gate",
                "playbook_plan_id": playbook_plan_id,
            }
        if record.get("state") in {"applied", "verified"}:
            return sanitize_public({
                "status": "applied",
                "message": "detector playbook plan was already applied",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            })
        if record.get("state") == "rolled_back":
            return sanitize_public({
                "status": "rejected",
                "message": "rolled-back detector playbook plans cannot be reapplied",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            })
        result = self._operator().apply(record["operator_plan_id"], record["operator_confirmation_token"])
        status = _operator_status(str(result.get("status") or "unknown"))
        record["state"] = status
        self._record("apply", plan_id=playbook_plan_id, intent=record["intent"], status=status)
        public = {
            "status": status,
            "playbook_plan_id": playbook_plan_id,
            "intent": record["intent"],
            "operator_workflow": record["operator_workflow"],
            "rollback_classification": record.get("rollback_classification"),
            "result": _remove_operator_internals(result),
        }
        return sanitize_public(public)

    def verify_detector_playbook_plan(self, playbook_plan_id: str) -> dict[str, Any]:
        record = self._plans.get(playbook_plan_id)
        if record is None:
            return sanitize_public({"status": "rejected", "message": "unknown playbook_plan_id", "playbook_plan_id": playbook_plan_id})
        if not record.get("apply_ready"):
            return sanitize_public({
                "status": record.get("state", "fixture-needed"),
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
                "apply_ready": False,
                "message": record.get("message", "detector playbook plan is not apply-ready"),
            })
        result = self._operator().verify(record["operator_plan_id"])
        status = _operator_status(str(result.get("status") or "unknown"))
        if status == "verified":
            record["state"] = "verified"
        self._record("verify", plan_id=playbook_plan_id, intent=record["intent"], status=status)
        public = {
            "status": status,
            "playbook_plan_id": playbook_plan_id,
            "intent": record["intent"],
            "operator_workflow": record["operator_workflow"],
            "result": _remove_operator_internals(result),
        }
        return sanitize_public(public)

    def rollback_detector_playbook_plan(self, playbook_plan_id: str, confirmation: str) -> dict[str, Any]:
        record = self._plans.get(playbook_plan_id)
        if record is None:
            self._record("rollback", plan_id=playbook_plan_id, status="rejected", reason="unknown_plan")
            return sanitize_public({"status": "rejected", "message": "unknown playbook_plan_id", "playbook_plan_id": playbook_plan_id})
        if not record.get("apply_ready"):
            self._record("rollback", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="not_apply_ready")
            return {
                "status": "rejected",
                "message": "detector playbook plan is not apply-ready",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            }
        if self._env().get(APPROVAL_ENV) != "1":
            self._record("rollback", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="env_gate")
            return {
                "status": "rejected",
                "message": f"detector playbooks require {APPROVAL_ENV}=1 at rollback time",
                "playbook_plan_id": playbook_plan_id,
            }
        if confirmation != ROLLBACK_CONFIRMATION_TOKEN:
            self._record("rollback", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="bad_confirmation")
            return {
                "status": "rejected",
                "message": "rollback confirmation token does not match detector playbooks gate",
                "playbook_plan_id": playbook_plan_id,
            }
        if record.get("state") == "rolled_back":
            return sanitize_public({
                "status": "rolled_back",
                "message": "detector playbook plan was already rolled back",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            })
        if record.get("state") not in {"applied", "verified"}:
            self._record("rollback", plan_id=playbook_plan_id, intent=record["intent"], status="rejected", reason="not_applied")
            return {
                "status": "rejected",
                "message": "detector playbook plan has not been applied",
                "playbook_plan_id": playbook_plan_id,
                "intent": record["intent"],
            }
        result = self._operator().rollback(record["operator_plan_id"], record["operator_rollback_confirmation_token"])
        status = _operator_status(str(result.get("status") or "unknown"))
        record["state"] = status
        self._record("rollback", plan_id=playbook_plan_id, intent=record["intent"], status=status)
        public = {
            "status": status,
            "playbook_plan_id": playbook_plan_id,
            "intent": record["intent"],
            "operator_workflow": record["operator_workflow"],
            "rollback_classification": record.get("rollback_classification"),
            "result": _remove_operator_internals(result),
        }
        return sanitize_public(public)

    def detector_playbooks_audit_log(self) -> dict[str, Any]:
        return {"status": "ok", "entries": [sanitize_public(entry) for entry in self._audit]}

    def _detector_family_matrix(self, *, include_live: bool) -> dict[str, Any]:
        by_unit_type: dict[str, list[dict[str, Any]]] = {}
        try:
            catalog = self._archive().detector_kind_catalog(include_live=include_live)
            raw = catalog.get("by_unit_type", {})
            if isinstance(raw, dict):
                by_unit_type = {
                    unit_type: [entry for entry in entries if isinstance(entry, dict)]
                    for unit_type, entries in raw.items()
                    if isinstance(entries, list)
                }
        except Exception:
            by_unit_type = {}

        discovered = {
            "live_unit_discovered": {"AVDetector": [], "AppDataDetector": []},
            "template_discovered": {"AVDetector": [], "AppDataDetector": []},
            "factory_discovered": {"AVDetector": [], "AppDataDetector": []},
        }
        provenance_to_bucket = {
            "live-unit": "live_unit_discovered",
            "template": "template_discovered",
            "factory": "factory_discovered",
        }
        for unit_type in ("AVDetector", "AppDataDetector"):
            for entry in by_unit_type.get(unit_type, []):
                provenance = entry.get("provenance") or []
                if isinstance(provenance, str):
                    provenance = [provenance]
                for source, bucket in provenance_to_bucket.items():
                    if source in provenance:
                        discovered[bucket][unit_type].append(sanitize_public(entry))

        return {
            "supported_fallback_local": {
                unit_type: list(kinds)
                for unit_type, kinds in SUPPORTED_FALLBACK_LOCAL.items()
            },
            **discovered,
            "fixture_needed": [dict(item) for item in FIXTURE_NEEDED_FAMILIES],
            "notes": [
                "Fallback/local catalog entries are supported as offline playbook templates, not claimed live on a stand.",
                "Live/template/factory buckets preserve detector_archive provenance when include_live is true.",
            ],
        }

    def _new_plan_id(self) -> str:
        return f"{PLAN_PREFIX}{uuid.uuid4()}"

    def _store_non_apply_ready(
        self,
        *,
        intent: str,
        status: str,
        body: dict[str, Any],
        message: str = "",
    ) -> dict[str, Any]:
        plan_id = self._new_plan_id()
        response = {
            "status": status,
            "playbook_plan_id": plan_id,
            "intent": intent,
            "apply_ready": False,
            "confirmation_token": CONFIRMATION_TOKEN,
            "rollback_confirmation_token": ROLLBACK_CONFIRMATION_TOKEN,
            **body,
        }
        self._plans[plan_id] = {
            "intent": intent,
            "apply_ready": False,
            "state": status,
            "message": message or body.get("message", ""),
            "public_plan": sanitize_public(response),
        }
        self._record("plan", plan_id=plan_id, intent=intent, status=status)
        return sanitize_public(response)

    def _plan_fixture_needed(self, intent: str) -> dict[str, Any]:
        family_by_intent = {
            "global_tracker_profile": FIXTURE_NEEDED_FAMILIES[0],
            "realtime_recognizer_external": FIXTURE_NEEDED_FAMILIES[1],
            "tag_and_track": FIXTURE_NEEDED_FAMILIES[2],
        }
        family = dict(family_by_intent[intent])
        return self._store_non_apply_ready(
            intent=intent,
            status="fixture-needed",
            body={
                "message": f"{intent} requires fixture-backed implementation before mutation is apply-ready.",
                "fixture_needed": family,
                "read_only_prerequisites": ["global_tracker.get_profile"] if intent == "global_tracker_profile" else [],
            },
            message="fixture-needed",
        )

    def _plan_guidance(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        if intent == "preflight_vmda_appdata":
            detector_kind = str(params.get("detector_kind") or params.get("detector") or "MoveInZone")
            body = {
                "guidance": {
                    "video_source_ap": str(params.get("video_source_ap") or ""),
                    "vmda_source_ap": str(params.get("vmda_source_ap") or ""),
                    "vmda_source_optional": True,
                    "scene_description_chain_creation": {
                        "when": "vmda_source_ap is omitted",
                        "operator_workflow": "create_appdata_detector_full",
                        "chain": "create SceneDescription AVDetector, then bind AppDataDetector to its SourceEndpoint.vmda",
                    },
                    "detector_kind": detector_kind,
                    "support": self._kind_support("AppDataDetector", detector_kind),
                },
                "detector_family_matrix": self._detector_family_matrix(include_live=True),
            }
            return self._store_non_apply_ready(intent=intent, status="guidance", body=body, message="read-only guidance")

        body = {
            "next_tools": [
                {
                    "tool": "metadata_schema_catalog",
                    "purpose": "Inspect metadata message shapes and vmda/metadata endpoint examples.",
                },
                {
                    "tool": "metadata_sample_bounded",
                    "purpose": "Pull capped metadata samples by vmda/metadata SourceEndpoint.",
                    "caps": {"timeout_s_max": 30.0, "limit_max": 200},
                },
                {
                    "tool": "vmda_query",
                    "purpose": "Run typed VMDA archive queries against camera detector endpoints.",
                    "endpoint_type": "*/SourceEndpoint.vmda plus VMDA database when required",
                },
                {
                    "tool": "build_heatmap / execute_heatmap_query",
                    "purpose": "Build/query heatmaps from VMDA metadata using bounded time/count settings.",
                    "caps": {"image_width_default": 320, "max_responses_default": 8},
                },
            ],
            "safety": [
                "Do not return raw metadata frames, raw media bytes, biometric vectors, credentials, or copied proto text.",
                "Use bounded count/time parameters for samples and heatmap queries.",
            ],
        }
        return self._store_non_apply_ready(intent=intent, status="guidance", body=body, message="read-only guidance")

    def _kind_support(self, unit_type: str, detector_kind: str) -> dict[str, Any]:
        matrix = self._detector_family_matrix(include_live=True)
        if detector_kind in matrix["supported_fallback_local"].get(unit_type, []):
            return {"status": "supported_fallback_local", "unit_type": unit_type, "detector_kind": detector_kind}
        for bucket in ("live_unit_discovered", "template_discovered", "factory_discovered"):
            for entry in matrix[bucket].get(unit_type, []):
                if entry.get("detector_kind") == detector_kind:
                    return {"status": bucket, **entry}
        return {"status": "fixture-needed", "unit_type": unit_type, "detector_kind": detector_kind}

    def _plan_operator_backed(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        spec = INTENT_SPECS[intent]
        workflow = str(spec["workflow"])
        operator_params = self._operator_params(intent, params)
        if isinstance(operator_params, dict) and operator_params.get("status") in {"error", "gap"}:
            self._record("plan", intent=intent, status=operator_params["status"], reason=operator_params.get("reason", ""))
            return sanitize_public(operator_params)
        return self._plan_operator_workflow(intent, workflow, operator_params)

    def _operator_params(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        out = dict(params)
        if intent in {"create_av_detector", "create_appdata_detector"}:
            if "detector_kind" in out and "detector" not in out:
                out["detector"] = out.pop("detector_kind")
        if intent in {"update_detector_parameters", "delete_detector"}:
            if "detector_uid" in out and "uid" not in out:
                out["uid"] = out["detector_uid"]
        if intent == "raise_external_event":
            out.pop("data", None)
            out.pop("raw_metadata", None)
            out.pop("raw_media", None)
        if intent == "raise_periodical_external_event":
            tracklets = list(out.get("tracklets") or [])
            if len(tracklets) > TRACKLET_LIMIT_CAP:
                return {
                    "status": "error",
                    "intent": intent,
                    "message": f"tracklets is capped at {TRACKLET_LIMIT_CAP}",
                    "reason": "tracklet_limit",
                }
            if tracklets:
                out["tracklets"] = [_sanitize_tracklet(item) for item in tracklets]
        return out

    def _plan_update_detector_geometry(self, params: dict[str, Any]) -> dict[str, Any]:
        visual_elements = self._visual_elements_for_geometry(params)
        visual_uid = str(params.get("visual_element_uid") or params.get("uid") or "").strip()
        visual_path = str(params.get("visual_element_path") or params.get("visual_element") or "").strip()
        property_path = str(params.get("property_path") or params.get("path") or params.get("property") or "").strip()
        value_kind = str(params.get("value_kind") or "").strip()
        if not (visual_uid or visual_path) or not property_path or not value_kind:
            return sanitize_public({
                "status": "gap",
                "intent": "update_detector_geometry",
                "message": "update_detector_geometry requires visual_element_uid or visual_element_path, property_path, and value_kind",
            })
        if value_kind not in GEOMETRY_VALUE_KINDS:
            return sanitize_public({
                "status": "error",
                "intent": "update_detector_geometry",
                "message": f"Unknown geometry value_kind {value_kind!r}",
            })

        visual = next((item for item in visual_elements if _visual_matches(item, visual_uid, visual_path)), None)
        if visual is None:
            return sanitize_public({
                "status": "gap",
                "intent": "update_detector_geometry",
                "message": "Could not resolve descriptor-backed visual element.",
            })
        prop = next((item for item in visual.get("properties", []) if isinstance(item, dict) and _property_matches(item, property_path)), None)
        if prop is None:
            return sanitize_public({
                "status": "gap",
                "intent": "update_detector_geometry",
                "message": f"Could not resolve descriptor-backed property {property_path!r}.",
            })
        descriptor_value_kind = str(prop.get("value_kind") or "")
        if descriptor_value_kind != value_kind:
            return sanitize_public({
                "status": "error",
                "intent": "update_detector_geometry",
                "message": f"value_kind mismatch: descriptor declares {descriptor_value_kind!r}, request used {value_kind!r}",
            })
        value = _value_from_params(params, value_kind)
        if value is None:
            return sanitize_public({
                "status": "gap",
                "intent": "update_detector_geometry",
                "message": "update_detector_geometry requires a typed geometry value.",
            })
        target_uid = str(visual.get("uid") or visual_uid).strip()
        if not target_uid:
            return sanitize_public({
                "status": "gap",
                "intent": "update_detector_geometry",
                "message": "Resolved visual element did not provide a uid for operator update.",
            })
        property_node = {"id": _property_id(prop), value_kind: value}
        operator_params = {
            "visual_element_uid": target_uid,
            "properties": [property_node],
        }
        response = self._plan_operator_workflow(
            "update_detector_geometry",
            "update_detector_visual_element",
            operator_params,
            extra_public={
                "typed_geometry": {
                    "visual_element_uid": target_uid,
                    "property_path": property_path,
                    "property_id": _property_id(prop),
                    "value_kind": value_kind,
                }
            },
        )
        return response

    def _visual_elements_for_geometry(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(params.get("visual_elements"), list):
            return [item for item in params["visual_elements"] if isinstance(item, dict)]
        detector_uid = str(params.get("detector_uid") or "").strip()
        if detector_uid:
            result = self._archive().detector_visual_elements(detector_uid)
            return [item for item in result.get("visual_elements", []) if isinstance(item, dict)]
        unit_type = str(params.get("unit_type") or "").strip()
        detector_kind = str(params.get("detector_kind") or params.get("detector") or "").strip()
        if unit_type and detector_kind:
            result = self._archive().detector_parameter_schema(unit_type, detector_kind)
            return [item for item in result.get("visual_elements", []) if isinstance(item, dict)]
        return []

    def _plan_operator_workflow(
        self,
        intent: str,
        workflow: str,
        operator_params: dict[str, Any],
        *,
        extra_public: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operator_plan = self._operator().plan(workflow, operator_params)
        if operator_plan.get("status") in {"gap", "error", "rejected"}:
            status = str(operator_plan.get("status"))
            self._record("plan", intent=intent, status=status, reason=str(operator_plan.get("message") or "operator_gap"))
            return sanitize_public({"intent": intent, "operator_workflow": workflow, **_remove_operator_internals(operator_plan)})
        plan_id = self._new_plan_id()
        public = {
            "status": "planned",
            "playbook_plan_id": plan_id,
            "intent": intent,
            "operator_workflow": workflow,
            "apply_ready": True,
            "task_summary": {
                "intent": intent,
                "operator_workflow": workflow,
                "expected": operator_plan.get("expected", {}),
            },
            "source_bindings": operator_plan.get("source_bindings", {}),
            "steps": _remove_operator_internals(operator_plan.get("steps", [])),
            "diff": _remove_operator_internals(operator_plan.get("diff", {})),
            "rollback": operator_plan.get("rollback", {}),
            "rollback_classification": _rollback_classification(operator_plan),
            "confirmation_token": CONFIRMATION_TOKEN,
            "rollback_confirmation_token": ROLLBACK_CONFIRMATION_TOKEN,
            "gate": self._gate(),
            "detector_family_matrix": self._detector_family_matrix(include_live=False),
            **(extra_public or {}),
        }
        self._plans[plan_id] = {
            "intent": intent,
            "operator_workflow": workflow,
            "operator_plan_id": operator_plan.get("plan_id"),
            "operator_confirmation_token": operator_plan.get("confirmation_token"),
            "operator_rollback_confirmation_token": operator_plan.get("rollback_confirmation_token"),
            "apply_ready": True,
            "state": "planned",
            "rollback_classification": public["rollback_classification"],
            "public_plan": sanitize_public(public),
        }
        self._record("plan", plan_id=plan_id, intent=intent, status="planned")
        return sanitize_public(public)
