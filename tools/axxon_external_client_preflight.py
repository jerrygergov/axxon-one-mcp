#!/usr/bin/env python3
"""Read-only preflight for Axxon Client HTTP and embeddable component fixtures."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import socket
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


EXTERNAL_CLIENT_MUTATIONS_REQUIRING_APPROVAL = [
    {"operation": "ClientHTTP.SwitchLayout", "risk": "changes operator display state", "requirement": "capture current layout/display and restore"},
    {"operation": "ClientHTTP.AddCameraToDisplay", "risk": "changes operator display composition", "requirement": "isolated display and remove/restore step"},
    {"operation": "ClientHTTP.RemoveCameraFromDisplay", "risk": "changes operator display composition", "requirement": "restore original display camera set"},
    {"operation": "ClientHTTP.SetArchiveMode", "risk": "changes playback/live mode in client UI", "requirement": "capture and restore previous mode"},
    {"operation": "ClientHTTP.SetSearchMode", "risk": "changes client UI search mode", "requirement": "capture and restore previous mode"},
    {"operation": "ClientHTTP.SetImmersionMode", "risk": "changes client UI state", "requirement": "capture and restore previous mode"},
    {"operation": "EmbeddableComponent.BrowserRender", "risk": "may expose operator/session visual data", "requirement": "sanitized screenshot policy and no credential persistence"},
]


def component_host_signature(*, status: int, content_type: str, size: int, text_prefix: str, path: str = "/") -> dict[str, Any]:
    lowered = text_prefix.casefold()
    path_lowered = path.casefold()
    return {
        "path": path,
        "http_status": status,
        "content_type": content_type,
        "bytes": size,
        "text_prefix_len": len(text_prefix),
        "mentions_component": "component" in lowered or path_lowered.endswith("embedded.html"),
        "mentions_video": "video" in lowered,
        "mentions_embed": "embed" in lowered or "iframe" in lowered or "embedded.js" in lowered,
    }


class ExternalClientPreflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        self.results.append(self.client_http_targets())
        self.results.append(self.embeddable_host())
        self.results.append(
            {
                "group": "approval_only_operations",
                "status": "WARN",
                "elapsed_ms": 0,
                "details": {"not_executed": EXTERNAL_CLIENT_MUTATIONS_REQUIRING_APPROVAL},
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def client_http_targets(self) -> dict[str, Any]:
        start = time.perf_counter()
        targets = [
            {"host": "127.0.0.1", "port": self.args.client_http_port, "purpose": "local Axxon Client HTTP API"},
            {"host": self.args.host, "port": self.args.client_http_port, "purpose": "remote host Client HTTP API"},
        ]
        checks = [self.socket_probe(item["host"], item["port"], item["purpose"]) for item in targets]
        reachable = [item for item in checks if item["reachable"]]
        status = "PASS" if reachable else "WARN"
        details = {
            "reachable_count": len(reachable),
            "checks": checks,
            "fixture_gap": "" if reachable else "no Axxon Client HTTP API target reachable",
        }
        return self.result("client_http_targets", status, details, start)

    def socket_probe(self, host: str, port: int, purpose: str) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=self.args.socket_timeout):
                return {"host": host, "port": port, "purpose": purpose, "reachable": True, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
        except OSError as exc:
            return {
                "host": host,
                "port": port,
                "purpose": purpose,
                "reachable": False,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "error_type": exc.__class__.__name__,
            }

    def embeddable_host(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            checks = []
            for path in ["/embedded.html", "/embedded.js", "/"]:
                response = self.client.http_request("GET", path, raw_body=True, max_bytes=self.args.max_root_bytes)
                body = response.get("body", {})
                text_prefix = str(body.get("text_prefix", ""))
                checks.append(
                    component_host_signature(
                        path=path,
                        status=int(response.get("status", 0)),
                        content_type=str(response.get("content_type", "")),
                        size=int(response.get("size", 0)),
                        text_prefix=text_prefix,
                    )
                )
            html_check = next((c for c in checks if c["path"] == "/embedded.html"), None)
            js_check = next((c for c in checks if c["path"] == "/embedded.js"), None)
            signature = next(
                (
                    item
                    for item in checks
                    if item["http_status"] == 200 and item["mentions_component"] and (item["mentions_video"] or item["mentions_embed"])
                ),
                checks[0],
            )
            looks_like_host = bool(
                signature["http_status"] == 200
                and signature["mentions_component"]
                and (signature["mentions_video"] or signature["mentions_embed"])
            )
            # Bonus signal: both the PDF entrypoint AND its companion script asset must serve OK
            both_assets_present = bool(
                html_check and js_check
                and html_check["http_status"] == 200
                and js_check["http_status"] == 200
                and js_check["bytes"] > 0
            )
            details = {
                "url": self.args.http_url,
                "signature": signature,
                "checks": checks,
                "both_assets_present": both_assets_present,
                "fixture_gap": "" if (looks_like_host and both_assets_present) else "web root, /embedded.html, and /embedded.js do not all look like an embeddable component host",
            }
            return self.result("embeddable_host", "PASS" if (looks_like_host and both_assets_present) else "WARN", details, start)
        except Exception as exc:
            return self.exception_result("embeddable_host", exc, start)

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
            "target": {"http_url": self.args.http_url, "host": self.args.host, "client_http_port": self.args.client_http_port, "username": self.args.username, "password": "<redacted>"},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"external-client-preflight-{stamp}.json"
        md_path = self.args.report_dir / f"external-client-preflight-{stamp}.md"
        latest_json = self.args.report_dir / "external-client-preflight-latest.json"
        latest_md = self.args.report_dir / "external-client-preflight-latest.md"
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
            "# Axxon One External Client Preflight",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Client HTTP port: `{self.args.client_http_port}`",
            "",
            "Read-only preflight for Axxon Client HTTP and embeddable component fixtures. It does not switch layouts, alter displays, change modes, render browser screenshots, or persist browser/session artifacts.",
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
        if result["group"] == "client_http_targets":
            return f"reachable={details.get('reachable_count')} gap={details.get('fixture_gap', '')}"
        if result["group"] == "embeddable_host":
            sig = details.get("signature", {})
            return f"path={sig.get('path')} http={sig.get('http_status')} bytes={sig.get('bytes')} component={sig.get('mentions_component')} video={sig.get('mentions_video')} embed={sig.get('mentions_embed')} gap={details.get('fixture_gap', '')}"
        if result["group"] == "approval_only_operations":
            return ", ".join(item["operation"] for item in details.get("not_executed", []))
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--client-http-port", type=int, default=8888)
    parser.add_argument("--socket-timeout", type=float, default=2.0)
    parser.add_argument("--max-root-bytes", type=int, default=65536)
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    preflight = ExternalClientPreflight(parse_args())
    report = preflight.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
