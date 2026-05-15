#!/usr/bin/env python3
"""Read-only preflight for PTZ telemetry and Tag&Track fixtures."""

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


PTZ_MUTATIONS_REQUIRING_APPROVAL = [
    {"rpc": "TelemetryService.AcquireSessionId", "risk": "opens a PTZ control session", "requirement": "non-production PTZ camera and release-session rollback"},
    {"rpc": "TelemetryService.Move", "risk": "moves camera continuously", "requirement": "known safe scene and stop/home rollback"},
    {"rpc": "TelemetryService.Zoom", "risk": "changes camera zoom", "requirement": "known safe scene and home preset rollback"},
    {"rpc": "TelemetryService.AbsoluteMove", "risk": "moves camera to absolute coordinates", "requirement": "known home position and bounded coordinates"},
    {"rpc": "TelemetryService.GoPreset", "risk": "moves camera to a preset", "requirement": "known non-production preset"},
    {"rpc": "TelemetryService.SetPreset", "risk": "changes preset state", "requirement": "codex preset label and cleanup"},
    {"rpc": "TelemetryService.PlayTour", "risk": "starts a PTZ tour", "requirement": "test tour and stop rollback"},
    {"rpc": "TelemetryService.PerformAuxiliaryOperation", "risk": "runs device-specific PTZ auxiliary operation", "requirement": "operator approval for named operation"},
    {"rpc": "TagAndTrackService.SetMode", "risk": "changes Tag&Track mode", "requirement": "capture original mode and restore"},
    {"rpc": "TagAndTrackService.FollowTrack", "risk": "commands PTZ tracking", "requirement": "known test track and stop/restore plan"},
    {"rpc": "TagAndTrackService.MoveToCoords", "risk": "moves PTZ by image coordinates", "requirement": "non-production camera and bounded coordinates"},
]


def telemetry_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(items),
        "access_point_lengths": sorted(len(str(item.get("access_point", ""))) for item in items),
        "display_name_lengths": sorted(len(str(item.get("display_name", ""))) for item in items),
    }


class PtzPreflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        inventory = self.client.load_inventory()
        self.fixtures["telemetry_items"] = self.telemetry_like_components(inventory.get("components", []), inventory.get("cameras", []))
        self.fixtures["telemetry_ap"] = self.fixtures["telemetry_items"][0].get("access_point", "") if self.fixtures["telemetry_items"] else ""

    def telemetry_like_components(self, components: list[dict[str, Any]], cameras: list[dict[str, Any]]) -> list[dict[str, Any]]:
        found = [
            item for item in components
            if "/Telemetry" in item.get("access_point", "") or "telemetry" in json.dumps(item).casefold()
        ]
        for camera in cameras:
            for ptz in camera.get("ptzs", []):
                if ptz.get("access_point"):
                    found.append(ptz)
        dedup: dict[str, dict[str, Any]] = {}
        for item in found:
            access_point = item.get("access_point", "")
            if access_point:
                dedup[access_point] = item
        return list(dedup.values())

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.discover_fixtures())
        self.results.append(self.read_control_panels())
        self.results.append(self.read_telemetry_if_available())
        self.results.append(
            {
                "group": "approval_only_mutations",
                "status": "WARN",
                "elapsed_ms": 0,
                "details": {"not_executed": PTZ_MUTATIONS_REQUIRING_APPROVAL},
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def discover_fixtures(self) -> dict[str, Any]:
        start = time.perf_counter()
        details = {"telemetry": telemetry_summary(self.fixtures.get("telemetry_items", []))}
        status = "PASS" if details["telemetry"]["count"] else "WARN"
        if status == "WARN":
            details["fixture_gap"] = "no telemetry/PTZ access point found"
        return self.result("ptz_fixture_discovery", status, details, start)

    def read_control_panels(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            pb2 = self.client.import_module("axxonsoft.bl.domain.Domain_pb2")
            domain = self.client.common_stubs()["domain"]
            items: list[dict[str, Any]] = []
            for page in domain.ListControlPanels(pb2.ListControlPanelsRequest(page_size=50), timeout=self.args.timeout):
                items.extend(self.client.message_to_dict(page).get("items", []))
                if len(items) >= 50:
                    break
            status = "PASS" if items else "WARN"
            details = {"control_panel_count": len(items), "shape": self.client.shape(items[:1])}
            if not items:
                details["fixture_gap"] = "no control panels found"
            return self.result("control_panel_discovery", status, details, start)
        except Exception as exc:
            return self.exception_result("control_panel_discovery", exc, start)

    def read_telemetry_if_available(self) -> dict[str, Any]:
        start = time.perf_counter()
        access_point = self.fixtures.get("telemetry_ap", "")
        if not access_point:
            return self.result("telemetry_read_preflight", "WARN", {"skipped": "no telemetry access point"}, start)
        try:
            pb2 = self.client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
            stub = self.client.stub_from_proto("axxonsoft/bl/ptz/Telemetry.proto", "TelemetryService")
            tag_pb2 = self.client.import_module("axxonsoft.bl.ptz.TagAndTrack_pb2")
            tag_stub = self.client.stub_from_proto("axxonsoft/bl/ptz/TagAndTrack.proto", "TagAndTrackService")
            availability = self.client.message_to_dict(stub.IsSessionAvailable(pb2.IsSessionAvailableRequest(access_point=access_point), timeout=self.args.timeout))
            position = self.client.message_to_dict(stub.GetPositionInformation(pb2.GetPositionInformationRequest(access_point=access_point), timeout=self.args.timeout))
            presets = self.client.message_to_dict(stub.GetPresetsInfo(pb2.GetPresetsInfoRequest(access_point=access_point), timeout=self.args.timeout))
            operations = self.client.message_to_dict(stub.GetAuxiliaryOperations(pb2.GetAuxiliaryOperationsRequest(access_point=access_point), timeout=self.args.timeout))
            tours = self.client.message_to_dict(stub.GetTours(pb2.GetToursRequest(access_point=access_point), timeout=self.args.timeout))
            trackers = self.client.message_to_dict(tag_stub.ListTrackers(tag_pb2.ListTnTTrackersRequest(access_point=access_point), timeout=self.args.timeout))
            details = {
                "telemetry_ap_len": len(access_point),
                "is_available": availability.get("is_available"),
                "position_shape": self.client.shape(position),
                "preset_count": len(presets.get("preset_info", [])),
                "operation_count": len(operations.get("operations", [])),
                "tour_count": len(tours.get("tours", [])),
                "tag_track_mode": trackers.get("mode", ""),
                "tag_track_tracker_count": len(trackers.get("trackers", [])),
            }
            return self.result("telemetry_read_preflight", "PASS", details, start)
        except Exception as exc:
            return self.exception_result("telemetry_read_preflight", exc, start)

    def result(self, group: str, status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def exception_result(self, group: str, exc: Exception, start: float) -> dict[str, Any]:
        details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
        if self.args.verbose:
            details["traceback"] = traceback.format_exc()
        return self.result(group, "FAIL", details, start)

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "fixtures": {"telemetry_count": len(self.fixtures.get("telemetry_items", [])), "telemetry_ap_len": len(self.fixtures.get("telemetry_ap", ""))},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"ptz-preflight-{stamp}.json"
        md_path = self.args.report_dir / f"ptz-preflight-{stamp}.md"
        latest_json = self.args.report_dir / "ptz-preflight-latest.json"
        latest_md = self.args.report_dir / "ptz-preflight-latest.md"
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
            "# Axxon One PTZ Preflight",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Read-only preflight for PTZ and Tag&Track workflows. It does not acquire sessions, move cameras, change presets, play tours, or change Tag&Track mode.",
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
        if result["group"] == "ptz_fixture_discovery":
            return f"telemetry={details.get('telemetry', {}).get('count')} gap={details.get('fixture_gap', '')}"
        if result["group"] == "control_panel_discovery":
            return f"control_panels={details.get('control_panel_count')} gap={details.get('fixture_gap', '')}"
        if result["group"] == "telemetry_read_preflight":
            return f"skipped={details.get('skipped', '')} presets={details.get('preset_count')} operations={details.get('operation_count')} trackers={details.get('tag_track_tracker_count')}"
        if result["group"] == "approval_only_mutations":
            return ", ".join(item["rpc"] for item in details.get("not_executed", []))
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    preflight = PtzPreflight(parse_args())
    report = preflight.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
