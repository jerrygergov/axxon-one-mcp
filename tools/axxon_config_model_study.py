#!/usr/bin/env python3
"""Read-only Axxon One configuration object model and mutation-shape study."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def study_groups() -> list[str]:
    return ["domain", "unit_tree", "factories", "properties", "similar_units", "appdata_detectors"]


def sensitive_property_tokens() -> set[str]:
    return {"password", "token", "license", "serial", "certificate", "private_key", "secret"}


def descriptor_value_kind(item: dict[str, Any]) -> str:
    for key in item:
        if key.startswith("value_") or key == "string_list_value":
            return key
    return ""


def access_point_family(access_point: str) -> str:
    parts = [part for part in access_point.split("/") if part]
    if len(parts) >= 3 and parts[0] == "hosts":
        return parts[2].split(".")[0]
    if len(parts) >= 2 and parts[0] == "hosts":
        return parts[1]
    return parts[0].split(".")[0] if parts else ""


def unit_sort_key(unit: dict[str, Any]) -> tuple[int, int, str]:
    display_id = str(unit.get("display_id", ""))
    if display_id.isdigit():
        return (0, int(display_id), str(unit.get("uid", "")))
    digits = "".join(ch for ch in display_id if ch.isdigit())
    if digits:
        return (1, int(digits), str(unit.get("uid", "")))
    return (2, 0, str(unit.get("uid", "")))


def compact_property_descriptor(item: dict[str, Any]) -> dict[str, Any]:
    prop_id = str(item.get("id", ""))
    lower = prop_id.lower()
    redacted = any(token in lower for token in sensitive_property_tokens())
    out: dict[str, Any] = {
        "id": prop_id,
        "name": item.get("name", ""),
        "type": item.get("type", ""),
        "readonly": bool(item.get("readonly", False)),
        "internal": bool(item.get("internal", False)),
        "value_kind": descriptor_value_kind(item),
    }
    if item.get("category"):
        out["category"] = item.get("category")
    if redacted:
        out["value"] = "<redacted>"
    else:
        value_key = out["value_kind"]
        if value_key and value_key in item and not isinstance(item[value_key], (dict, list)):
            out["value"] = item[value_key]
        if "display_value" in item:
            out["display_value_present"] = True
    if "range_constraint" in item:
        out["constraint"] = "range"
    if "enum_constraint" in item:
        out["constraint"] = "enum"
        out["enum_items"] = len(item.get("enum_constraint", {}).get("items", []))
    if item.get("properties"):
        out["nested_properties"] = len(item.get("properties", []))
    return out


def compact_unit_descriptor(item: dict[str, Any], *, include_properties: bool = False, include_children: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "uid": item.get("uid", ""),
        "display_id": item.get("display_id", ""),
        "type": item.get("type", ""),
        "display_name": item.get("display_name", ""),
        "access_point": item.get("access_point", ""),
        "status": item.get("status", ""),
        "stripped": bool(item.get("stripped", False)),
        "properties_count": len(item.get("properties", [])),
        "traits_count": len(item.get("traits", [])),
        "child_units_count": len(item.get("units", [])),
        "factory_count": len(item.get("factory", [])),
        "opaque_params_count": len(item.get("opaque_params", [])),
        "assigned_templates_count": len(item.get("assigned_templates", [])),
        "has_config_etag": bool(item.get("config_etag")),
    }
    if item.get("config_name"):
        out["config_name"] = item.get("config_name")
    if include_properties:
        out["writable_properties"] = [
            compact_property_descriptor(prop)
            for prop in item.get("properties", [])
            if not prop.get("readonly") and not prop.get("internal")
        ][:40]
        out["readonly_properties"] = [
            compact_property_descriptor(prop)
            for prop in item.get("properties", [])
            if prop.get("readonly") and not prop.get("internal")
        ][:20]
    if include_children:
        out["child_units"] = [
            compact_unit_descriptor(child)
            for child in item.get("units", [])
        ][:80]
        out["factory"] = [
            compact_unit_descriptor(factory, include_properties=True)
            for factory in item.get("factory", [])
        ][:80]
    return out


class ConfigModelStudy:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.inventory: dict[str, Any] = {}
        self.full_cameras: list[dict[str, Any]] = []
        self.full_archives: list[dict[str, Any]] = []
        self.components: list[dict[str, Any]] = []
        self.host_units: list[dict[str, Any]] = []
        self.unit_index: dict[str, dict[str, Any]] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.inventory = self.client.load_inventory()
        self.components = self.inventory.get("components", [])

    def selected_groups(self) -> list[str]:
        if not self.args.group:
            return study_groups()
        wanted = set(self.args.group)
        return [group for group in study_groups() if group in wanted]

    def run_domain(self) -> dict[str, Any]:
        domain_pb2 = self.client.import_module("axxonsoft.bl.domain.Domain_pb2")
        domain = self.client.common_stubs()["domain"]

        cameras: list[dict[str, Any]] = []
        for page in domain.ListCameras(
            domain_pb2.ListCamerasRequest(page_size=200, view=domain_pb2.VIEW_MODE_FULL),
            timeout=self.args.timeout,
        ):
            cameras.extend(self.client.message_to_dict(page).get("items", []))
        self.full_cameras = cameras

        archives: list[dict[str, Any]] = []
        for page in domain.ListArchives(
            domain_pb2.ListArchivesRequest(page_size=200, view=domain_pb2.VIEW_MODE_FULL),
            timeout=self.args.timeout,
        ):
            archives.extend(self.client.message_to_dict(page).get("items", []))
        self.full_archives = archives

        detector_counter: Counter[str] = Counter()
        detector_type_names: Counter[str] = Counter()
        appdata_children = 0
        av_parents = 0
        for camera in cameras:
            for detector in camera.get("detectors", []):
                ap = detector.get("access_point", "")
                detector_counter[access_point_family(ap)] += 1
                detector_type_names[detector.get("type", "")] += 1
                if "AppDataDetector" in ap:
                    appdata_children += 1
                if "AVDetector" in ap:
                    av_parents += 1

        component_prefixes: Counter[str] = Counter()
        component_types: Counter[str] = Counter()
        for item in self.components:
            ap = item.get("access_point", "")
            component_prefixes[access_point_family(ap)] += 1
            component_types[item.get("type", "")] += 1

        return {
            "nodes": len(self.inventory.get("nodes", [])),
            "cameras": len(cameras),
            "archives": len(archives),
            "components": len(self.components),
            "camera_samples": [
                {
                    "display_name": item.get("display_name", ""),
                    "access_point": item.get("access_point", ""),
                    "detectors": len(item.get("detectors", [])),
                    "streams": len(item.get("streams", [])),
                }
                for item in cameras[:8]
            ],
            "archive_samples": [
                {
                    "display_name": item.get("display_name", ""),
                    "access_point": item.get("access_point", ""),
                    "status": item.get("status", ""),
                }
                for item in archives[:8]
            ],
            "detectors_from_full_cameras": {
                "total": sum(detector_counter.values()),
                "av_parent_count": av_parents,
                "appdata_child_count": appdata_children,
                "by_access_point_family": detector_counter.most_common(20),
                "by_detector_type": detector_type_names.most_common(30),
            },
            "components_by_access_point_family": component_prefixes.most_common(30),
            "components_by_type": component_types.most_common(30),
        }

    def walk_units(self, item: dict[str, Any]) -> None:
        uid = item.get("uid", "")
        if uid:
            self.unit_index[uid] = item
        for child in item.get("units", []):
            self.walk_units(child)

    def run_unit_tree(self) -> dict[str, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.common_stubs()["config"]
        host_uid = f"hosts/{self.args.tls_cn}"
        response = stub.ListUnits(pb2.ListUnitsRequest(unit_uids=[host_uid], display_mode=0), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        self.host_units = data.get("units", [])
        self.unit_index = {}
        for unit in self.host_units:
            self.walk_units(unit)

        by_type: Counter[str] = Counter()
        by_ap_family: Counter[str] = Counter()
        writable_by_type: defaultdict[str, int] = defaultdict(int)
        factory_by_parent_type: defaultdict[str, Counter[str]] = defaultdict(Counter)
        etag_by_type: Counter[str] = Counter()
        for unit in self.unit_index.values():
            unit_type = unit.get("type", "")
            by_type[unit_type] += 1
            ap = unit.get("access_point", "")
            by_ap_family[access_point_family(ap)] += 1
            writable_by_type[unit_type] += sum(1 for prop in unit.get("properties", []) if not prop.get("readonly") and not prop.get("internal"))
            if unit.get("config_etag"):
                etag_by_type[unit_type] += 1
            for factory in unit.get("factory", []):
                factory_by_parent_type[unit_type][factory.get("type", "")] += 1

        factory_summary = []
        for parent_type, counter in sorted(factory_by_parent_type.items()):
            factory_summary.append({"parent_type": parent_type, "child_factories": counter.most_common(30)})

        return {
            "requested_host_uid": host_uid,
            "root_units": len(self.host_units),
            "total_units": len(self.unit_index),
            "not_found": data.get("not_found_objects", []),
            "unreachable": data.get("unreachable_objects", []),
            "units_by_type": by_type.most_common(80),
            "units_by_access_point_family": by_ap_family.most_common(80),
            "types_with_config_etag": etag_by_type.most_common(80),
            "writable_property_counts_by_type": sorted(writable_by_type.items(), key=lambda item: (-item[1], item[0]))[:80],
            "factory_summary": factory_summary,
            "root_samples": [compact_unit_descriptor(item, include_children=True) for item in self.host_units],
        }

    def candidate_units(self) -> list[dict[str, Any]]:
        if not self.unit_index:
            self.run_unit_tree()
        wanted = ["DeviceIpint", "VideoChannel", "MultimediaStorage", "AVDetector", "AppDataDetector"]
        candidates: list[dict[str, Any]] = []
        for wanted_type in wanted:
            match = next((unit for unit in self.unit_index.values() if unit.get("type") == wanted_type), None)
            if match:
                candidates.append(match)
        if self.host_units:
            candidates.insert(0, self.host_units[0])
        return candidates

    def run_factories(self) -> dict[str, Any]:
        if not self.unit_index:
            self.run_unit_tree()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.common_stubs()["config"]
        requests = []
        seen: set[tuple[str, str]] = set()
        for parent in self.unit_index.values():
            parent_uid = parent.get("uid", "")
            for factory in parent.get("factory", [])[:20]:
                unit_type = factory.get("type", "")
                key = (parent_uid, unit_type)
                if parent_uid and unit_type and key not in seen:
                    seen.add(key)
                    requests.append(pb2.RequestedFactory(unit_type=unit_type, parent_uid=parent_uid, ignore_possible_limits=True))
                if len(requests) >= 60:
                    break
            if len(requests) >= 60:
                break
        response = stub.BatchGetFactories(pb2.BatchGetFactoriesRequest(factories=requests), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        status_counts: Counter[str] = Counter()
        items = []
        for item in data.get("items", []):
            status_counts[item.get("status", "OK")] += 1
            factory = item.get("factory", {})
            items.append(
                {
                    "requested": item.get("requested", {}),
                    "status": item.get("status", "OK"),
                    "factory": compact_unit_descriptor(factory, include_properties=True, include_children=True) if factory else {},
                }
            )
        return {"requested": len(requests), "status_counts": status_counts.most_common(), "items": items[:60]}

    def run_properties(self) -> dict[str, Any]:
        candidates = self.candidate_units()
        return {
            "representative_units": [
                compact_unit_descriptor(unit, include_properties=True, include_children=True)
                for unit in candidates[:12]
            ]
        }

    def run_similar_units(self) -> dict[str, Any]:
        if not self.unit_index:
            self.run_unit_tree()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.common_stubs()["config"]
        samples = []
        warnings = []
        for unit_type in ["DeviceIpint", "MultimediaStorage", "AVDetector", "AppDataDetector"]:
            unit = next((item for item in self.unit_index.values() if item.get("type") == unit_type), None)
            if not unit:
                continue
            try:
                response = stub.ListSimilarUnits(
                    pb2.ListSimilarUnitsRequest(
                        uid=unit.get("uid", ""),
                        node_name=self.client.node_name(),
                        page_size=20,
                        search_mode=pb2.ListSimilarUnitsRequest.BY_UNIT_TYPE,
                    ),
                    timeout=self.args.timeout,
                )
                data = self.client.message_to_dict(response)
                samples.append({"type": unit_type, "uid": unit.get("uid", ""), "count": len(data.get("similar_units", [])), "items": data.get("similar_units", [])[:10]})
            except Exception as exc:
                warnings.append({"type": unit_type, "uid": unit.get("uid", ""), "error_type": exc.__class__.__name__, "error": str(exc)[:240]})
        return {"samples": samples, "warnings": warnings}

    def run_appdata_detectors(self) -> dict[str, Any]:
        if not self.unit_index:
            self.run_unit_tree()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.common_stubs()["config"]
        host_uid = f"hosts/{self.args.tls_cn}"
        units = sorted(
            [unit for unit in self.unit_index.values() if unit.get("type") == "AppDataDetector"],
            key=unit_sort_key,
        )
        requested_factory = pb2.RequestedFactory(unit_type="AppDataDetector", parent_uid=host_uid, ignore_possible_limits=True)
        factory_response = stub.BatchGetFactories(pb2.BatchGetFactoriesRequest(factories=[requested_factory]), timeout=self.args.timeout)
        factory_data = self.client.message_to_dict(factory_response)
        factory_items = factory_data.get("items", [])
        factory_entry = factory_items[0] if factory_items else {}
        factory = factory_entry.get("factory", {}) if isinstance(factory_entry, dict) else {}
        detector_prop = next((prop for prop in factory.get("properties", []) if prop.get("id") == "detector"), {})
        exact_ap_samples = []
        for unit in units[:5]:
            ap = unit.get("access_point", "")
            if not ap:
                continue
            try:
                readback = stub.ListUnitsByAccessPoints(
                    pb2.ListUnitsByAccessPointsRequest(access_points=[ap], display_mode=3),
                    timeout=self.args.timeout,
                )
                readback_data = self.client.message_to_dict(readback)
                returned_units = readback_data.get("units", [])
                root = returned_units[0] if returned_units else {}
                exact_ap_samples.append(
                    {
                        "access_point": ap,
                        "returned_units": len(returned_units),
                        "root_uid": root.get("uid", ""),
                        "root_type": root.get("type", ""),
                        "root_status": root.get("status", ""),
                        "writable_properties": [
                            prop.get("id", "")
                            for prop in root.get("properties", [])
                            if not prop.get("readonly") and not prop.get("internal")
                        ],
                        "total_properties": len(root.get("properties", [])),
                        "child_units_count": len(root.get("units", [])),
                    }
                )
            except Exception as exc:
                exact_ap_samples.append(
                    {
                        "access_point": ap,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc)[:240],
                    }
                )
        return {
            "host_uid": host_uid,
            "count": len(units),
            "factory_status": factory_entry.get("status", ""),
            "factory_shape": self.client.shape(factory_data),
            "factory_detector_options_count": len(detector_prop.get("enum_constraint", {}).get("items", [])),
            "factory": compact_unit_descriptor(factory, include_properties=True, include_children=True) if factory else {},
            "exact_ap_samples": exact_ap_samples,
            "units": [
                {
                    "uid": unit.get("uid", ""),
                    "display_id": unit.get("display_id", ""),
                    "display_name": unit.get("display_name", ""),
                    "access_point": unit.get("access_point", ""),
                    "config_name": unit.get("config_name", ""),
                    "status": unit.get("status", ""),
                    "enabled": next(
                        (
                            prop.get("value_bool")
                            for prop in unit.get("properties", [])
                            if prop.get("id") == "enabled"
                        ),
                        None,
                    ),
                    "detector": next(
                        (
                            prop.get("value_string")
                            for prop in unit.get("properties", [])
                            if prop.get("id") == "detector"
                        ),
                        "",
                    ),
                    "writable_properties": [
                        prop.get("id", "")
                        for prop in unit.get("properties", [])
                        if not prop.get("readonly") and not prop.get("internal")
                    ],
                    "child_units_count": len(unit.get("units", [])),
                    "visual_elements_count": sum(1 for child in unit.get("units", []) if child.get("type") == "VisualElement"),
                }
                for unit in units
            ],
        }

    def invoke(self, group: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            details = getattr(self, f"run_{group}")()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "WARN"
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def run(self) -> dict[str, Any]:
        self.setup()
        for group in self.selected_groups():
            self.results.append(self.invoke(group))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "username": self.args.username, "password": "<redacted>"},
            "selection": {"groups": self.selected_groups()},
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"config-model-study-{stamp}.json"
        md_path = self.args.report_dir / f"config-model-study-{stamp}.md"
        latest_json = self.args.report_dir / "config-model-study-latest.json"
        latest_md = self.args.report_dir / "config-model-study-latest.md"
        json_text = json.dumps(self.client.sanitize(report), indent=2, ensure_ascii=True) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        latest_json.write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(report)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Configuration Object Model Study",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "This is a read-only study. It inventories domain objects, configuration units, factories, and writable property shapes before any `ChangeConfig` mutation.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = self.note_for(result["group"], details)
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note.replace('|', '\\|')[:220]} |")
        lines.extend(["", "## Mutation Model", ""])
        lines.extend(
            [
                "- Read a full `UnitDescriptor` with `ConfigurationService.ListUnits` or `ListUnitsByAccessPoints`.",
                "- For creation, inspect the parent unit `factory` entries or call `BatchGetFactories(RequestedFactory(unit_type, parent_uid, ignore_possible_limits=true))`.",
                "- Convert only writable, non-internal property descriptors into `Property` values when building `ChangeConfigRequest.added` or `changed` units.",
                "- Use stable test names such as `codex-*`, read back the generated uid from `ChangeConfigResponse.added`, verify inventory deltas, then remove the created unit.",
                "- Do not persist credentials, tokens, serial numbers, license keys, private keys, or raw plate values in reports.",
            ]
        )
        appdata = next((result.get("details", {}) for result in report["results"] if result["group"] == "appdata_detectors"), None)
        if appdata:
            lines.extend(["", "## AppDataDetector Inventory", ""])
            lines.append(f"- Host UID: `{appdata.get('host_uid', '')}`")
            lines.append(f"- AppDataDetector units: {appdata.get('count', 0)}")
            lines.append(f"- Factory detector options: {appdata.get('factory_detector_options_count', 0)}")
            lines.append("")
            lines.extend(["| UID | Display ID | Display Name | Access Point | Detector | Enabled | Writable Props | Child Units | Visual Elements |", "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |"])
            for unit in appdata.get("units", []):
                writable = ", ".join(unit.get("writable_properties", []))
                lines.append(
                    f"| `{unit.get('uid', '')}` | `{unit.get('display_id', '')}` | {unit.get('display_name', '')} | `{unit.get('access_point', '')}` | `{unit.get('detector', '')}` | `{unit.get('enabled', '')}` | {writable.replace('|', '\\|')[:160]} | {unit.get('child_units_count', 0)} | {unit.get('visual_elements_count', 0)} |"
                )
            if appdata.get("exact_ap_samples"):
                lines.extend(["", "## Exact Access-Point Reads", ""])
                lines.extend(["| Access Point | Returned Units | Root Type | Writable Props | Total Props | Child Units |", "| --- | ---: | --- | --- | ---: | ---: |"])
                for sample in appdata.get("exact_ap_samples", []):
                    if sample.get("error"):
                        writable = f"{sample.get('error_type', '')}: {sample.get('error', '')}"
                    else:
                        writable = ", ".join(sample.get("writable_properties", []))
                    lines.append(
                        f"| `{sample.get('access_point', '')}` | {sample.get('returned_units', 0)} | `{sample.get('root_type', '')}` | {writable.replace('|', '\\|')[:160]} | {sample.get('total_properties', 0)} | {sample.get('child_units_count', 0)} |"
                    )
        lines.append("")
        return "\n".join(lines)

    def note_for(self, group: str, details: dict[str, Any]) -> str:
        if details.get("error"):
            return details["error"]
        if group == "domain":
            detectors = details.get("detectors_from_full_cameras", {})
            return f"cameras={details.get('cameras')} archives={details.get('archives')} components={details.get('components')} appdata={detectors.get('appdata_child_count')} av={detectors.get('av_parent_count')}"
        if group == "unit_tree":
            return f"total_units={details.get('total_units')} top_types={details.get('units_by_type', [])[:4]}"
        if group == "factories":
            return f"requested={details.get('requested')} statuses={details.get('status_counts')}"
        if group == "properties":
            return f"representatives={len(details.get('representative_units', []))}"
        if group == "similar_units":
            return f"samples={len(details.get('samples', []))}"
        if group == "appdata_detectors":
            return f"count={details.get('count')} factory_options={details.get('factory_detector_options_count')}"
        return f"keys={len(details)}"


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--group", action="append", choices=study_groups())
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    study = ConfigModelStudy(parse_args())
    report = study.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
