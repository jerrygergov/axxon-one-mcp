#!/usr/bin/env python3
"""Controlled legacy HTTP export lifecycle smoke for Axxon One."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any
import urllib.parse

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


HTTP_EXPORT_CONFIRMATION = "CONFIRM-http-export-smoke"


class HttpExportSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, str] = {}

    def setup(self) -> None:
        self.client.authenticate_http_grpc()
        inventory = self.client.load_inventory()
        camera = next((item for item in inventory.get("cameras", []) if item.get("access_point")), {})
        camera_ap = self.args.camera_ap or camera.get("access_point", "")
        self.fixtures = {
            "camera_ap": camera_ap,
            "camera_legacy_ap": camera_ap.removeprefix("hosts/"),
            "archive_ap": self.client.archive_access_point(),
        }
        self.fixtures["archive_timestamp"] = self.resolve_archive_timestamp()

    def resolve_archive_timestamp(self) -> str:
        begin, end = self.client.archive_time_range_legacy(hours=self.args.hours)
        response = self.client.http_request(
            "GET",
            f"/archive/contents/intervals/{self.fixtures['camera_legacy_ap']}/{end}/{begin}",
            bearer=True,
            max_items=1,
        )
        intervals = response.get("body", {}).get("intervals", []) if response.get("status") == 200 else []
        if intervals:
            timestamp = intervals[-1].get("end") or intervals[-1].get("begin") or end
        else:
            timestamp = end
        return timestamp.split(".", 1)[0]

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.archive_frame_export_lifecycle())
        report = self.report()
        self.write_report(report)
        return report

    def archive_frame_export_lifecycle(self) -> dict[str, Any]:
        start = time.perf_counter()
        export_id = ""
        deleted = False
        try:
            timestamp = self.fixtures["archive_timestamp"]
            path = f"/export/archive/{self.fixtures['camera_legacy_ap']}/{timestamp}/{timestamp}"
            query = urllib.parse.urlencode(
                {
                    "waittimeout": str(self.args.waittimeout_ms),
                    "archive": self.fixtures["archive_ap"],
                }
            )
            response = self.client.http_request(
                "POST",
                path,
                {"format": "jpg", "comment": "codex-http-export-smoke", "maxfilesize": self.args.max_file_size},
                bearer=True,
                query=query,
            )
            location = response.get("headers", {}).get("Location", "")
            export_id = location.rstrip("/").split("/")[-1] if location else ""
            status_body = self.poll_status(export_id) if export_id else {}
            files = status_body.get("files", []) if isinstance(status_body, dict) else []
            download = self.download_file(export_id, files[0]) if files else {}
            delete_response = self.client.http_request("DELETE", f"/export/{export_id}", bearer=True) if export_id else {}
            deleted = delete_response.get("status") == 204
            status = "PASS" if response.get("status") == 202 and status_body.get("state") == 2 and download.get("status") == 200 and deleted else "WARN"
            return self.result(
                "archive_frame_export_lifecycle",
                status,
                {
                    "start_status": response.get("status"),
                    "location_present": bool(location),
                    "export_id_len": len(export_id),
                    "state": status_body.get("state"),
                    "progress": status_body.get("progress"),
                    "file_count": len(files),
                    "download": download,
                    "deleted": deleted,
                },
                start,
            )
        except Exception as exc:
            return self.exception_result("archive_frame_export_lifecycle", exc, start, export_id_len=len(export_id), deleted=deleted)
        finally:
            if export_id and not deleted:
                self.try_delete(export_id)

    def poll_status(self, export_id: str) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for _ in range(self.args.poll_attempts):
            response = self.client.http_request("GET", f"/export/{export_id}/status", bearer=True, max_items=5)
            body = response.get("body", {})
            last = body if isinstance(body, dict) else {}
            if response.get("status") == 200 and last.get("state") in (2, 3, 4, 5, 6):
                return last
            time.sleep(self.args.poll_delay)
        return last

    def download_file(self, export_id: str, name: str) -> dict[str, Any]:
        response = self.client.http_request(
            "GET",
            f"/export/{export_id}/file",
            bearer=True,
            query=urllib.parse.urlencode({"name": name}),
            raw_body=True,
            max_bytes=self.args.max_download_bytes,
        )
        body = response.get("body", {})
        return {
            "status": response.get("status"),
            "content_type": response.get("content_type", ""),
            "bytes": response.get("size", 0),
            "sha256": body.get("sha256", "") if isinstance(body, dict) else "",
        }

    def try_delete(self, export_id: str) -> None:
        try:
            self.client.http_request("DELETE", f"/export/{export_id}", bearer=True)
        except Exception:
            pass

    def result(self, group: str, status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def exception_result(self, group: str, exc: Exception, start: float, **extra: Any) -> dict[str, Any]:
        details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800], **extra}
        if self.args.verbose:
            details["traceback"] = traceback.format_exc()
        return self.result(group, "FAIL", details, start)

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "selection": {
                "hours": self.args.hours,
                "waittimeout_ms": self.args.waittimeout_ms,
                "poll_attempts": self.args.poll_attempts,
                "max_download_bytes": self.args.max_download_bytes,
            },
            "fixtures": self.fixtures,
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"http-export-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"http-export-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "http-export-smoke-latest.json"
        latest_md = self.args.report_dir / "http-export-smoke-latest.md"
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
            "# Axxon One Legacy HTTP Export Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Starts one temporary one-frame JPEG export through legacy HTTP `/export`, downloads only a bounded file prefix, and deletes the export id.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Fixtures", ""])
        for key, value in report["fixtures"].items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            download = details.get("download", {})
            note = (
                f"start={details.get('start_status')} state={details.get('state')} files={details.get('file_count')} "
                f"download={download.get('status')}/{download.get('bytes')} deleted={details.get('deleted')}"
            )
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--camera-ap", default="")
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument("--waittimeout-ms", type=int, default=30000)
    parser.add_argument("--poll-attempts", type=int, default=20)
    parser.add_argument("--poll-delay", type=float, default=1.0)
    parser.add_argument("--max-download-bytes", type=int, default=262144)
    parser.add_argument("--max-file-size", type=int, default=1048576)
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not args.i_understand_this_mutates:
        parser.error("--i-understand-this-mutates is required because this tool starts and deletes a legacy HTTP export")
    if args.confirm != HTTP_EXPORT_CONFIRMATION:
        parser.error(f"--confirm must equal {HTTP_EXPORT_CONFIRMATION}")
    return args


if __name__ == "__main__":
    report = HttpExportSmoke(parse_args()).run()
    raise SystemExit(1 if report["summary"]["FAIL"] else 0)
