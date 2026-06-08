#!/usr/bin/env python3
"""Sweep safe legacy Axxon One HTTP API read endpoints."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def safe_endpoint_groups() -> list[dict[str, Any]]:
    return [
        {
            "name": "server",
            "checks": [
                {"name": "hosts", "method": "GET", "path": "/hosts/"},
                {"name": "product_version", "method": "GET", "path": "/product/version"},
                {"name": "webserver_statistics", "method": "GET", "path": "/statistics/webserver"},
                {"name": "hardware_statistics", "method": "GET", "path": "/statistics/hardware"},
            ],
        },
        {
            "name": "camera_inventory",
            "checks": [
                {"name": "camera_list", "method": "GET", "path": "/camera/list"},
                {"name": "camera_list_filtered", "method": "GET", "path": "/camera/list?filter={camera_legacy_ap}"},
                {"name": "camera_detectors", "method": "GET", "path": "/detectors/{camera_device}"},
                {"name": "camera_statistics", "method": "GET", "path": "/statistics/{camera_legacy_ap}"},
            ],
        },
        {
            "name": "archive_read",
            "checks": [
                {"name": "archive_list", "method": "GET", "path": "/archive/list/{camera_legacy_ap}"},
                {
                    "name": "archive_intervals",
                    "method": "GET",
                    "path": "/archive/contents/intervals/{camera_legacy_ap}/{end}/{begin}",
                },
                {
                    "name": "archive_frames",
                    "method": "GET",
                    "path": "/archive/contents/frames/{camera_legacy_ap}/{end}/{begin}?limit=3",
                },
                {"name": "archive_depth", "method": "GET", "path": "/archive/statistics/depth/{camera_legacy_ap}"},
                {
                    "name": "archive_capacity",
                    "method": "GET",
                    "path": "/archive/statistics/capacity/{camera_legacy_ap}/{end}/{begin}",
                },
                {"name": "archive_calendar", "method": "GET", "path": "/archive/calendar/{camera_legacy_ap}/{begin}/{end}"},
            ],
        },
        {
            "name": "events_read",
            "checks": [
                {"name": "audit_events", "method": "GET", "path": "/audit/{host_name}/{end}/{begin}?filter=17-20,6,1:4"},
                {"name": "detector_events", "method": "GET", "path": "/archive/events/detectors/{end}/{begin}"},
                {
                    "name": "camera_detector_events",
                    "method": "GET",
                    "path": "/archive/events/detectors/{camera_legacy_ap}/{end}/{begin}",
                },
                {"name": "alerts", "method": "GET", "path": "/archive/events/alerts/{end}/{begin}?limit=50&offset=0"},
                {
                    "name": "host_alerts",
                    "method": "GET",
                    "path": "/archive/events/alerts/{host_name}/{end}/{begin}?limit=50&offset=0",
                },
            ],
        },
        {
            "name": "macros_read",
            "checks": [
                {"name": "macro_list", "method": "GET", "path": "/macro/list/"},
                {"name": "macro_list_exclude_auto", "method": "GET", "path": "/macro/list/?exclude_auto"},
            ],
        },
    ]


class LegacyHttpSweep:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, str] = {}

    def setup(self) -> None:
        if self.args.auth_mode == "bearer":
            self.client.authenticate_http_grpc()
        inventory = self.client.load_inventory()
        self.fixtures = self.build_fixtures(inventory)

    def build_fixtures(self, inventory: dict[str, Any]) -> dict[str, str]:
        camera = self.choose_camera(inventory.get("cameras", []))
        camera_ap = camera.get("access_point", "")
        begin, end = self.client.archive_time_range_legacy(hours=self.args.hours)
        return {
            "host_name": self.client.node_name(),
            "camera_ap": camera_ap,
            "camera_legacy_ap": camera_ap.removeprefix("hosts/"),
            "camera_device": self.camera_device(camera_ap, inventory.get("components", [])),
            "archive_ap": self.safe_fixture(self.client.archive_access_point),
            "begin": begin,
            "end": end,
        }

    def choose_camera(self, cameras: list[dict[str, Any]]) -> dict[str, Any]:
        preferred_names = {"Tracker", "Face", "LPR + MMR", "Traffic Analyzer RR 1"}
        for camera in cameras:
            if camera.get("display_name") in preferred_names and camera.get("access_point"):
                return camera
        return next((camera for camera in cameras if camera.get("access_point")), {})

    def camera_device(self, camera_ap: str, components: list[dict[str, Any]]) -> str:
        for component in components:
            access_point = component.get("access_point", "")
            if camera_ap and access_point.startswith(camera_ap):
                return self.device_from_access_point(access_point)
        return self.device_from_access_point(camera_ap)

    def device_from_access_point(self, access_point: str) -> str:
        parts = access_point.split("/")
        if len(parts) >= 3 and parts[0] == "hosts":
            return "/".join(parts[1:3])
        return access_point.removeprefix("hosts/")

    def safe_fixture(self, func: Any) -> str:
        try:
            return str(func())
        except Exception:
            return ""

    def selected_groups(self) -> list[dict[str, Any]]:
        groups = safe_endpoint_groups()
        if not self.args.group:
            return groups
        wanted = set(self.args.group)
        return [group for group in groups if group["name"] in wanted]

    def render_path(self, path: str) -> str:
        return path.format(**self.fixtures)

    def invoke(self, group: str, check: dict[str, str]) -> dict[str, Any]:
        start = time.perf_counter()
        path = self.render_path(check["path"])
        if "{}" in path or path.endswith("//"):
            return self.result(group, check, path, "WARN", {"reason": "missing fixture"}, start)
        try:
            response = self.client.http_request(
                check["method"],
                path,
                basic=self.args.auth_mode == "basic",
                bearer=self.args.auth_mode == "bearer",
                max_items=self.args.max_items,
            )
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "shape": self.client.shape(response.get("body")),
            }
            status = "PASS" if 200 <= response["status"] < 300 else "WARN"
            return self.result(group, check, path, status, details, start)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(group, check, path, "FAIL", details, start)

    def result(
        self,
        group: str,
        check: dict[str, str],
        path: str,
        status: str,
        details: dict[str, Any],
        start: float,
    ) -> dict[str, Any]:
        return {
            "group": group,
            "name": check["name"],
            "method": check["method"],
            "path": path,
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for group in self.selected_groups():
            for check in group["checks"]:
                self.results.append(self.invoke(group["name"], check))
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
            "target": {
                "http_url": self.args.http_url,
                "username": self.args.username,
                "password": "<redacted>",
            },
            "selection": {
                "groups": [group["name"] for group in self.selected_groups()],
                "timeout_seconds": self.args.timeout,
                "hours": self.args.hours,
                "auth_mode": self.args.auth_mode,
            },
            "fixtures": {
                "camera_ap": self.fixtures.get("camera_ap", ""),
                "camera_legacy_ap": self.fixtures.get("camera_legacy_ap", ""),
                "camera_device": self.fixtures.get("camera_device", ""),
                "host_name": self.fixtures.get("host_name", ""),
                "archive_ap": self.fixtures.get("archive_ap", ""),
                "begin": self.fixtures.get("begin", ""),
                "end": self.fixtures.get("end", ""),
            },
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"legacy-http-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"legacy-http-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "legacy-http-sweep-latest.json"
        latest_md = self.args.report_dir / "legacy-http-sweep-latest.md"
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
            "# Axxon One Legacy HTTP Read Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Groups: `{', '.join(report['selection']['groups'])}`",
            f"- Auth mode: `{report['selection']['auth_mode']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Fixtures", ""])
        for key, value in report["fixtures"].items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Results", "", "| Status | Group | Endpoint | ms | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}".replace("|", "\\|")
            if result["status"] == "FAIL":
                note = details.get("error", "")[:180].replace("|", "\\|")
            endpoint = f"{result['method']} {result['path']}"
            lines.append(f"| {result['status']} | `{result['group']}` | `{endpoint}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--group", action="append", help="Limit to one endpoint group. Can be repeated.")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--auth-mode", choices=["anonymous", "basic", "bearer"], default="basic")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    sweep = LegacyHttpSweep(parse_args())
    report = sweep.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
