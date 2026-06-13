#!/usr/bin/env python3
"""Bulk camera onboarding planner/orchestrator for Axxon One MCP.

The module is intentionally offline-testable: validation and planning consume injectable
DevicesCatalog/DiscoveryService/site-graph-compatible providers, while apply/rollback use an
injectable ChangeConfig-compatible mutation client. Live providers are built only after the env
profile is explicitly selected or a live-backed method needs them.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, MutableMapping


BULK_ONBOARDING_APPROVE_ENV = "AXXON_BULK_ONBOARDING_APPROVE"
BULK_ONBOARDING_CONFIRMATION = "CONFIRM-bulk-onboarding"
BULK_ONBOARDING_ROLLBACK_CONFIRMATION = f"{BULK_ONBOARDING_CONFIRMATION}-rollback"
BULK_ONBOARDING_TOOL_NAMES = (
    "bulk_onboarding_connect_axxon_profile",
    "bulk_onboarding_schema",
    "bulk_onboarding_validate_manifest",
    "bulk_onboarding_plan",
    "bulk_onboarding_apply_plan",
    "bulk_onboarding_verify_plan",
    "bulk_onboarding_rollback_plan",
    "bulk_onboarding_audit_log",
)

DEFAULT_HOST_UID = "hosts/Server"
INPUT_SOURCES = ("rows", "csv_text", "json_text")
PATH_LIKE_IMPORT_FIELDS = ("path", "file", "filename", "manifest_path")
REQUIRED_FIELDS = ("display_name", "vendor", "model")
OPTIONAL_FIELDS = (
    "display_id",
    "host_uid",
    "ip",
    "ip_address",
    "mac",
    "mac_address",
    "username",
    "login",
    "password",
    "archive_uid",
    "archive_access_point",
    "template_id",
    "template_name",
    "detector_profile",
    "detector_sensitivity",
)
DESTRUCTIVE_ARCHIVE_OPERATIONS = {
    "archive_create",
    "create",
    "clear",
    "format",
    "reindex",
    "resize",
    "delete",
    "backup",
    "restore",
}

SUPPORTED_DETECTOR_PROFILES: dict[str, dict[str, Any]] = {
    "av_motion": {
        "workflow": "create_av_detector_full",
        "unit_type": "AVDetector",
        "detector": "MotionDetection",
        "description": "Create an AVDetector motion profile bound to the planned camera video source.",
    },
    "appdata_move_in_zone": {
        "workflow": "create_appdata_detector_full",
        "unit_type": "AppDataDetector",
        "detector": "MoveInZone",
        "description": "Create a SceneDescription-backed AppDataDetector MoveInZone profile.",
    },
}

SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "cookie",
    "authorization",
    "bearer",
    "session_id",
    "otp",
    "tfa",
    "private_key",
    "license_key",
    "default_credentials",
    "raw_media",
    "ca_contents",
    "ca_pem",
    "secret",
)
PUBLIC_CONFIRMATION_KEYS = {
    "confirmation_token",
    "rollback_confirmation_token",
    "confirmation_tokens",
}
SECRET_PROPERTY_IDS = {"password", "passwd", "authorization", "bearer", "token", "cookie", "session_id"}
MAC_RE = re.compile(r"^[0-9a-fA-F]{2}([:-]?[0-9a-fA-F]{2}){5}$")


@dataclass
class BulkOnboardingDependencies:
    """Injectable providers used by the planner and orchestrator."""

    catalog_provider: Any | None = None
    discovery_provider: Any | None = None
    site_graph_provider: Any | None = None
    mutation_client_factory: Callable[[], Any] | None = None


def default_config_factory() -> Any:
    from axxon_api_client import AxxonClientConfig

    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_live_dependencies_factory(config: Any) -> BulkOnboardingDependencies:
    from axxon_mcp_devices_catalog import AxxonMcpDevicesCatalog
    from axxon_mcp_discovery import AxxonMcpDiscovery
    from axxon_mcp_site_graph import AxxonMcpSiteGraph

    def _config() -> Any:
        return config

    def _mutation_client() -> Any:
        from axxon_api_client import AxxonApiClient
        from axxon_mcp_operator import AxxonOperatorClient

        return AxxonOperatorClient(AxxonApiClient(config))

    return BulkOnboardingDependencies(
        catalog_provider=AxxonMcpDevicesCatalog(config_factory=_config),
        discovery_provider=AxxonMcpDiscovery(config_factory=_config),
        site_graph_provider=AxxonMcpSiteGraph(config_factory=_config),
        mutation_client_factory=_mutation_client,
    )


def _public_config_summary(config: Any) -> dict[str, Any]:
    try:
        from axxon_mcp_admin import public_config_summary

        return public_config_summary(config)
    except Exception:
        return {
            "host": getattr(config, "host", None),
            "port": getattr(config, "port", None),
            "tls_cn": getattr(config, "tls_cn", None),
            "user": getattr(config, "user", None),
            "timeout": getattr(config, "timeout", None),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: Any) -> str:
    return _clean_str(value).lower()


def _is_secret_key(key: Any) -> bool:
    key_l = str(key).lower()
    if key_l in PUBLIC_CONFIRMATION_KEYS:
        return False
    if key_l.endswith("token") and key_l not in PUBLIC_CONFIRMATION_KEYS:
        return True
    return any(part in key_l for part in SECRET_KEY_PARTS)


def _looks_like_secret_string(value: str) -> bool:
    value_l = value.strip().lower()
    return value_l.startswith("bearer ") or value_l.startswith("basic ")


def redact(value: Any) -> Any:
    """Recursively redact secret-like keys, values, and ChangeConfig property values."""

    if isinstance(value, dict):
        prop_id = _lower(value.get("id") or value.get("name") or value.get("key"))
        property_is_secret = prop_id in SECRET_PROPERTY_IDS
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _is_secret_key(key_s):
                redacted[key] = "<redacted>"
            elif property_is_secret and (key_s.startswith("value") or key_s == "properties"):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str) and _looks_like_secret_string(value):
        return "<redacted>"
    return value


def _prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    prop: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        prop["properties"] = properties
    return prop


def _prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": bool(value)}


def _canonical_mac(value: str) -> str:
    raw = _clean_str(value)
    if not raw:
        return ""
    compact = re.sub(r"[^0-9a-fA-F]", "", raw).lower()
    if len(compact) != 12:
        return raw.lower()
    return ":".join(compact[idx : idx + 2] for idx in range(0, 12, 2))


def _valid_mac(value: str) -> bool:
    if not value:
        return True
    return bool(MAC_RE.match(value))


def _valid_ip(value: str) -> bool:
    if not value:
        return True
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _stable_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "camera"


def _status_from(errors: list[Any], warnings: list[Any]) -> str:
    if errors:
        return "error"
    if warnings:
        return "warn"
    return "ok"


def _json_fingerprint(payload: Any) -> str:
    encoded = json.dumps(redact(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _call_provider(provider: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(provider, method_name)
    try:
        return method(*args, **kwargs)
    except TypeError:
        return method()


def _value_set(*values: Any) -> set[str]:
    return {_clean_str(value) for value in values if _clean_str(value)}


@dataclass
class AxxonMcpBulkOnboarding:
    """Stateful bulk onboarding planner with gated apply/verify/rollback."""

    dependencies: BulkOnboardingDependencies | None = None
    config_factory: Callable[[], Any] = default_config_factory
    live_dependencies_factory: Callable[[Any], BulkOnboardingDependencies] = default_live_dependencies_factory
    environ: MutableMapping[str, str] | None = None
    profile_name: str | None = None
    _plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    _state: dict[str, dict[str, Any]] = field(default_factory=dict)
    _audit: list[dict[str, Any]] = field(default_factory=list)
    _sequence: int = 0
    _mutation_client: Any | None = None

    def bulk_onboarding_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            response = {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
                "profile_name": profile,
                "approval_env": BULK_ONBOARDING_APPROVE_ENV,
                "confirmation_token": BULK_ONBOARDING_CONFIRMATION,
                "rollback_confirmation_token": BULK_ONBOARDING_ROLLBACK_CONFIRMATION,
            }
            self._record("connect", status="gap", profile_name=profile)
            return response

        config = self.config_factory()
        self.dependencies = self.live_dependencies_factory(config)
        self.profile_name = profile
        response = {
            "connected": True,
            "status": "ok",
            "profile_name": profile,
            "profile": _public_config_summary(config),
            "mode": "bulk-onboarding",
            "approval_env": BULK_ONBOARDING_APPROVE_ENV,
            "confirmation_token": BULK_ONBOARDING_CONFIRMATION,
            "rollback_confirmation_token": BULK_ONBOARDING_ROLLBACK_CONFIRMATION,
            "approval_required": True,
        }
        self._record("connect", status="ok", profile_name=profile)
        return redact(response)

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.bulk_onboarding_connect_axxon_profile(profile)

    def bulk_onboarding_schema(self) -> dict[str, Any]:
        response = {
            "status": "ok",
            "tool": "bulk_onboarding_schema",
            "input_sources": list(INPUT_SOURCES),
            "required_fields": list(REQUIRED_FIELDS),
            "identity_requirement": "display_name plus vendor/model and at least one of ip, ip_address, mac, mac_address",
            "optional_fields": list(OPTIONAL_FIELDS),
            "supported_detector_profiles": {
                key: {
                    "workflow": value["workflow"],
                    "unit_type": value["unit_type"],
                    "detector": value["detector"],
                    "description": value["description"],
                }
                for key, value in SUPPORTED_DETECTOR_PROFILES.items()
            },
            "archive_policy": {
                "allowed": ["existing archive assignment", "descriptor-backed policy update"],
                "rejected_destructive_operations": sorted(DESTRUCTIVE_ARCHIVE_OPERATIONS),
            },
            "template_policy": "ConfigurationService/ChangeTemplates-compatible template references only.",
            "disallowed_import_fields": list(PATH_LIKE_IMPORT_FIELDS),
            "approval_env": BULK_ONBOARDING_APPROVE_ENV,
            "confirmation_token": BULK_ONBOARDING_CONFIRMATION,
            "rollback_confirmation_token": BULK_ONBOARDING_ROLLBACK_CONFIRMATION,
            "redaction_policy": [
                "Redact passwords, authorization values, bearer tokens, cookies, session ids, OTP/TFA secrets.",
                "Redact private keys, CA contents, license keys, raw media bytes, and default device credentials.",
                "Intrinsic Axxon object identifiers such as hosts/Server/... may be returned.",
            ],
        }
        self._record("schema", status="ok")
        return response

    def bulk_onboarding_validate_manifest(
        self,
        rows: list[dict[str, Any]] | None = None,
        csv_text: str = "",
        json_text: str = "",
        options: dict[str, Any] | None = None,
        path: str = "",
        file: str = "",
        filename: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        result = self._validate_manifest(
            rows=rows,
            csv_text=csv_text,
            json_text=json_text,
            options=options or {},
            path=path,
            file=file,
            filename=filename,
            manifest_path=manifest_path,
        )
        self._record(
            "validate",
            status=result["status"],
            row_count=result["summary"]["total_rows"],
            error_rows=result["summary"]["error_rows"],
        )
        return redact(result)

    def bulk_onboarding_plan(
        self,
        rows: list[dict[str, Any]] | None = None,
        csv_text: str = "",
        json_text: str = "",
        options: dict[str, Any] | None = None,
        path: str = "",
        file: str = "",
        filename: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        options = dict(options or {})
        validation = self._validate_manifest(
            rows=rows,
            csv_text=csv_text,
            json_text=json_text,
            options=options,
            path=path,
            file=file,
            filename=filename,
            manifest_path=manifest_path,
        )
        row_errors = self._errors_by_row(validation.get("row_errors", []))
        camera_plans: list[dict[str, Any]] = []
        apply_ready_rows: list[str] = []
        for row in validation.get("rows", []):
            errors = row_errors.get(row["row_number"], [])
            if errors:
                camera_plans.append(
                    {
                        "row_id": row["row_id"],
                        "row_number": row["row_number"],
                        "display_name": row.get("display_name"),
                        "status": "error",
                        "apply_ready": False,
                        "errors": errors,
                        "steps": [],
                        "rollback": {"strategy": "none", "reason": "validation_errors"},
                    }
                )
                continue
            camera_plan = self._build_camera_plan(row, options)
            camera_plans.append(camera_plan)
            apply_ready_rows.append(camera_plan["row_id"])

        if validation["status"] == "error" and not apply_ready_rows:
            status = "error"
        elif validation["status"] == "error":
            status = "partial"
        elif validation["status"] == "warn":
            status = "planned_with_warnings"
        else:
            status = "planned"

        batch_plan_id = f"bulk-plan-{_json_fingerprint({'rows': validation.get('rows', []), 'options': options})}"
        plan = {
            "batch_plan_id": batch_plan_id,
            "status": status,
            "tool": "bulk_onboarding_plan",
            "manifest_summary": validation["summary"],
            "validation_status": validation["status"],
            "validation_errors": validation.get("errors", []),
            "validation_warnings": validation.get("warnings", []),
            "camera_plans": camera_plans,
            "dependency_snapshots": validation["dependencies"],
            "confirmation_token": BULK_ONBOARDING_CONFIRMATION,
            "rollback_confirmation_token": BULK_ONBOARDING_ROLLBACK_CONFIRMATION,
            "batch_rollback_order": list(reversed(apply_ready_rows)),
        }
        self._plans[batch_plan_id] = plan
        self._state[batch_plan_id] = {
            "status": "planned",
            "applied_rows": [],
            "row_results": [],
        }
        self._record(
            "plan",
            status=status,
            batch_plan_id=batch_plan_id,
            row_count=validation["summary"]["total_rows"],
            apply_ready_count=len(apply_ready_rows),
        )
        return redact(plan)

    def bulk_onboarding_apply_plan(self, batch_plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plans.get(batch_plan_id)
        if plan is None:
            return self._reject("apply", batch_plan_id, "unknown_plan", "unknown batch_plan_id")
        state = self._state.get(batch_plan_id, {})
        if state.get("status") != "planned":
            return self._reject("apply", batch_plan_id, "not_planned", "batch plan is not in planned state")
        if confirmation != plan.get("confirmation_token"):
            return self._reject("apply", batch_plan_id, "bad_confirmation", "confirmation token does not match the plan")
        if not self._approval_enabled():
            return self._reject(
                "apply",
                batch_plan_id,
                "approval_env",
                f"Set {BULK_ONBOARDING_APPROVE_ENV}=1 to enable bulk onboarding apply.",
            )

        apply_ready = [camera for camera in plan.get("camera_plans", []) if camera.get("apply_ready")]
        if not apply_ready:
            return self._reject("apply", batch_plan_id, "no_apply_ready_rows", "batch plan has no apply-ready camera rows")

        client = self._ensure_mutation_client()
        row_results: list[dict[str, Any]] = []
        applied_rows: list[dict[str, Any]] = []
        batch_error = False
        for camera_plan in sorted(apply_ready, key=lambda item: int(item.get("row_number", 0))):
            row_state = self._apply_camera_plan(client, camera_plan)
            row_results.append(row_state["public_result"])
            if row_state["applied_record"]["steps"]:
                applied_rows.append(row_state["applied_record"])
                state["applied_rows"] = list(applied_rows)
            if row_state["public_result"]["status"] == "error":
                batch_error = True
                break

        if batch_error:
            final_status = "partial" if any(row["status"] == "applied" for row in row_results) else "error"
        else:
            final_status = "applied"
        state.update({"status": final_status, "row_results": row_results, "applied_rows": applied_rows})
        response = {
            "status": final_status,
            "batch_plan_id": batch_plan_id,
            "row_results": row_results,
            "applied_rows": applied_rows,
            "deterministic_order": [row["row_id"] for row in row_results],
            "rollback_available": bool(applied_rows),
        }
        self._record("apply", status=final_status, batch_plan_id=batch_plan_id, row_count=len(row_results))
        return redact(response)

    def bulk_onboarding_verify_plan(self, batch_plan_id: str) -> dict[str, Any]:
        plan = self._plans.get(batch_plan_id)
        if plan is None:
            return self._reject("verify", batch_plan_id, "unknown_plan", "unknown batch_plan_id")
        state = self._state.get(batch_plan_id, {"status": "planned", "applied_rows": []})
        client = self._mutation_client
        applied_by_row = {row["row_id"]: row for row in state.get("applied_rows", [])}
        rows: list[dict[str, Any]] = []
        for camera_plan in plan.get("camera_plans", []):
            applied = applied_by_row.get(camera_plan["row_id"], {})
            created_uids = list(applied.get("created_uids", []))
            camera_uid = created_uids[0] if created_uids else None
            still_present = False
            read_status = "not_applied"
            if camera_uid and client is not None and hasattr(client, "read_unit"):
                unit = client.read_unit(camera_uid)
                still_present = bool(unit.get("units"))
                read_status = "present" if still_present else "missing"
            elif camera_uid:
                read_status = "unknown_no_reader"
            rows.append(
                {
                    "row_id": camera_plan["row_id"],
                    "row_number": camera_plan["row_number"],
                    "camera": {
                        "expected_display_name": camera_plan.get("display_name"),
                        "expected_uid_placeholder": camera_plan.get("expected_camera_access_point"),
                        "created_uid": camera_uid,
                        "still_present": still_present,
                        "read_status": read_status,
                    },
                    "template": camera_plan.get("expected", {}).get("template"),
                    "archive": camera_plan.get("expected", {}).get("archive"),
                    "detector": camera_plan.get("expected", {}).get("detector"),
                    "snapshot_status": state.get("status", "planned"),
                }
            )
        response = {
            "status": "verified",
            "batch_plan_id": batch_plan_id,
            "snapshot_status": state.get("status", "planned"),
            "rows": rows,
        }
        self._record("verify", status="verified", batch_plan_id=batch_plan_id, row_count=len(rows))
        return redact(response)

    def bulk_onboarding_rollback_plan(self, batch_plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plans.get(batch_plan_id)
        if plan is None:
            return self._reject("rollback", batch_plan_id, "unknown_plan", "unknown batch_plan_id")
        if confirmation != plan.get("rollback_confirmation_token"):
            return self._reject("rollback", batch_plan_id, "bad_confirmation", "rollback confirmation token does not match the plan")
        if not self._approval_enabled():
            return self._reject(
                "rollback",
                batch_plan_id,
                "approval_env",
                f"Set {BULK_ONBOARDING_APPROVE_ENV}=1 to enable bulk onboarding rollback.",
            )

        state = self._state.get(batch_plan_id, {})
        applied_rows = list(state.get("applied_rows", []))
        client = self._ensure_mutation_client()
        row_results: list[dict[str, Any]] = []
        rollback_error = False
        for row in reversed(applied_rows):
            removed_uids: list[str] = []
            step_results: list[dict[str, Any]] = []
            for step in reversed(row.get("steps", [])):
                created = list(reversed(step.get("created_uids", [])))
                if not created:
                    step_results.append({"step_id": step.get("step_id"), "status": "noop", "operation": step.get("operation")})
                    continue
                result = client.change_config({"removed": [{"uid": uid} for uid in created]})
                if result.get("failed"):
                    rollback_error = True
                    step_results.append(
                        {
                            "step_id": step.get("step_id"),
                            "status": "error",
                            "operation": step.get("operation"),
                            "failed": result.get("failed", []),
                        }
                    )
                    break
                removed_uids.extend(created)
                step_results.append(
                    {
                        "step_id": step.get("step_id"),
                        "status": "rolled_back",
                        "operation": step.get("operation"),
                        "removed_uids": created,
                    }
                )
            row_results.append(
                {
                    "row_id": row["row_id"],
                    "row_number": row["row_number"],
                    "status": "error" if rollback_error else "rolled_back",
                    "removed_uids": removed_uids,
                    "steps": step_results,
                }
            )
            if rollback_error:
                break

        final_status = "rollback_partial" if rollback_error else "rolled_back"
        state.update({"status": final_status, "rollback_rows": row_results})
        response = {
            "status": final_status,
            "batch_plan_id": batch_plan_id,
            "row_results": row_results,
            "rollback_order": [row["row_id"] for row in row_results],
        }
        self._record("rollback", status=final_status, batch_plan_id=batch_plan_id, row_count=len(row_results))
        return redact(response)

    def bulk_onboarding_audit_log(self) -> dict[str, Any]:
        return {"status": "ok", "entries": redact(list(self._audit))}

    def _deps(self) -> BulkOnboardingDependencies:
        if self.dependencies is None:
            self.bulk_onboarding_connect_axxon_profile("env")
        return self.dependencies or BulkOnboardingDependencies()

    def _env(self) -> MutableMapping[str, str]:
        return self.environ if self.environ is not None else os.environ

    def _approval_enabled(self) -> bool:
        return self._env().get(BULK_ONBOARDING_APPROVE_ENV) == "1"

    def _ensure_mutation_client(self) -> Any:
        if self._mutation_client is not None:
            return self._mutation_client
        deps = self._deps()
        if deps.mutation_client_factory is None:
            raise RuntimeError("bulk onboarding apply requires a mutation_client_factory")
        self._mutation_client = deps.mutation_client_factory()
        return self._mutation_client

    def _record(self, action: str, **fields: Any) -> None:
        self._sequence += 1
        self._audit.append(
            redact(
                {
                    "sequence": self._sequence,
                    "timestamp": _utc_now(),
                    "action": action,
                    **fields,
                }
            )
        )

    def _reject(self, action: str, batch_plan_id: str, reason: str, message: str) -> dict[str, Any]:
        self._record(action, status="rejected", batch_plan_id=batch_plan_id, reason=reason)
        return {
            "status": "rejected",
            "batch_plan_id": batch_plan_id,
            "message": message,
            "reason": reason,
            "approval_env": BULK_ONBOARDING_APPROVE_ENV,
        }

    def _parse_manifest(
        self,
        *,
        rows: list[dict[str, Any]] | None,
        csv_text: str,
        json_text: str,
        path: str,
        file: str,
        filename: str,
        manifest_path: str,
    ) -> dict[str, Any]:
        path_fields = {
            name: value
            for name, value in {
                "path": path,
                "file": file,
                "filename": filename,
                "manifest_path": manifest_path,
            }.items()
            if _clean_str(value)
        }
        if path_fields:
            return {
                "rows": [],
                "errors": [
                    {
                        "code": "file_import_rejected",
                        "message": "File/path/URL import sources are not supported; pass rows, csv_text, or json_text inline.",
                        "fields": sorted(path_fields),
                    }
                ],
                "row_errors": [],
                "source": None,
            }

        selected = []
        if rows is not None:
            selected.append("rows")
        if _clean_str(csv_text):
            selected.append("csv_text")
        if _clean_str(json_text):
            selected.append("json_text")
        if len(selected) != 1:
            return {
                "rows": [],
                "errors": [
                    {
                        "code": "input_source_count",
                        "message": "Manifest input must provide exactly one of rows, csv_text, or json_text.",
                        "selected_sources": selected,
                    }
                ],
                "row_errors": [],
                "source": None,
            }

        source = selected[0]
        try:
            if source == "rows":
                parsed = list(rows or [])
            elif source == "csv_text":
                parsed = list(csv.DictReader(csv_text.splitlines()))
            else:
                loaded = json.loads(json_text)
                if isinstance(loaded, dict):
                    if "rows" not in loaded or not isinstance(loaded["rows"], list):
                        return {
                            "rows": [],
                            "errors": [{"code": "json_rows_missing", "message": "JSON object input must contain a rows array."}],
                            "row_errors": [],
                            "source": source,
                        }
                    parsed = loaded["rows"]
                elif isinstance(loaded, list):
                    parsed = loaded
                else:
                    return {
                        "rows": [],
                        "errors": [{"code": "json_type", "message": "JSON input must be an array or an object with a rows array."}],
                        "row_errors": [],
                        "source": source,
                    }
        except (csv.Error, json.JSONDecodeError) as exc:
            return {
                "rows": [],
                "errors": [{"code": "parse_error", "message": str(exc)}],
                "row_errors": [],
                "source": source,
            }

        normalized_input_rows: list[dict[str, Any]] = []
        row_errors: list[dict[str, Any]] = []
        for idx, row in enumerate(parsed, start=1):
            if not isinstance(row, dict):
                row_errors.append(
                    {
                        "row_number": idx,
                        "row_id": f"row-{idx}",
                        "code": "row_type",
                        "message": "Manifest rows must be JSON/CSV objects.",
                    }
                )
                continue
            normalized_input_rows.append({"row_number": idx, "source": source, "raw": dict(row)})
        return {"rows": normalized_input_rows, "errors": [], "row_errors": row_errors, "source": source}

    def _validate_manifest(
        self,
        *,
        rows: list[dict[str, Any]] | None,
        csv_text: str,
        json_text: str,
        options: dict[str, Any],
        path: str,
        file: str,
        filename: str,
        manifest_path: str,
    ) -> dict[str, Any]:
        parsed = self._parse_manifest(
            rows=rows,
            csv_text=csv_text,
            json_text=json_text,
            path=path,
            file=file,
            filename=filename,
            manifest_path=manifest_path,
        )
        normalized_rows = [self._normalize_row(item["raw"], item["row_number"], options) for item in parsed["rows"]]
        dependencies = self._dependency_snapshots(options)
        row_errors = list(parsed["row_errors"])
        row_warnings: list[dict[str, Any]] = []
        top_warnings: list[dict[str, Any]] = []
        if dependencies["discovery"]["public"]["status"] == "warn":
            top_warnings.append({"code": "discovery_unavailable", "message": dependencies["discovery"]["public"]["message"]})
        for dep_name in ("catalog", "site_graph"):
            if dependencies[dep_name]["public"]["status"] == "warn":
                top_warnings.append({"code": f"{dep_name}_unavailable", "message": dependencies[dep_name]["public"]["message"]})

        seen: dict[str, dict[str, tuple[int, str]]] = {
            "ip": {},
            "mac": {},
            "display_name": {},
            "display_id": {},
            "row_signature": {},
        }
        for row in normalized_rows:
            errors, warnings = self._validate_row(row, options, dependencies)
            row_errors.extend(errors)
            row_warnings.extend(warnings)
            for field_name in ("ip", "mac", "display_name", "display_id"):
                value = _lower(row.get(field_name))
                if not value:
                    continue
                prior = seen[field_name].get(value)
                if prior is not None:
                    row_errors.append(
                        {
                            "row_number": row["row_number"],
                            "row_id": row["row_id"],
                            "code": "duplicate_field",
                            "field": field_name,
                            "message": f"Duplicate {field_name} also appears on row {prior[0]}.",
                        }
                    )
                else:
                    seen[field_name][value] = (row["row_number"], row["row_id"])
            signature = json.dumps(
                {
                    "display_name": _lower(row.get("display_name")),
                    "display_id": _lower(row.get("display_id")),
                    "vendor": _lower(row.get("vendor")),
                    "model": _lower(row.get("model")),
                    "ip": _lower(row.get("ip")),
                    "mac": _lower(row.get("mac")),
                },
                sort_keys=True,
            )
            prior_signature = seen["row_signature"].get(signature)
            if prior_signature is not None:
                row_errors.append(
                    {
                        "row_number": row["row_number"],
                        "row_id": row["row_id"],
                        "code": "duplicate_row",
                        "message": f"Duplicate manifest row also appears on row {prior_signature[0]}.",
                    }
                )
            else:
                seen["row_signature"][signature] = (row["row_number"], row["row_id"])

        errors = list(parsed["errors"])
        error_rows = {item.get("row_number") for item in row_errors if item.get("row_number") is not None}
        warning_rows = {item.get("row_number") for item in row_warnings if item.get("row_number") is not None}
        total_rows = len(normalized_rows) + len(parsed["row_errors"])
        summary = {
            "total_rows": total_rows,
            "valid_rows": max(0, len(normalized_rows) - len(error_rows)),
            "error_rows": len(error_rows),
            "warning_rows": len(warning_rows),
            "source": parsed["source"],
        }
        status = _status_from(errors + row_errors, top_warnings + row_warnings)
        return {
            "status": status,
            "tool": "bulk_onboarding_validate_manifest",
            "summary": summary,
            "rows": normalized_rows,
            "errors": errors,
            "warnings": top_warnings,
            "row_errors": row_errors,
            "row_warnings": row_warnings,
            "dependencies": {key: value["public"] for key, value in dependencies.items()},
        }

    def _normalize_row(self, row: dict[str, Any], row_number: int, options: dict[str, Any]) -> dict[str, Any]:
        display_name = _clean_str(row.get("display_name") or row.get("name"))
        display_id = _clean_str(row.get("display_id"))
        row_id = display_id or f"row-{row_number}-{_stable_slug(display_name)}"
        detector_profile = _clean_str(row.get("detector_profile") or row.get("detector") or options.get("detector_profile"))
        normalized = {
            "row_number": row_number,
            "row_id": row_id,
            "display_name": display_name,
            "display_id": display_id,
            "host_uid": _clean_str(row.get("host_uid") or options.get("host_uid") or DEFAULT_HOST_UID),
            "vendor": _clean_str(row.get("vendor")),
            "model": _clean_str(row.get("model")),
            "ip": _clean_str(row.get("ip") or row.get("ip_address")),
            "mac": _canonical_mac(_clean_str(row.get("mac") or row.get("mac_address"))),
            "login": _clean_str(row.get("login") or row.get("username")),
            "password": _clean_str(row.get("password")),
            "credentials": row.get("credentials") if isinstance(row.get("credentials"), dict) else {},
            "archive_ref": _clean_str(row.get("archive_uid") or row.get("archive_access_point") or options.get("archive_uid")),
            "template_id": _clean_str(row.get("template_id") or options.get("template_id")),
            "template_name": _clean_str(row.get("template_name") or options.get("template_name")),
            "detector_profile": detector_profile,
            "detector_overrides": self._detector_overrides(row, options),
            "raw_overrides": {
                key: value
                for key, value in row.items()
                if key not in set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS) | {"ip_address", "mac_address", "credentials"}
            },
        }
        if not normalized["password"] and isinstance(normalized["credentials"], dict):
            normalized["password"] = _clean_str(normalized["credentials"].get("password"))
        return normalized

    def _detector_overrides(self, row: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        if isinstance(options.get("detector_overrides"), dict):
            overrides.update(options["detector_overrides"])
        for key, value in row.items():
            if str(key).startswith("detector_") and key != "detector_profile":
                overrides[key] = value
        return overrides

    def _dependency_snapshots(self, options: dict[str, Any]) -> dict[str, dict[str, Any]]:
        deps = self._deps() if self.dependencies is not None else BulkOnboardingDependencies()
        catalog_pairs, catalog_public = self._catalog_snapshot(deps.catalog_provider)
        discovery_index, discovery_public = self._discovery_snapshot(deps.discovery_provider)
        site_data, site_public = self._site_graph_snapshot(deps.site_graph_provider)
        archives = site_data["archives"]
        templates = site_data["templates"]
        detectors_public = {
            "status": "ok",
            "supported_profiles": sorted(SUPPORTED_DETECTOR_PROFILES),
            "requested_profile": _clean_str(options.get("detector_profile")),
        }
        return {
            "catalog": {"pairs": catalog_pairs, "public": catalog_public},
            "discovery": {"index": discovery_index, "public": discovery_public},
            "site_graph": {"data": site_data, "public": site_public},
            "archives": {
                "refs": archives,
                "public": {"status": site_public["status"], "count": len(archives), "refs": sorted(archives)},
            },
            "templates": {
                "refs": templates,
                "public": {"status": site_public["status"], "count": len(templates), "refs": sorted(templates)},
            },
            "detectors": {"public": detectors_public},
        }

    def _catalog_snapshot(self, provider: Any | None) -> tuple[set[tuple[str, str]] | None, dict[str, Any]]:
        if provider is None:
            return None, {"status": "warn", "message": "DevicesCatalog provider is unavailable.", "count": 0}
        try:
            if hasattr(provider, "list_devices"):
                response = _call_provider(provider, "list_devices")
                devices = response.get("devices", []) if isinstance(response, dict) else response
                status = response.get("status", "ok") if isinstance(response, dict) else "ok"
                if status not in {"ok", "warn"}:
                    return None, {"status": "warn", "message": "DevicesCatalog returned a non-ok status.", "count": 0}
            elif hasattr(provider, "devices"):
                devices = provider.devices
            else:
                return None, {"status": "warn", "message": "DevicesCatalog provider exposes no list_devices method.", "count": 0}
            pairs = {
                (_lower(item.get("vendor")), _lower(item.get("model")))
                for item in devices
                if isinstance(item, dict) and _clean_str(item.get("vendor")) and _clean_str(item.get("model"))
            }
            return pairs, {"status": "ok", "count": len(pairs), "supported_pairs": sorted(f"{v}/{m}" for v, m in pairs)}
        except Exception as exc:
            return None, {"status": "warn", "message": f"DevicesCatalog unavailable: {exc}", "count": 0}

    def _discovery_snapshot(self, provider: Any | None) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
        index = {"ip": {}, "mac": {}}
        if provider is None:
            return index, {"status": "warn", "message": "DiscoveryService provider is unavailable.", "count": 0}
        try:
            if hasattr(provider, "discover_devices"):
                response = _call_provider(provider, "discover_devices", max_devices=1000, max_seconds=5.0)
            elif hasattr(provider, "devices"):
                response = {"status": "ok", "devices": provider.devices}
            else:
                return index, {"status": "warn", "message": "DiscoveryService provider exposes no discover_devices method.", "count": 0}
            if not isinstance(response, dict) or response.get("status", "ok") not in {"ok", "warn"}:
                return index, {"status": "warn", "message": "DiscoveryService data is unavailable.", "count": 0}
            devices = response.get("devices", [])
            for item in devices:
                if not isinstance(item, dict):
                    continue
                ip = _clean_str(item.get("ip") or item.get("ip_address"))
                mac = _canonical_mac(_clean_str(item.get("mac") or item.get("mac_address")))
                if ip:
                    index["ip"][ip] = item
                if mac:
                    index["mac"][mac] = item
            return index, {"status": "ok", "count": len(devices)}
        except Exception as exc:
            return index, {"status": "warn", "message": f"DiscoveryService unavailable: {exc}", "count": 0}

    def _site_graph_snapshot(self, provider: Any | None) -> tuple[dict[str, Any], dict[str, Any]]:
        empty = {"cameras": [], "archives": set(), "templates": set()}
        if provider is None:
            return empty, {"status": "warn", "message": "Site graph provider is unavailable.", "cameras": 0}
        try:
            if hasattr(provider, "build_site_graph"):
                response = _call_provider(
                    provider,
                    "build_site_graph",
                    include_layouts=False,
                    include_maps=False,
                    include_permissions=False,
                    include_health=False,
                    limit=1000,
                )
            else:
                response = provider
            if not isinstance(response, dict) or response.get("status", "ok") not in {"ok", "warn"}:
                return empty, {"status": "warn", "message": "Site graph data is unavailable.", "cameras": 0}
            cameras = [item for item in response.get("cameras", []) if isinstance(item, dict)]
            archives = self._collect_refs(response.get("archives", []), ("uid", "access_point", "archive_access_point", "name"))
            templates = self._collect_refs(response.get("templates", []), ("id", "template_id", "name"))
            for node in response.get("nodes", []):
                if not isinstance(node, dict):
                    continue
                node_type = _lower(node.get("type") or node.get("kind") or node.get("unit_type"))
                if "deviceipint" in node_type or "camera" in node_type:
                    cameras.append(node)
                if "archive" in node_type or "multimediastorage" in node_type:
                    archives.update(_value_set(node.get("uid"), node.get("access_point"), node.get("name")))
                if "template" in node_type:
                    templates.update(_value_set(node.get("id"), node.get("template_id"), node.get("name")))
            return (
                {"cameras": cameras, "archives": archives, "templates": templates},
                {"status": "ok", "cameras": len(cameras), "archives": len(archives), "templates": len(templates)},
            )
        except Exception as exc:
            return empty, {"status": "warn", "message": f"Site graph unavailable: {exc}", "cameras": 0}

    def _collect_refs(self, items: Any, fields: tuple[str, ...]) -> set[str]:
        refs: set[str] = set()
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            for field_name in fields:
                refs.update(_value_set(item.get(field_name)))
        return refs

    def _validate_row(
        self,
        row: dict[str, Any],
        options: dict[str, Any],
        dependencies: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        def add_error(code: str, message: str, field: str = "") -> None:
            error = {"row_number": row["row_number"], "row_id": row["row_id"], "code": code, "message": message}
            if field:
                error["field"] = field
            errors.append(error)

        for field_name in REQUIRED_FIELDS:
            if not row.get(field_name):
                add_error("required_field", f"{field_name} is required.", field_name)
        if not row.get("ip") and not row.get("mac"):
            add_error("device_identity", "At least one of ip/ip_address/mac/mac_address is required.", "ip")
        if row.get("ip") and not _valid_ip(row["ip"]):
            add_error("invalid_ip", f"Invalid IP address: {row['ip']}", "ip")
        if row.get("mac") and not _valid_mac(row["mac"]):
            add_error("invalid_mac", f"Invalid MAC address: {row['mac']}", "mac")

        pairs = dependencies["catalog"]["pairs"]
        if pairs is not None and row.get("vendor") and row.get("model"):
            if (_lower(row["vendor"]), _lower(row["model"])) not in pairs:
                add_error("unsupported_catalog_model", f"Unsupported vendor/model: {row['vendor']}/{row['model']}", "model")

        discovery_public = dependencies["discovery"]["public"]
        discovery_index = dependencies["discovery"]["index"]
        discovered = None
        if row.get("ip"):
            discovered = discovery_index["ip"].get(row["ip"])
        if discovered is None and row.get("mac"):
            discovered = discovery_index["mac"].get(row["mac"])
        if discovered:
            found_vendor = _clean_str(discovered.get("vendor"))
            found_model = _clean_str(discovered.get("model"))
            if (
                found_vendor
                and found_model
                and (_lower(found_vendor), _lower(found_model)) != (_lower(row.get("vendor")), _lower(row.get("model")))
            ):
                add_error(
                    "discovery_mismatch",
                    f"DiscoveryService found {found_vendor}/{found_model} for the supplied IP/MAC.",
                    "vendor",
                )
        elif discovery_public["status"] == "warn" and options.get("require_discovery"):
            add_error("discovery_required", "Discovery correlation is required but discovery data is unavailable.", "ip")

        self._validate_site_conflicts(row, dependencies["site_graph"]["data"]["cameras"], add_error)
        archive_ref = row.get("archive_ref")
        if archive_ref and archive_ref not in dependencies["archives"]["refs"]:
            add_error("archive_missing", f"Archive reference does not exist: {archive_ref}", "archive_uid")
        template_id = row.get("template_id")
        template_name = row.get("template_name")
        template_refs = dependencies["templates"]["refs"]
        if template_id and template_id not in template_refs:
            add_error("template_missing", f"Template id does not exist: {template_id}", "template_id")
        if template_name and template_name not in template_refs:
            add_error("template_missing", f"Template name does not exist: {template_name}", "template_name")

        archive_operation = _lower(row.get("raw_overrides", {}).get("archive_operation") or row.get("raw_overrides", {}).get("operation"))
        if archive_operation in DESTRUCTIVE_ARCHIVE_OPERATIONS:
            add_error("destructive_archive_maintenance", f"Destructive archive operation is rejected: {archive_operation}", "archive_operation")

        detector_profile = _clean_str(row.get("detector_profile"))
        if detector_profile and detector_profile not in SUPPORTED_DETECTOR_PROFILES:
            add_error("unsupported_detector_profile", f"Unsupported detector profile: {detector_profile}", "detector_profile")

        return errors, warnings

    def _validate_site_conflicts(
        self,
        row: dict[str, Any],
        cameras: list[dict[str, Any]],
        add_error: Callable[[str, str, str], None],
    ) -> None:
        for camera in cameras:
            cam_values = {
                "display_name": _lower(camera.get("display_name") or camera.get("name")),
                "display_id": _lower(camera.get("display_id")),
                "ip": _lower(camera.get("ip") or camera.get("ip_address")),
                "mac": _lower(_canonical_mac(_clean_str(camera.get("mac") or camera.get("mac_address")))),
            }
            for field_name in ("display_name", "display_id", "ip", "mac"):
                value = _lower(row.get(field_name))
                if value and cam_values[field_name] == value:
                    add_error(
                        "existing_camera",
                        f"Existing camera conflict on {field_name}: {camera.get('uid') or camera.get('access_point') or '<unknown>'}",
                        field_name,
                    )
                    return

    def _errors_by_row(self, row_errors: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in row_errors:
            row_number = item.get("row_number")
            if isinstance(row_number, int):
                grouped.setdefault(row_number, []).append(item)
        return grouped

    def _build_camera_plan(self, row: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        row_id = row["row_id"]
        camera_placeholder = f"<created:{row_id}:DeviceIpint>"
        video_ap_placeholder = f"{camera_placeholder}/SourceEndpoint.video:0:0"
        camera_payload = self._camera_change_config_payload(row)
        steps: list[dict[str, Any]] = [
            {
                "step_id": f"{row_id}:create-camera",
                "operation": "add",
                "service": "ConfigurationService.ChangeConfig",
                "workflow": "create_camera",
                "unit_type": "DeviceIpint",
                "payload": camera_payload,
                "expected": {
                    "display_name": row["display_name"],
                    "vendor": row["vendor"],
                    "model": row["model"],
                    "camera_uid": camera_placeholder,
                    "video_source_ap": video_ap_placeholder,
                },
                "rollback": {"operation": "remove_created_uids"},
            }
        ]
        expected: dict[str, Any] = {
            "display_name": row["display_name"],
            "vendor": row["vendor"],
            "model": row["model"],
            "display_id": row.get("display_id"),
            "camera_access_point": video_ap_placeholder,
        }
        if row.get("template_id") or row.get("template_name"):
            template = {"id": row.get("template_id"), "name": row.get("template_name")}
            expected["template"] = template
            steps.append(
                {
                    "step_id": f"{row_id}:apply-template",
                    "operation": "apply_template",
                    "service": "ConfigurationService.ChangeTemplates",
                    "template": template,
                    "target_camera_uid": camera_placeholder,
                    "rollback": {"operation": "restore_recorded_camera_snapshot"},
                }
            )
        if row.get("archive_ref"):
            archive = {"ref": row["archive_ref"], "destructive": False}
            expected["archive"] = archive
            steps.append(
                {
                    "step_id": f"{row_id}:archive-assign",
                    "operation": "archive_assign",
                    "service": "ConfigurationService.ChangeConfig",
                    "workflow": "archive_policy_update",
                    "archive_ref": row["archive_ref"],
                    "destructive": False,
                    "descriptor_backed": True,
                    "rejected_operations": sorted(DESTRUCTIVE_ARCHIVE_OPERATIONS),
                    "rollback": {"operation": "restore_recorded_archive_policy"},
                }
            )
        detector_profile = row.get("detector_profile")
        if detector_profile:
            meta = SUPPORTED_DETECTOR_PROFILES[detector_profile]
            detector = {
                "profile": detector_profile,
                "workflow": meta["workflow"],
                "detector": meta["detector"],
                "unit_type": meta["unit_type"],
                "detector_overrides": dict(row.get("detector_overrides") or {}),
            }
            expected["detector"] = detector
            steps.append(
                {
                    "step_id": f"{row_id}:detector-default",
                    "operation": "add_detector",
                    "service": "ConfigurationService.ChangeConfig",
                    "workflow": meta["workflow"],
                    "unit_type": meta["unit_type"],
                    "detector": meta["detector"],
                    "params": {
                        "display_name": f"{row['display_name']} {meta['detector']}",
                        "video_source_ap": video_ap_placeholder,
                        "detector_overrides": dict(row.get("detector_overrides") or {}),
                    },
                    "rollback": {"operation": "remove_created_uids"},
                }
            )
        return {
            "row_id": row_id,
            "row_number": row["row_number"],
            "status": "planned",
            "apply_ready": True,
            "display_name": row["display_name"],
            "host_uid": row["host_uid"],
            "vendor": row["vendor"],
            "model": row["model"],
            "ip": row.get("ip"),
            "mac": row.get("mac"),
            "expected_camera_access_point": video_ap_placeholder,
            "risk": "mutation",
            "steps": steps,
            "expected": expected,
            "rollback": {
                "strategy": "reverse_recorded_steps",
                "description": "Rollback removes only ChangeConfig-created units and restores recorded template/archive metadata when available.",
            },
            "diff": {
                "before": {"camera": None},
                "after": {
                    "camera": {
                        "display_name": row["display_name"],
                        "vendor": row["vendor"],
                        "model": row["model"],
                        "ip": row.get("ip"),
                        "mac": row.get("mac"),
                    },
                    "template": expected.get("template"),
                    "archive": expected.get("archive"),
                    "detector": expected.get("detector"),
                },
            },
        }

    def _camera_change_config_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        props = [
            _prop_string("vendor", row["vendor"], properties=[_prop_string("model", row["model"], properties=[])]),
            _prop_string("display_name", row["display_name"], properties=[]),
            _prop_bool("blockingConfiguration", False),
        ]
        if row.get("display_id"):
            props.append(_prop_string("display_id", row["display_id"], properties=[]))
        if row.get("ip"):
            props.append(_prop_string("ip", row["ip"]))
        if row.get("mac"):
            props.append(_prop_string("mac", row["mac"]))
        if row.get("login") or row.get("password"):
            props.append(
                _prop_string(
                    "credentials",
                    "inline",
                    properties=[
                        _prop_string("login", row.get("login", "")),
                        _prop_string("password", row.get("password", "")),
                    ],
                )
            )
        return {"added": [{"uid": row["host_uid"], "units": [{"type": "DeviceIpint", "properties": props, "units": []}]}]}

    def _apply_camera_plan(self, client: Any, camera_plan: dict[str, Any]) -> dict[str, Any]:
        created_uids: list[str] = []
        step_records: list[dict[str, Any]] = []
        row_status = "applied"
        row_error: dict[str, Any] | None = None
        for step in camera_plan.get("steps", []):
            operation = step.get("operation")
            if operation not in {"add", "add_detector"}:
                step_records.append(
                    {
                        "step_id": step["step_id"],
                        "operation": operation,
                        "status": "recorded",
                        "created_uids": [],
                    }
                )
                continue
            payload = step.get("payload") if operation == "add" else self._detector_payload(camera_plan, step, created_uids)
            result = client.change_config(payload)
            if result.get("failed"):
                row_status = "error"
                row_error = {
                    "step_id": step.get("step_id"),
                    "operation": operation,
                    "failed": result.get("failed", []),
                    "failed_reason": result.get("failed_reason", []),
                }
                break
            added = list(result.get("added", []))
            created_uids.extend(added)
            step_records.append(
                {
                    "step_id": step["step_id"],
                    "operation": operation,
                    "status": "applied",
                    "created_uids": added,
                }
            )
        public_result: dict[str, Any] = {
            "row_id": camera_plan["row_id"],
            "row_number": camera_plan["row_number"],
            "status": row_status,
            "created_uids": list(created_uids),
            "steps": list(step_records),
        }
        if row_error:
            public_result["error"] = row_error
        return {
            "public_result": public_result,
            "applied_record": {
                "row_id": camera_plan["row_id"],
                "row_number": camera_plan["row_number"],
                "status": row_status,
                "created_uids": created_uids,
                "steps": step_records,
            },
        }

    def _detector_payload(
        self,
        camera_plan: dict[str, Any],
        step: dict[str, Any],
        created_uids: list[str],
    ) -> dict[str, Any]:
        camera_uid = created_uids[0] if created_uids else f"<created:{camera_plan['row_id']}:DeviceIpint>"
        props = [
            _prop_string("display_name", step["params"]["display_name"]),
            _prop_string("detector", step["detector"]),
            _prop_string("video_source_ap", f"{camera_uid}/SourceEndpoint.video:0:0"),
        ]
        for key, value in sorted(step["params"].get("detector_overrides", {}).items()):
            props.append(_prop_string(str(key), str(value)))
        return {
            "added": [
                {
                    "uid": camera_plan["host_uid"],
                    "units": [{"type": step["unit_type"], "properties": props, "units": []}],
                }
            ]
        }
