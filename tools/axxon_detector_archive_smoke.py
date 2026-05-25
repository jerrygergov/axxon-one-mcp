#!/usr/bin/env python3
"""Live smoke for Phase 5E detector archive tools.

Default mode is read-only. ``--mutation`` adds approved operator workflows, and
``--archive-maintenance-noop`` dispatches maintenance workflows only against a
``codex-nonexistent-*`` volume id.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
import uuid

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import add_common_args, config_from_args  # noqa: E402
from axxon_mcp_detector_archive import AxxonMcpDetectorArchive, _archive_policy_descriptor  # noqa: E402


LATEST_BASENAME = "phase-5e-detector-archive-smoke-latest"
REPORT_BASENAME = "phase-5e-detector-archive-smoke"
OPERATOR_APPROVE_ENV = "AXXON_OPERATOR_APPROVE"
ARCHIVE_MAINTENANCE_APPROVE_ENV = "AXXON_ARCHIVE_MAINTENANCE_APPROVE"
NOOP_VOLUME_PREFIX = "codex-nonexistent-"
DEFAULT_METADATA_SAMPLE_LIMIT = 20
DEFAULT_METADATA_SAMPLE_TIMEOUT = 5.0
SECRET_KEY_RE = re.compile(
    r"(password|passwd|pwd|secret|certificate|private[_-]?key|serial|license|root[_-]?password|"
    r"[A-Za-z0-9_-]*token[A-Za-z0-9_-]*|authorization|auth)",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"\bBearer\s+[^,\s;}\]]+", re.IGNORECASE)
QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<key>\b(?:password|passwd|pwd|secret|root[_-]?password|[A-Za-z0-9_-]*token[A-Za-z0-9_-]*)\b)"
    r"(?P<sep>\s*[:=]\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<key>\b(?:password|passwd|pwd|secret|root[_-]?password|[A-Za-z0-9_-]*token[A-Za-z0-9_-]*)\b)"
    r"(?P<sep>\s*[:=]\s*)[^,\s;}\]]+",
    re.IGNORECASE,
)
USER_KEYS = {"username", "user", "login"}
TLS_CN_KEYS = {"tls_cn", "tls-cn", "tls_common_name"}


def _secret_key(key: Any) -> bool:
    return bool(SECRET_KEY_RE.search(str(key)))


def _identity_key(key: Any) -> str:
    normalized = str(key).lower()
    if normalized in USER_KEYS:
        return "user"
    if normalized in TLS_CN_KEYS:
        return "tls-cn"
    return ""


def _sanitize_text(value: str, host: str = "") -> str:
    text = value
    if host and not text.startswith("hosts/"):
        text = text.replace(host, "<demo-host>")
    text = BEARER_RE.sub("Bearer <redacted>", text)
    text = QUOTED_SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}<redacted>", text)
    text = UNQUOTED_SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}<redacted>", text)
    return text


def sanitize_evidence(value: Any, host: str = "") -> Any:
    """Sanitize report evidence while preserving intrinsic Axxon UIDs."""
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            identity = _identity_key(key)
            if identity == "user":
                out[key] = "<demo-user>" if item else item
            elif identity == "tls-cn":
                out[key] = "<demo-tls-cn>" if item else item
            elif _secret_key(key):
                if isinstance(item, str) and BEARER_RE.search(item):
                    out[key] = _sanitize_text(item, host)
                else:
                    out[key] = "<redacted>" if item else item
            else:
                out[key] = sanitize_evidence(item, host)
        return out
    if isinstance(value, list):
        return [sanitize_evidence(item, host) for item in value]
    if isinstance(value, tuple):
        return [sanitize_evidence(item, host) for item in value]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, str):
        return _sanitize_text(value, host)
    return value


def report_paths(report_dir: Path, stamp: str) -> dict[str, Path]:
    return {
        "json": report_dir / f"{REPORT_BASENAME}-{stamp}.json",
        "md": report_dir / f"{REPORT_BASENAME}-{stamp}.md",
        "latest_json": report_dir / f"{LATEST_BASENAME}.json",
        "latest_md": report_dir / f"{LATEST_BASENAME}.md",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--metadata-sample-limit", type=int, default=DEFAULT_METADATA_SAMPLE_LIMIT)
    parser.add_argument("--metadata-sample-timeout", type=float, default=DEFAULT_METADATA_SAMPLE_TIMEOUT)
    parser.add_argument("--noop-volume-prefix", default=NOOP_VOLUME_PREFIX)
    parser.add_argument("--detector-uid", default=os.getenv("AXXON_DETECTOR_UID", ""))
    parser.add_argument("--video-source-ap", default=os.getenv("AXXON_VIDEO_SOURCE_AP", ""))
    parser.add_argument("--vmda-source-ap", default=os.getenv("AXXON_VMDA_SOURCE_AP", ""))
    parser.add_argument("--archive-access-point", default=os.getenv("AXXON_ARCHIVE_ACCESS_POINT", ""))
    parser.add_argument("--archive-policy-fixture-uid", default=os.getenv("AXXON_ARCHIVE_POLICY_FIXTURE_UID", ""))
    parser.add_argument("--mutation", action="store_true")
    parser.add_argument("--archive-maintenance-noop", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    args.metadata_sample_limit = max(1, min(200, int(args.metadata_sample_limit)))
    args.metadata_sample_timeout = max(0.1, min(30.0, float(args.metadata_sample_timeout)))
    if not args.noop_volume_prefix.startswith(NOOP_VOLUME_PREFIX):
        parser.error(f"--noop-volume-prefix must start with {NOOP_VOLUME_PREFIX!r}")
    if args.mutation and os.environ.get(OPERATOR_APPROVE_ENV) != "1":
        parser.error(f"--mutation requires {OPERATOR_APPROVE_ENV}=1")
    if args.archive_maintenance_noop and (
        os.environ.get(OPERATOR_APPROVE_ENV) != "1" or os.environ.get(ARCHIVE_MAINTENANCE_APPROVE_ENV) != "1"
    ):
        parser.error(
            f"--archive-maintenance-noop requires {OPERATOR_APPROVE_ENV}=1 and "
            f"{ARCHIVE_MAINTENANCE_APPROVE_ENV}=1"
        )
    return args


def result_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = str(payload.get("status") or "").lower()
        if status in {"ok", "applied", "verified", "rolled_back", "planned"}:
            return "PASS"
        if status in {"fixture-needed", "skipped", "gap"}:
            return "WARN"
        if status in {"error", "fail", "failed", "rejected"}:
            return "FAIL"
    return "PASS"


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def prop_int(prop_id: str, value: int) -> dict[str, Any]:
    return {"id": prop_id, "value_int32": value}


def changed_scalar_property(prop: dict[str, Any]) -> dict[str, Any] | None:
    prop_id = prop.get("id")
    if not prop_id or prop.get("readonly") or prop.get("internal") or prop_id == "display_name":
        return None
    if "value_bool" in prop:
        return prop_bool(prop_id, not bool(prop.get("value_bool")))
    if "value_int32" in prop:
        current = int(prop.get("value_int32") or 0)
        bounds = prop.get("range_constraint") or {}
        minimum = int(bounds.get("min_int", 0))
        maximum = int(bounds.get("max_int", max(current + 1, minimum + 1)))
        candidate = current + 1 if current + 1 <= maximum else minimum
        return prop_int(prop_id, candidate)
    enum_items = (prop.get("enum_constraint") or {}).get("items") or []
    if "value_string" in prop and enum_items:
        current = prop.get("value_string") or ""
        for item in enum_items:
            candidate = item.get("value_string") or item.get("value") or ""
            if candidate and candidate != current:
                return {"id": prop_id, "value_string": candidate}
    return None


def detector_scalar_change(properties: list[dict[str, Any]]) -> dict[str, Any] | None:
    preferred = ["enabled", "period", "onlyKeyFrames", "FrameScale", "plateProbMin", "deviceType"]
    by_id = {prop.get("id"): prop for prop in properties if isinstance(prop, dict)}
    for prop_id in preferred:
        change = changed_scalar_property(by_id.get(prop_id, {}))
        if change:
            return change
    for prop in properties:
        if isinstance(prop, dict):
            change = changed_scalar_property(prop)
            if change:
                return change
    return None


def visual_element_change(unit: dict[str, Any]) -> dict[str, Any] | None:
    for prop in unit.get("properties") or []:
        if not isinstance(prop, dict) or prop.get("readonly") or prop.get("internal") or not prop.get("id"):
            continue
        if "value_rectangle" in prop:
            old = prop.get("value_rectangle") or {}
            return {
                "id": prop["id"],
                "value_rectangle": {
                    "x": 0.2,
                    "y": 0.2,
                    "w": 0.6,
                    "h": 0.6,
                    "index": int(old.get("index") or 0),
                },
            }
        if "value_simple_polygon" in prop:
            return {
                "id": prop["id"],
                "value_simple_polygon": {
                    "points": [
                        {"x": 0.2, "y": 0.2},
                        {"x": 0.2, "y": 0.8},
                        {"x": 0.8, "y": 0.8},
                        {"x": 0.8, "y": 0.2},
                    ]
                },
            }
    return None


def iter_units(unit: dict[str, Any]) -> list[dict[str, Any]]:
    units = [unit]
    for child in unit.get("units") or []:
        if isinstance(child, dict):
            units.extend(iter_units(child))
    return units


def nested_property_from_path(path: str, value_kind: str, value: Any) -> dict[str, Any] | None:
    if value_kind not in {"value_bool", "value_int32", "value_int64", "value_uint32", "value_uint64", "value_string"}:
        return None
    if value == "<redacted>":
        return None
    parts = [part for part in path.split(".") if part]
    if not parts:
        return None
    leaf: dict[str, Any] = {"id": parts[-1], value_kind: value}
    for part in reversed(parts[:-1]):
        leaf = {"id": part, "properties": [leaf]}
    return leaf


def first_policy_noop_property(policy: dict[str, Any]) -> dict[str, Any] | None:
    for section in ("recording_properties", "retention_properties", "schedule_properties", "archive_bindings"):
        for item in policy.get(section) or []:
            if item.get("readonly"):
                continue
            prop = nested_property_from_path(str(item.get("path") or ""), str(item.get("value_kind") or ""), item.get("value"))
            if prop:
                return prop
    return None


class DetectorArchiveSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.started_at = dt.datetime.now(dt.UTC)
        self.tool = AxxonMcpDetectorArchive(config_factory=lambda: config_from_args(args))
        self.results: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}

    @property
    def host(self) -> str:
        try:
            client = self.tool.ensure_client()
            return str(getattr(getattr(client, "config", None), "host", self.args.host))
        except Exception:
            return str(self.args.host)

    def record(self, group: str, func: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        try:
            evidence = func()
            status = result_status(evidence)
        except Exception as exc:  # noqa: BLE001 - live smoke reports structured failures.
            evidence = {"status": "error", "error_type": exc.__class__.__name__, "message": str(exc)[:800]}
            if self.args.verbose:
                import traceback

                evidence["traceback"] = traceback.format_exc()
            status = "FAIL"
        clean = sanitize_evidence(evidence, self.host)
        self.results.append(
            {
                "group": group,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "evidence": clean,
            }
        )
        return evidence

    def run(self) -> dict[str, Any]:
        self.record("connect", self.connect)
        fixture_report = self.record("analytics_fixture_report", self.tool.analytics_fixture_report)
        self.context["fixture_report"] = fixture_report if isinstance(fixture_report, dict) else {}
        self.record("detector_kind_catalog", self.tool.detector_kind_catalog)
        self.record("av_detector_schema", lambda: self.tool.detector_parameter_schema("AVDetector", "MotionDetection"))
        self.record("appdata_detector_schema", lambda: self.tool.detector_parameter_schema("AppDataDetector", "MoveInZone"))
        detector_uid = self.detector_uid()
        if detector_uid:
            self.record("detector_config_get", lambda: self.tool.detector_config_get(detector_uid))
            self.record("detector_visual_elements", lambda: self.tool.detector_visual_elements(detector_uid))
        else:
            self.record("detector_config_get", lambda: self.fixture_needed("detector_config_get", "No detector fixture was discovered."))
            self.record(
                "detector_visual_elements",
                lambda: self.fixture_needed("detector_visual_elements", "No detector fixture was discovered."),
            )
        self.record("metadata_schema_catalog", self.tool.metadata_schema_catalog)
        vmda_source_ap = self.vmda_source_ap()
        if vmda_source_ap:
            self.record(
                "metadata_sample_bounded",
                lambda: self.tool.metadata_sample_bounded(
                    vmda_source_ap,
                    timeout_s=self.args.metadata_sample_timeout,
                    limit=self.args.metadata_sample_limit,
                ),
            )
        else:
            self.record(
                "metadata_sample_bounded",
                lambda: self.fixture_needed("metadata_sample_bounded", "No VMDA or metadata endpoint fixture was discovered."),
            )
        archive_target = self.archive_policy_target()
        if archive_target:
            self.record("archive_policy_get", lambda: self.tool.archive_policy_get(archive_target))
        else:
            self.record(
                "archive_policy_get",
                lambda: self.fixture_needed("archive_policy_get", "No camera/archive fixture was discovered."),
            )
        archive_status = self.record("archive_management_status", self.tool.archive_management_status)
        self.context["archive_management_status"] = archive_status if isinstance(archive_status, dict) else {}

        if self.args.mutation:
            self.run_mutation()
        if self.args.archive_maintenance_noop:
            self.run_archive_maintenance_noop()

        report = self.report()
        self.write_report(report)
        return report

    def connect(self) -> dict[str, Any]:
        connected = self.tool.connect_axxon_profile("env")
        client = self.tool.ensure_client()
        authenticate = getattr(client, "authenticate_http_grpc", None)
        if callable(authenticate):
            authenticate()
        return connected

    def fixture_needed(self, tool: str, message: str) -> dict[str, Any]:
        return {"status": "fixture-needed", "tool": tool, "message": message}

    def detector_uid(self) -> str:
        if self.args.detector_uid:
            return self.args.detector_uid
        fixtures = (self.context.get("fixture_report") or {}).get("fixtures") or {}
        for key in ("av_detector", "appdata_detector"):
            evidence = fixtures.get(key, {}).get("evidence") or []
            for item in evidence:
                if isinstance(item, str) and "Detector" in item:
                    return item.split("/EventSupplier")[0].split("/SourceEndpoint")[0]
        return ""

    def vmda_source_ap(self) -> str:
        if self.args.vmda_source_ap:
            return self.args.vmda_source_ap
        fixtures = (self.context.get("fixture_report") or {}).get("fixtures") or {}
        for item in fixtures.get("vmda_metadata", {}).get("evidence") or []:
            if isinstance(item, str) and ("SourceEndpoint.vmda" in item or "SourceEndpoint.metadata" in item):
                return item
        return self.discover_component("SourceEndpoint.vmda") or self.discover_component("SourceEndpoint.metadata")

    def video_source_ap(self) -> str:
        if self.args.video_source_ap:
            return self.args.video_source_ap
        return self.discover_component("SourceEndpoint.video") or self.discover_component("/Sources/src.")

    def discover_component(self, marker: str) -> str:
        client = self.tool.ensure_client()
        inventory = getattr(client, "inventory", None) or {}
        if not inventory:
            load_inventory = getattr(client, "load_inventory", None)
            if callable(load_inventory):
                try:
                    inventory = load_inventory()
                except Exception:
                    inventory = {}
        for item in inventory.get("components", []):
            access_point = item.get("access_point", "")
            if marker in access_point:
                return access_point
        return ""

    def archive_policy_target(self) -> str:
        client = self.tool.ensure_client()
        inventory = getattr(client, "inventory", None) or {}
        if not inventory:
            load_inventory = getattr(client, "load_inventory", None)
            if callable(load_inventory):
                try:
                    inventory = load_inventory()
                except Exception:
                    inventory = {}
        for collection in ("cameras", "archives"):
            for item in inventory.get(collection, []):
                for field in ("uid", "access_point", "accessPoint"):
                    value = item.get(field)
                    if isinstance(value, str) and value:
                        return value
        return ""

    def operator_registry(self) -> Any:
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        client = self.tool.ensure_client()
        return OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(client),
            host=f"hosts/{self.args.tls_cn}",
            enabled=True,
        )

    def apply_verify_rollback(self, registry: Any, workflow: str, params: dict[str, Any]) -> dict[str, Any]:
        plan = registry.plan(workflow, params)
        if plan.get("status") == "gap":
            return plan
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        verified = registry.verify(plan["plan_id"])
        rolled_back = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        rollback_verified = registry.verify(plan["plan_id"])
        return {
            "status": "ok" if applied.get("status") == "applied" and rolled_back.get("status") == "rolled_back" else "error",
            "plan": plan,
            "apply": applied,
            "verify": verified,
            "rollback": rolled_back,
            "rollback_verify": rollback_verified,
        }

    def run_mutation(self) -> None:
        registry = self.operator_registry()
        video_source_ap = self.video_source_ap()
        if not video_source_ap:
            self.record(
                "mutation_av_detector",
                lambda: self.fixture_needed("create_av_detector_full", "No video SourceEndpoint fixture was discovered."),
            )
            self.record(
                "mutation_appdata_detector",
                lambda: self.fixture_needed("create_appdata_detector_full", "No video SourceEndpoint fixture was discovered."),
            )
            self.record("mutation_archive_policy", lambda: self.mutate_archive_policy(registry))
            self.context["operator_audit_log"] = registry.audit_log()
            return
        self.record("mutation_av_detector", lambda: self.mutate_av_detector(registry, video_source_ap))
        self.record("mutation_appdata_detector", lambda: self.mutate_appdata_detector(registry, video_source_ap))
        self.record("mutation_archive_policy", lambda: self.mutate_archive_policy(registry))
        self.context["operator_audit_log"] = registry.audit_log()

    def mutate_av_detector(self, registry: Any, video_source_ap: str) -> dict[str, Any]:
        name = f"codex-detector-archive-av-{uuid.uuid4().hex[:8]}"
        plan = registry.plan(
            "create_av_detector_full",
            {"display_name": name, "video_source_ap": video_source_ap, "detector": "MotionDetection"},
        )
        if plan.get("status") == "gap":
            return plan
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        verified = registry.verify(plan["plan_id"])
        created_uid = (applied.get("created_uids") or [""])[0]
        update_result: dict[str, Any] = self.fixture_needed(
            "update_detector_parameters",
            "No writable scalar parameter was discovered.",
        )
        visual_result: dict[str, Any] = self.fixture_needed(
            "update_detector_visual_element",
            "No writable visual element child was discovered.",
        )
        try:
            if created_uid:
                client = registry.ensure_client()
                units = client.read_unit(created_uid).get("units") or []
                unit = units[0] if units else {}
                scalar_change = detector_scalar_change(list(unit.get("properties") or []))
                if scalar_change:
                    update_result = self.apply_verify_rollback(
                        registry,
                        "update_detector_parameters",
                        {"uid": created_uid, "properties": [scalar_change]},
                    )
                for child in iter_units(unit):
                    visual_change = visual_element_change(child)
                    child_uid = str(child.get("uid") or "")
                    if visual_change and child_uid and child_uid != created_uid:
                        visual_result = self.apply_verify_rollback(
                            registry,
                            "update_detector_visual_element",
                            {"uid": child_uid, "properties": [visual_change]},
                        )
                        break
        finally:
            rolled_back = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
            rollback_verified = registry.verify(plan["plan_id"])
        return {
            "status": "ok" if applied.get("status") == "applied" and rolled_back.get("status") == "rolled_back" else "error",
            "create": {"plan": plan, "apply": applied, "verify": verified},
            "scalar_update": update_result,
            "visual_update": visual_result,
            "rollback": rolled_back,
            "rollback_verify": rollback_verified,
        }

    def mutate_appdata_detector(self, registry: Any, video_source_ap: str) -> dict[str, Any]:
        name = f"codex-detector-archive-appdata-{uuid.uuid4().hex[:8]}"
        params = {
            "display_name": name,
            "video_source_ap": video_source_ap,
            "vmda_source_ap": self.vmda_source_ap(),
            "detector": "MoveInZone",
        }
        return self.apply_verify_rollback(registry, "create_appdata_detector_full", params)

    def mutate_archive_policy(self, registry: Any) -> dict[str, Any]:
        uid = self.args.archive_policy_fixture_uid
        if not uid or "codex-" not in uid:
            return self.fixture_needed(
                "archive_policy_update",
                "No isolated codex archive/camera fixture was supplied; real archive policy update skipped.",
            )
        client = self.tool.ensure_client()
        descriptor, source = _archive_policy_descriptor(client, uid)
        if descriptor is None:
            return self.fixture_needed("archive_policy_update", "The supplied codex archive policy fixture was not resolvable.")
        policy = self.tool.archive_policy_get(uid)
        prop = first_policy_noop_property(policy)
        if prop is None:
            return self.fixture_needed(
                "archive_policy_update",
                "The supplied codex archive policy fixture did not expose a writable scalar policy property.",
            )
        result = self.apply_verify_rollback(
            registry,
            "archive_policy_update",
            {"uid": uid, "descriptor": descriptor, "properties": [prop]},
        )
        result["descriptor_source"] = source
        return result

    def run_archive_maintenance_noop(self) -> None:
        registry = self.operator_registry()
        self.record("archive_maintenance_noop", lambda: self.archive_maintenance_noop(registry))
        self.context["operator_audit_log"] = registry.audit_log()

    def archive_maintenance_noop(self, registry: Any) -> dict[str, Any]:
        access_point = self.args.archive_access_point or (self.context.get("archive_management_status") or {}).get("archive_access_point")
        if not access_point:
            return self.fixture_needed("archive_maintenance_noop", "No archive access point fixture was discovered.")
        volume_id = f"{self.args.noop_volume_prefix}{uuid.uuid4()}"
        results = []
        for workflow in ("archive_format_volume", "archive_reindex", "archive_cancel_reindex"):
            plan = registry.plan(workflow, {"access_point": access_point, "volume_ids": [volume_id]})
            if plan.get("status") == "gap":
                results.append({"workflow": workflow, "plan": plan})
                continue
            applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
            verified = registry.verify(plan["plan_id"])
            results.append({"workflow": workflow, "plan": plan, "apply": applied, "verify": verified})
            if workflow == "archive_reindex":
                results[-1]["rollback"] = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        failed = [item for item in results if (item.get("apply") or {}).get("status") not in ("applied", None)]
        return {
            "status": "ok" if not failed else "error",
            "access_point": access_point,
            "noop_volume_id_prefix": self.args.noop_volume_prefix,
            "noop_volume_id_len": len(volume_id),
            "results": results,
        }

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "host": self.args.host,
                "grpc_target": f"{self.args.host}:{self.args.grpc_port}",
                "http_url": self.args.http_url,
                "username": self.args.username,
                "password": "<redacted>" if self.args.password else "",
                "tls_cn": self.args.tls_cn,
            },
            "modes": {
                "read_only": True,
                "mutation": bool(self.args.mutation),
                "archive_maintenance_noop": bool(self.args.archive_maintenance_noop),
            },
            "defaults": {
                "metadata_sample_limit": self.args.metadata_sample_limit,
                "metadata_sample_timeout": self.args.metadata_sample_timeout,
                "noop_volume_prefix": self.args.noop_volume_prefix,
            },
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
            "operator_audit_log": sanitize_evidence(self.context.get("operator_audit_log", []), self.host),
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        paths = report_paths(self.args.report_dir, stamp)
        clean = sanitize_evidence(report, self.host)
        json_text = json.dumps(clean, indent=2, ensure_ascii=True, default=str) + "\n"
        paths["json"].write_text(json_text, encoding="utf-8")
        paths["latest_json"].write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(clean)
        paths["md"].write_text(md_text, encoding="utf-8")
        paths["latest_md"].write_text(md_text, encoding="utf-8")
        print(f"JSON report: {paths['json']}")
        print(f"Markdown report: {paths['md']}")
        print(f"Latest markdown: {paths['latest_md']}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Detector Archive Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{report['target']['grpc_target']}`",
            f"- HTTP target: `{report['target']['http_url']}`",
            f"- Mutation: `{report['modes']['mutation']}`",
            f"- Archive maintenance no-op: `{report['modes']['archive_maintenance_noop']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            note = self.note_for(result).replace("|", "\\|")[:240]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        evidence = result.get("evidence") or {}
        if isinstance(evidence, dict):
            if evidence.get("message"):
                return str(evidence["message"])
            if evidence.get("error_type"):
                return f"{evidence.get('error_type')}: {evidence.get('message', '')}"
            if evidence.get("tool"):
                return f"tool={evidence['tool']} keys={sorted(evidence.keys())}"
            return f"keys={sorted(evidence.keys())}"
        return str(evidence)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = DetectorArchiveSmoke(args).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
