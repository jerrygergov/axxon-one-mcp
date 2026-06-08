#!/usr/bin/env python3
"""Compare auth modes for selected legacy Axxon HTTP read endpoints."""

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


def probe_endpoints() -> list[dict[str, str]]:
    return [
        {"group": "server", "name": "hosts", "path": "/hosts/"},
        {"group": "server", "name": "product_version", "path": "/product/version"},
        {"group": "server", "name": "webserver_statistics", "path": "/statistics/webserver"},
        {"group": "server", "name": "hardware_statistics", "path": "/statistics/hardware"},
        {"group": "macros", "name": "legacy_macro_list", "path": "/macro/list/"},
        {"group": "macros", "name": "legacy_macro_list_exclude_auto", "path": "/macro/list/?exclude_auto"},
        {"group": "macros", "name": "v1_logic_macros", "path": "/v1/logic_service/macros"},
    ]


class LegacyAuthProbe:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []

    def selected_endpoints(self) -> list[dict[str, str]]:
        endpoints = probe_endpoints()
        if not self.args.group:
            return endpoints
        wanted = set(self.args.group)
        return [endpoint for endpoint in endpoints if endpoint["group"] in wanted]

    def setup(self) -> None:
        if not self.args.no_bearer:
            try:
                self.client.authenticate_http_grpc()
            except Exception as exc:
                self.results.append(
                    {
                        "group": "auth",
                        "name": "http_grpc_bearer",
                        "auth_mode": "bearer",
                        "path": "/grpc",
                        "status": "WARN",
                        "elapsed_ms": 0,
                        "details": {"error_type": exc.__class__.__name__, "error": str(exc)[:500]},
                    }
                )

    def auth_modes(self) -> list[str]:
        modes = ["anonymous", "basic"]
        if self.client.http_token:
            modes.append("bearer")
        return modes

    def invoke(self, endpoint: dict[str, str], auth_mode: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            response = self.client.http_request(
                "GET",
                endpoint["path"],
                basic=auth_mode == "basic",
                bearer=auth_mode == "bearer",
                max_items=self.args.max_items,
                max_bytes=self.args.max_bytes,
            )
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "shape": self.client.shape(response.get("body")),
            }
            status = "PASS" if 200 <= response["status"] < 300 else "WARN"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "FAIL"
        return {
            "group": endpoint["group"],
            "name": endpoint["name"],
            "auth_mode": auth_mode,
            "path": endpoint["path"],
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for endpoint in self.selected_endpoints():
            for auth_mode in self.auth_modes():
                self.results.append(self.invoke(endpoint, auth_mode))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "selection": {"groups": self.args.group or ["server", "macros"], "auth_modes": self.auth_modes()},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"legacy-auth-probe-{stamp}.json"
        md_path = self.args.report_dir / f"legacy-auth-probe-{stamp}.md"
        latest_json = self.args.report_dir / "legacy-auth-probe-latest.json"
        latest_md = self.args.report_dir / "legacy-auth-probe-latest.md"
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
            "# Axxon One Legacy HTTP Auth Probe",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Auth modes: `{', '.join(report['selection']['auth_modes'])}`",
            "",
            "Read-only endpoint comparison for anonymous, Basic, and HTTP `/grpc` Bearer auth. Tokens and credentials are not written to this report.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Auth | Endpoint | ms | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}".replace("|", "\\|")
            if result["status"] == "FAIL":
                note = details.get("error", "")
            lines.append(f"| {result['status']} | `{result['auth_mode']}` | `GET {result['path']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--group", action="append", choices=sorted({endpoint["group"] for endpoint in probe_endpoints()}))
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--max-bytes", type=int, default=200000)
    parser.add_argument("--no-bearer", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    report = LegacyAuthProbe(parse_args()).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
