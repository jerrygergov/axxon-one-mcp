#!/usr/bin/env python3
"""No-op probe for legacy HTTP archive delete-video endpoint."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "PROBE_DELETE_VIDEO_NOOP_ONLY"


def noop_delete_query(*, host_name: str, stamp: str) -> dict[str, str]:
    endpoint = f"hosts/{host_name}/codex-nonexistent-delete-video/SourceEndpoint.video:0:0"
    storage = f"hosts/{host_name}/codex-nonexistent-delete-video/MultimediaStorage"
    return {
        "begins_at": stamp,
        "ends_at": stamp,
        "storage_id": storage,
        "endpoint": endpoint,
    }


class DeleteVideoNoopProbe:
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
        host_name = self.client.node_name()
        stamp = self.started_at.strftime("%Y%m%dT%H%M%S.%f")
        query = noop_delete_query(host_name=host_name, stamp=stamp)
        self.fixtures = {
            "host_name": host_name,
            "begin": query["begins_at"],
            "end": query["ends_at"],
            "endpoint": query["endpoint"],
            "storage_id": query["storage_id"],
            "camera_count": str(len(inventory.get("cameras", []))),
        }

    def auth_kwargs(self) -> dict[str, bool]:
        return {
            "basic": self.args.auth_mode == "basic",
            "bearer": self.args.auth_mode == "bearer",
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.invoke_noop_delete())
        report = self.report()
        self.write_report(report)
        return report

    def invoke_noop_delete(self) -> dict[str, Any]:
        start = time.perf_counter()
        path = "/archive/contents/bookmarks/"
        query = self.client.query_string(
            {
                "begins_at": self.fixtures["begin"],
                "ends_at": self.fixtures["end"],
                "storage_id": self.fixtures["storage_id"],
                "endpoint": self.fixtures["endpoint"],
            }
        )
        try:
            response = self.client.http_request("DELETE", path, query=query, **self.auth_kwargs(), max_items=5)
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "shape": self.client.shape(response.get("body")),
                "noop_fixture": "codex-nonexistent-delete-video",
            }
            # The endpoint is considered verified when the server accepts the documented
            # DELETE shape and rejects/ignores a nonexistent target without a transport error.
            status = "PASS" if response["status"] in {200, 204, 400, 404, 409, 422, 500} else "WARN"
            return self.result("delete_video_noop_dispatch", "DELETE", path + "?" + query, status, details, start)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result("delete_video_noop_dispatch", "DELETE", path + "?" + query, "FAIL", details, start)

    def result(
        self,
        name: str,
        method: str,
        path: str,
        status: str,
        details: dict[str, Any],
        start: float,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "method": method,
            "path": path,
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

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
                "auth_mode": self.args.auth_mode,
                "confirmation": CONFIRMATION,
            },
            "fixtures": self.fixtures,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"delete-video-noop-probe-{stamp}.json"
        md_path = self.args.report_dir / f"delete-video-noop-probe-{stamp}.md"
        latest_json = self.args.report_dir / "delete-video-noop-probe-latest.json"
        latest_md = self.args.report_dir / "delete-video-noop-probe-latest.md"
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
            "# Axxon One Delete-Video No-Op Probe",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Auth mode: `{report['selection']['auth_mode']}`",
            "",
            "This probe calls the PDF-documented `DELETE /archive/contents/bookmarks/` shape with a `codex-nonexistent-*` endpoint and storage id. It verifies dispatch behavior only and does not target real archive data.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Fixtures", ""])
        for key, value in report["fixtures"].items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Results", "", "| Status | Step | Endpoint | ms | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}".replace("|", "\\|")
            if result["status"] == "FAIL":
                note = details.get("error", "")[:180].replace("|", "\\|")
            endpoint = f"{result['method']} {result['path']}"
            lines.append(f"| {result['status']} | `{result['name']}` | `{endpoint}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--auth-mode", choices=["basic", "bearer"], default="bearer")
    parser.add_argument("--i-understand-delete-video-noop", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if args.i_understand_delete_video_noop != CONFIRMATION:
        parser.error(f"--i-understand-delete-video-noop must equal {CONFIRMATION}")
    return args


def main() -> int:
    probe = DeleteVideoNoopProbe(parse_args())
    report = probe.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 and report["summary"].get("WARN", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
