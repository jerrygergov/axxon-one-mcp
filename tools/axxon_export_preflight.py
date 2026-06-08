#!/usr/bin/env python3
"""Read-only preflight for export sessions, settings, and required fixtures."""

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


EXPORT_MUTATIONS_REQUIRING_APPROVAL = [
    {
        "rpc": "ExportService.StartSession",
        "risk": "creates an export job and may write result files",
        "requirement": "short archived interval, export-agent target if needed, byte limit, and cleanup plan",
    },
    {
        "rpc": "ExportService.DownloadFile",
        "risk": "downloads generated export bytes",
        "requirement": "known file id from a codex export session and strict byte/chunk cap",
    },
    {
        "rpc": "ExportService.StopSession",
        "risk": "changes export job state",
        "requirement": "only for a session created by this workflow",
    },
    {
        "rpc": "ExportService.DestroySession",
        "risk": "removes export session and generated results",
        "requirement": "only for a codex session id captured by this workflow",
    },
    {
        "rpc": "DomainSettingsService.UpdateExportSettings",
        "risk": "changes domain-wide export defaults",
        "requirement": "settings etag snapshot and explicit rollback",
    },
]


def export_agent_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(items),
        "access_point_lengths": sorted(len(str(item.get("access_point", ""))) for item in items),
        "display_name_lengths": sorted(len(str(item.get("display_name", ""))) for item in items),
    }


class ExportPreflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        inventory = self.client.load_inventory()
        camera = next((item for item in inventory.get("cameras", []) if item.get("access_point")), {})
        self.fixtures["camera_ap"] = camera.get("access_point", "")
        self.fixtures["camera_legacy_ap"] = self.fixtures["camera_ap"].removeprefix("hosts/")
        self.fixtures["archive_ap"] = self.client.archive_access_point()
        self.fixtures["export_agents"] = self.export_like_components(inventory.get("components", [])) + self.export_agent_units()

    def export_like_components(self, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in components if "export" in json.dumps(item).casefold()]

    def export_agent_units(self) -> list[dict[str, Any]]:
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/config/ConfigurationService.proto", "ConfigurationService")
        response = stub.ListUnits(pb2.ListUnitsRequest(unit_uids=["hosts/Server"], display_mode=0), timeout=self.args.timeout)
        agents = []
        for unit in self.client.message_to_dict(response).get("units", []):
            for child in unit.get("units", []):
                if child.get("type") == "MMExportAgent":
                    agents.append(child)
        return agents

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.list_sessions())
        self.results.append(self.get_export_settings())
        self.results.append(self.discover_fixtures())
        self.results.append(
            {
                "group": "approval_only_mutations",
                "status": "WARN",
                "elapsed_ms": 0,
                "details": {"not_executed": EXPORT_MUTATIONS_REQUIRING_APPROVAL},
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def export_stub_and_pb2(self) -> tuple[Any, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.mmexport.ExportService_pb2")
        return self.client.stub_from_proto("axxonsoft/bl/mmexport/ExportService.proto", "ExportService"), pb2

    def list_sessions(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.export_stub_and_pb2()
            request = pb2.ListSessionsRequest(page_size=100)
            pages = 0
            sessions = 0
            states: Counter[str] = Counter()
            for page in stub.ListSessions(request, timeout=self.args.timeout):
                pages += 1
                data = self.client.message_to_dict(page)
                sessions += len(data.get("sessions", []))
                for session in data.get("sessions", []):
                    state = session.get("state", {}).get("state", "S_NONE")
                    states[state] += 1
                if pages >= self.args.max_session_pages:
                    break
            return self.result("list_sessions", "PASS", {"pages": pages, "session_count": sessions, "states": dict(states)}, start)
        except Exception as exc:
            return self.exception_result("list_sessions", exc, start)

    def get_export_settings(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            pb2 = self.client.import_module("axxonsoft.bl.settings.DomainSettingsService_pb2")
            stub = self.client.stub_from_proto("axxonsoft/bl/settings/DomainSettingsService.proto", "DomainSettingsService")
            data = self.client.message_to_dict(stub.GetExportSettings(pb2.GetExportSettingsRequest(), timeout=self.args.timeout))
            settings = data.get("settings", {})
            details = {
                "etag_len": len(str(data.get("etag", ""))),
                "settings_shape": self.client.shape(settings),
                "options_shape": self.client.shape(settings.get("options", {})),
            }
            return self.result("get_export_settings", "PASS", details, start)
        except Exception as exc:
            return self.exception_result("get_export_settings", exc, start)

    def discover_fixtures(self) -> dict[str, Any]:
        start = time.perf_counter()
        details = {
            "export_agents": export_agent_summary(self.fixtures.get("export_agents", [])),
            "camera_ap_len": len(self.fixtures.get("camera_ap", "")),
            "archive_ap_len": len(self.fixtures.get("archive_ap", "")),
            "archive_interval_available": False,
        }
        try:
            self.client.authenticate_http_grpc()
            begin, end = self.client.archive_time_range_legacy(hours=self.args.hours)
            response = self.client.http_request(
                "GET",
                f"/archive/contents/intervals/{self.fixtures['camera_legacy_ap']}/{end}/{begin}",
                bearer=True,
                max_items=1,
            )
            intervals = response.get("body", {}).get("intervals", []) if response.get("status") == 200 else []
            details["archive_interval_available"] = bool(intervals)
            details["interval_count_sampled"] = len(intervals)
            details["interval_read_status"] = response.get("status")
        except Exception as exc:
            details["interval_error_type"] = exc.__class__.__name__
            details["interval_error"] = str(exc)[:300]
        status = "PASS" if details["archive_interval_available"] else "WARN"
        if details["export_agents"]["count"] == 0:
            status = "WARN"
            details["fixture_gap"] = "no export-agent component found"
        return self.result("fixture_preflight", status, details, start)

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
            "fixtures": {
                "camera_ap_len": len(self.fixtures.get("camera_ap", "")),
                "archive_ap_len": len(self.fixtures.get("archive_ap", "")),
                "export_agent_count": len(self.fixtures.get("export_agents", [])),
            },
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"export-preflight-{stamp}.json"
        md_path = self.args.report_dir / f"export-preflight-{stamp}.md"
        latest_json = self.args.report_dir / "export-preflight-latest.json"
        latest_md = self.args.report_dir / "export-preflight-latest.md"
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
            "# Axxon One Export Preflight",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Read-only preflight for export workflows. It does not start export sessions, download files, stop sessions, destroy sessions, or update export settings.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            note = self.note_for(result).replace("|", "\\|")[:220]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        details = result.get("details", {})
        if details.get("error"):
            return details["error"]
        if result["group"] == "list_sessions":
            return f"pages={details.get('pages')} sessions={details.get('session_count')} states={details.get('states')}"
        if result["group"] == "get_export_settings":
            return f"etag_len={details.get('etag_len')} options_keys={details.get('options_shape', {}).get('type', details.get('options_shape'))}"
        if result["group"] == "fixture_preflight":
            return f"export_agents={details.get('export_agents', {}).get('count')} archive_interval={details.get('archive_interval_available')} gap={details.get('fixture_gap', '')}"
        if result["group"] == "approval_only_mutations":
            return ", ".join(item["rpc"] for item in details.get("not_executed", []))
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--max-session-pages", type=int, default=2)
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    preflight = ExportPreflight(parse_args())
    report = preflight.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
