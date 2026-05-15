#!/usr/bin/env python3
"""Controlled Axxon One ChangeConfig mutation smoke tests with rollback."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def mutation_groups() -> list[str]:
    return ["archive", "camera", "av_detector", "av_detector_parameters", "appdata_detector", "appdata_visual_element"]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == "CONFIRM-config-mutation-smoke")


def prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        out["properties"] = properties
    return out


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def prop_int(prop_id: str, value: int) -> dict[str, Any]:
    return {"id": prop_id, "value_int32": value}


def detector_scalar_change(properties: list[dict[str, Any]]) -> dict[str, Any]:
    preferred = ["plateProbMin", "period", "enabled", "onlyKeyFrames", "FrameScale", "deviceType"]
    writable = [
        prop
        for prop in properties
        if not prop.get("readonly") and not prop.get("internal") and prop.get("id") != "display_name"
    ]
    by_id = {prop.get("id"): prop for prop in writable}
    for prop_id in preferred:
        if prop_id in by_id:
            change = changed_scalar_property(by_id[prop_id])
            if change:
                return change
    for prop in writable:
        change = changed_scalar_property(prop)
        if change:
            return change
    raise RuntimeError("no writable scalar detector parameter found")


def changed_scalar_property(prop: dict[str, Any]) -> dict[str, Any] | None:
    prop_id = prop.get("id")
    if not prop_id:
        return None
    if "value_bool" in prop:
        return {"id": prop_id, "value_bool": not bool(prop.get("value_bool"))}
    if "value_int32" in prop:
        current = int(prop.get("value_int32", 0))
        bounds = prop.get("range_constraint", {})
        minimum = int(bounds.get("min_int", 0))
        maximum = int(bounds.get("max_int", max(current + 1, minimum + 1)))
        value = current + 1 if current + 1 <= maximum else minimum
        if value == current and minimum <= maximum:
            value = maximum if current != maximum else minimum
        return {"id": prop_id, "value_int32": value}
    if "value_string" in prop and prop.get("enum_constraint", {}).get("items"):
        current = prop.get("value_string", "")
        for item in prop["enum_constraint"]["items"]:
            candidate = item.get("value_string", "")
            if candidate and candidate != current:
                return {"id": prop_id, "value_string": candidate}
    return None


def visual_element_parameter_change(unit: dict[str, Any]) -> dict[str, Any]:
    for prop in unit.get("properties", []):
        if prop.get("readonly") or prop.get("internal"):
            continue
        if "value_rectangle" in prop:
            old = prop.get("value_rectangle", {})
            return {
                "id": prop.get("id"),
                "value_rectangle": {
                    "x": 0.21,
                    "y": 0.41,
                    "w": 0.58,
                    "h": 0.88,
                    "index": int(old.get("index", 0)),
                },
            }
        if "value_simple_polygon" in prop:
            return {
                "id": prop.get("id"),
                "value_simple_polygon": {
                    "points": [
                        {"x": 0.15, "y": 0.15},
                        {"x": 0.15, "y": 0.85},
                        {"x": 0.85, "y": 0.85},
                        {"x": 0.85, "y": 0.15},
                    ]
                },
            }
    raise RuntimeError("no writable visual element parameter found")


def no_visual_parameter_summary(owner_type: str) -> dict[str, str]:
    return {"visual_owner_type": owner_type, "visual_skipped": "no VisualElement child"}


class ConfigMutationSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_uids: list[str] = []

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_http_grpc()

    def selected_groups(self) -> list[str]:
        if not self.args.group:
            return mutation_groups()
        wanted = set(self.args.group)
        return [group for group in mutation_groups() if group in wanted]

    def change_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeConfig", payload)
        if response.get("status") != 200:
            raise RuntimeError(f"ChangeConfig HTTP status {response.get('status')}")
        return response.get("body") or {}

    def ensure_success(self, stage: str, body: dict[str, Any]) -> None:
        if body.get("failed"):
            raise RuntimeError(f"{stage} failed: {self.client.sanitize(body.get('failed_reason', []))}")

    def add_under_host(self, unit_type: str, properties: list[dict[str, Any]]) -> dict[str, Any]:
        body = self.change_config({"added": [{"uid": f"hosts/{self.args.tls_cn}", "units": [{"type": unit_type, "properties": properties, "units": []}]}]})
        self.ensure_success("add", body)
        for uid in body.get("added", []):
            self.created_uids.append(uid)
        return body

    def change_unit(self, uid: str, unit_type: str, properties: list[dict[str, Any]]) -> dict[str, Any]:
        body = self.change_config({"changed": [{"uid": uid, "type": unit_type, "properties": properties, "units": []}]})
        self.ensure_success("change", body)
        return body

    def remove_unit(self, uid: str) -> dict[str, Any]:
        body = self.change_config({"removed": [{"uid": uid}]})
        self.ensure_success("remove", body)
        if uid in self.created_uids:
            self.created_uids.remove(uid)
        return body

    def run_archive(self) -> dict[str, Any]:
        name = f"codex-temp-archive-{self.short_stamp()}"
        added = self.add_under_host(
            "MultimediaStorage",
            [prop_string("display_name", name), prop_string("color", "Gray"), prop_string("storage_type", "object"), prop_int("day_depth", 0)],
        )
        uid = added["added"][0]
        changed = self.change_unit(uid, "MultimediaStorage", [prop_string("display_name", name + "-changed")])
        removed = self.remove_unit(uid)
        return {"added": added.get("added", []), "changed_failed": len(changed.get("failed", [])), "removed_failed": len(removed.get("failed", []))}

    def run_camera(self) -> dict[str, Any]:
        name = f"codex-temp-camera-{self.short_stamp()}"
        display_id = "9" + self.short_stamp()[-3:]
        added = self.add_under_host(
            "DeviceIpint",
            [
                prop_string("vendor", "Virtual", properties=[prop_string("model", "Virtual several streams", properties=[])]),
                prop_string("display_name", name, properties=[]),
                prop_bool("blockingConfiguration", False),
                prop_string("display_id", display_id, properties=[]),
            ],
        )
        uid = added["added"][0]
        changed = self.change_unit(uid, "DeviceIpint", [prop_string("display_name", name + "-changed")])
        removed = self.remove_unit(uid)
        return {"added": added.get("added", []), "display_id": display_id, "changed_failed": len(changed.get("failed", [])), "removed_failed": len(removed.get("failed", []))}

    def av_detector_properties(self, detector: str, name: str) -> list[dict[str, Any]]:
        source = self.args.video_source_ap
        return [
            prop_string("display_name", name),
            prop_string(
                "input",
                "Video",
                properties=[
                    prop_string("camera_ref", source, properties=[prop_string("streaming_id", source)]),
                    prop_string("detector", detector),
                ],
            ),
        ]

    def run_av_detector(self) -> dict[str, Any]:
        created: list[str] = []
        for detector in ["SceneDescription", "MotionDetection", "NeuroTracker"]:
            name = f"codex-temp-{detector}-{self.short_stamp()}"
            added = self.add_under_host("AVDetector", self.av_detector_properties(detector, name))
            uid = added["added"][0]
            created.append(uid)
            self.change_unit(uid, "AVDetector", [prop_string("display_name", name + "-changed")])
            self.remove_unit(uid)
        return {"created_and_removed": created}

    def run_av_detector_parameters(self) -> dict[str, Any]:
        name = f"codex-temp-MotionDetection-params-{self.short_stamp()}"
        added = self.add_under_host("AVDetector", self.av_detector_properties("MotionDetection", name))
        uid = added["added"][0]
        try:
            before = self.read_unit(uid)["units"][0]
            scalar_change = detector_scalar_change(before.get("properties", []))
            scalar_body = self.change_unit(uid, "AVDetector", [scalar_change])
            after_scalar = self.read_unit(uid)["units"][0]
            scalar_readback = self.property_value(after_scalar, scalar_change["id"], next(key for key in scalar_change if key.startswith("value_")))

            visual_summary = self.change_optional_visual_parameter(uid, "AVDetector")
            removed = self.remove_unit(uid)
            if visual_summary.get("visual_skipped"):
                visual_summary.update(self.change_appdata_visual_parameter())
            return {
                "added": added.get("added", []),
                "scalar_parameter": scalar_change["id"],
                "scalar_value_key": next(key for key in scalar_change if key.startswith("value_")),
                "scalar_readback": scalar_readback,
                "scalar_changed_failed": len(scalar_body.get("failed", [])),
                **visual_summary,
                "removed_failed": len(removed.get("failed", [])),
            }
        finally:
            if uid in self.created_uids:
                self.remove_unit(uid)

    def change_optional_visual_parameter(self, uid: str, owner_type: str) -> dict[str, Any]:
        try:
            visual_before = self.visual_element_child(uid)
        except RuntimeError:
            return no_visual_parameter_summary(owner_type)
        visual_change = visual_element_parameter_change(visual_before)
        visual_body = self.change_config({"changed": [{"uid": visual_before["uid"], "type": "VisualElement", "properties": [visual_change]}]})
        self.ensure_success("change visual element", visual_body)
        visual_after = self.visual_element_child(uid)
        visual_value_key = next(key for key in visual_change if key.startswith("value_"))
        visual_readback = self.property_value(visual_after, visual_change["id"], visual_value_key)
        return {
            "visual_owner_type": owner_type,
            "visual_element_uid": visual_before["uid"],
            "visual_parameter": visual_change["id"],
            "visual_value_key": visual_value_key,
            "visual_readback_present": visual_readback is not None,
            "visual_changed_failed": len(visual_body.get("failed", [])),
        }

    def change_appdata_visual_parameter(self) -> dict[str, Any]:
        name = f"codex-temp-visual-fallback-{self.short_stamp()}"
        added = self.add_under_host("AppDataDetector", self.appdata_properties(name))
        uid = added["added"][0]
        try:
            visual_before = self.visual_element_child(uid)
            visual_change = {
                "id": "polyline",
                "value_simple_polygon": {
                    "points": [
                        {"x": 0.12, "y": 0.12},
                        {"x": 0.12, "y": 0.88},
                        {"x": 0.88, "y": 0.88},
                        {"x": 0.88, "y": 0.12},
                    ]
                },
            }
            visual_body = self.change_config({"changed": [{"uid": visual_before["uid"], "type": "VisualElement", "properties": [visual_change]}]})
            self.ensure_success("change AppDataDetector visual element", visual_body)
            visual_after = self.visual_element_child(uid)
            visual_value_key = next(key for key in visual_change if key.startswith("value_"))
            visual_readback = self.property_value(visual_after, visual_change["id"], visual_value_key)
            return {
                "fallback_visual_added": added.get("added", []),
                "fallback_visual_owner_type": "AppDataDetector",
                "visual_element_uid": visual_before["uid"],
                "visual_parameter": visual_change["id"],
                "visual_value_key": visual_value_key,
                "visual_readback_present": visual_readback is not None,
                "visual_changed_failed": len(visual_body.get("failed", [])),
            }
        finally:
            self.remove_unit(uid)

    def appdata_properties(self, name: str) -> list[dict[str, Any]]:
        return [
            prop_string("display_name", name),
            prop_string(
                "input",
                "TargetList",
                properties=[
                    prop_string("camera_ref", self.args.video_source_ap, properties=[prop_string("streaming_id", self.args.vmda_source_ap)]),
                    prop_string("detector", "MoveInZone"),
                ],
            ),
        ]

    def run_appdata_detector(self) -> dict[str, Any]:
        name = f"codex-temp-MoveInZone-{self.short_stamp()}"
        added = self.add_under_host("AppDataDetector", self.appdata_properties(name))
        uid = added["added"][0]
        event_supplier = uid + "/EventSupplier"
        self.change_unit(uid, "AppDataDetector", [prop_string("display_name", name + "-changed"), prop_bool("enabled", True)])
        readback = self.read_by_access_point(event_supplier)
        time.sleep(max(0, self.args.event_wait_seconds))
        event_summary = self.count_detector_events(event_supplier)
        self.remove_unit(uid)
        return {
            "added": added.get("added", []),
            "event_supplier": event_supplier,
            "readback_units": len(readback.get("units", [])),
            "event_summary": event_summary,
        }

    def run_appdata_visual_element(self) -> dict[str, Any]:
        name = f"codex-temp-visual-{self.short_stamp()}"
        added = self.add_under_host("AppDataDetector", self.appdata_properties(name))
        uid = added["added"][0]
        try:
            visual_element = self.visual_element_child(uid)
            polygon = {
                "points": [
                    {"x": 0.10, "y": 0.10},
                    {"x": 0.10, "y": 0.90},
                    {"x": 0.90, "y": 0.90},
                    {"x": 0.90, "y": 0.10},
                ]
            }
            body = self.change_config(
                {
                    "changed": [
                        {
                            "uid": visual_element["uid"],
                            "type": "VisualElement",
                            "properties": [{"id": "polyline", "value_simple_polygon": polygon}],
                        }
                    ]
                }
            )
            self.ensure_success("change visual element", body)
            readback = self.visual_element_child(uid)
            readback_polygon = self.property_value(readback, "polyline", "value_simple_polygon")
            return {
                "added": added.get("added", []),
                "visual_element_uid": visual_element["uid"],
                "changed_failed": len(body.get("failed", [])),
                "readback_points": len((readback_polygon or {}).get("points", [])),
            }
        finally:
            self.remove_unit(uid)

    def read_by_access_point(self, access_point: str) -> dict[str, Any]:
        self.client.authenticate_grpc()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        response = self.client.common_stubs()["config"].ListUnitsByAccessPoints(
            pb2.ListUnitsByAccessPointsRequest(access_points=[access_point], display_mode=3),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def read_unit(self, uid: str) -> dict[str, Any]:
        self.client.authenticate_grpc()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        response = self.client.common_stubs()["config"].ListUnits(
            pb2.ListUnitsRequest(unit_uids=[uid], display_mode=0),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def visual_element_child(self, uid: str) -> dict[str, Any]:
        data = self.read_unit(uid)
        units = data.get("units", [])
        if not units:
            raise RuntimeError(f"unit not found after add: {uid}")
        for child in units[0].get("units", []):
            if child.get("type") == "VisualElement":
                return child
        raise RuntimeError(f"no VisualElement child found for {uid}")

    def property_value(self, unit: dict[str, Any], prop_id: str, value_key: str) -> Any:
        for prop in unit.get("properties", []):
            if prop.get("id") == prop_id:
                return prop.get(value_key)
        return None

    def count_detector_events(self, subject: str) -> dict[str, Any]:
        event_history_pb2 = self.client.import_module("axxonsoft.bl.events.EventHistory_pb2")
        events_pb2 = self.client.import_module("axxonsoft.bl.events.Events_pb2")
        primitive_pb2 = self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
        end = dt.datetime.now(dt.UTC)
        begin = end - dt.timedelta(minutes=self.args.event_window_minutes)
        request = event_history_pb2.ReadCountRequest(
            range=primitive_pb2.TimeRange(begin_time=self.axxon_ts(begin), end_time=self.axxon_ts(end)),
            node_description=event_history_pb2.NodeDescription(node_name=self.client.node_name()),
            filters=event_history_pb2.SearchFilterArray(
                filters=[event_history_pb2.SearchFilter(type=int(events_pb2.ET_DetectorEvent), subjects=[subject])]
            ),
        )
        total = 0
        pages = 0
        for page in stub.ReadCount(request, timeout=self.args.timeout):
            pages += 1
            total += int(getattr(page, "count", 0))
        return {"subject": subject, "minutes": self.args.event_window_minutes, "pages": pages, "count": total}

    def short_stamp(self) -> str:
        return dt.datetime.now(dt.UTC).strftime("%H%M%S")

    def axxon_ts(self, value: dt.datetime) -> str:
        return value.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S.%f")

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        for uid in list(reversed(self.created_uids)):
            try:
                body = self.remove_unit(uid)
                cleanup_results.append({"uid": uid, "status": "removed", "failed": len(body.get("failed", []))})
            except Exception as exc:
                cleanup_results.append({"uid": uid, "status": "cleanup_failed", "error": str(exc)[:400]})
        return cleanup_results

    def invoke(self, group: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            details = getattr(self, f"run_{group}")()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "FAIL"
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def run(self) -> dict[str, Any]:
        self.setup()
        try:
            for group in self.selected_groups():
                self.results.append(self.invoke(group))
        finally:
            cleanup_results = self.cleanup()
            if cleanup_results:
                self.results.append({"group": "cleanup", "status": "WARN", "elapsed_ms": 0, "details": {"cleanup": cleanup_results}})
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "selection": {"groups": self.selected_groups()},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"config-mutation-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"config-mutation-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "config-mutation-smoke-latest.json"
        latest_md = self.args.report_dir / "config-mutation-smoke-latest.md"
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
            "# Axxon One ChangeConfig Mutation Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "All created objects use `codex-temp-*` names and are removed before the tool exits.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {self.note_for(result).replace('|', '\\|')[:220]} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        details = result.get("details", {})
        if details.get("error"):
            return details["error"]
        if result["group"] == "appdata_detector":
            summary = details.get("event_summary", {})
            return f"added={details.get('added')} readback={details.get('readback_units')} events={summary.get('count')} subject={summary.get('subject')}"
        if result["group"] == "appdata_visual_element":
            return f"added={details.get('added')} visual_element={details.get('visual_element_uid')} readback_points={details.get('readback_points')}"
        if result["group"] == "av_detector_parameters":
            return f"added={details.get('added')} scalar={details.get('scalar_parameter')} visual={details.get('visual_parameter')} visual_readback={details.get('visual_readback_present')}"
        if "added" in details:
            return f"added={details.get('added')} changed_failed={details.get('changed_failed')} removed_failed={details.get('removed_failed')}"
        if "created_and_removed" in details:
            return f"created_and_removed={details.get('created_and_removed')}"
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--group", action="append", choices=mutation_groups())
    parser.add_argument("--video-source-ap", default="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
    parser.add_argument("--vmda-source-ap", default="hosts/Server/AVDetector.1/SourceEndpoint.vmda")
    parser.add_argument("--event-wait-seconds", type=float, default=3.0)
    parser.add_argument("--event-window-minutes", type=float, default=3.0)
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not mutation_approved(args):
        parser.error("--i-understand-this-mutates and --confirm CONFIRM-config-mutation-smoke are required")
    return args


def main() -> int:
    smoke = ConfigMutationSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
