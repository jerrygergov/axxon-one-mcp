#!/usr/bin/env python3
"""Opt-in legacy HTTP bookmark create/edit/delete smoke."""

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


CONFIRMATION = "CREATE_EDIT_DELETE_TEMP_BOOKMARK"
BOOKMARK_CREATE_PATHS = ["/archive/contents/bookmarks/create", "/archive/contents/bookmarks/create/"]


def bookmark_create_payload(
    *,
    begin: str,
    end: str,
    endpoint: str,
    storage_id: str,
    comment_suffix: str,
) -> list[dict[str, Any]]:
    return [
        {
            "begins_at": begin,
            "ends_at": end,
            "comment": f"codex-bookmark-smoke-{comment_suffix}",
            "is_protected": False,
            "endpoint": endpoint,
            "storage_id": storage_id,
        }
    ]


def bookmark_delete_payload(bookmark: dict[str, Any], *, host_name: str) -> list[dict[str, Any]]:
    deleted = dict(bookmark)
    deleted["hostname"] = host_name
    deleted["endpoint"] = ""
    deleted["storage_id"] = ""
    return [deleted]


class BookmarkSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.fixtures: dict[str, str] = {}
        self.results: list[dict[str, Any]] = []
        self.created_bookmark: dict[str, Any] = {}

    def setup(self) -> None:
        if self.args.auth_mode == "bearer":
            self.client.authenticate_http_grpc()
        inventory = self.client.load_inventory()
        camera = self.choose_camera(inventory.get("cameras", []))
        camera_ap = camera.get("access_point", "")
        begin, end = self.archive_bookmark_range(camera_ap.removeprefix("hosts/"))
        self.fixtures = {
            "host_name": self.client.node_name(),
            "camera_ap": camera_ap,
            "camera_legacy_ap": camera_ap.removeprefix("hosts/"),
            "archive_ap": self.client.archive_access_point(),
            "begin": begin,
            "end": end,
            "comment_suffix": self.started_at.strftime("%Y%m%dT%H%M%S"),
        }

    def choose_camera(self, cameras: list[dict[str, Any]]) -> dict[str, Any]:
        preferred_names = {"Tracker", "Face", "LPR + MMR", "Traffic Analyzer RR 1"}
        for camera in cameras:
            if camera.get("display_name") in preferred_names and camera.get("access_point"):
                return camera
        return next((camera for camera in cameras if camera.get("access_point")), {})

    def archive_bookmark_range(self, camera_legacy_ap: str) -> tuple[str, str]:
        begin, end = self.client.archive_time_range_legacy(hours=self.args.hours)
        try:
            response = self.client.http_request(
                "GET",
                f"/archive/contents/intervals/{camera_legacy_ap}/{end}/{begin}",
                **self.auth_kwargs(),
                max_items=1,
            )
            intervals = response.get("body", {}).get("intervals", []) if response.get("status") == 200 else []
            if intervals:
                interval_end = self.parse_legacy_time(str(intervals[0].get("end", "")))
                start = interval_end - dt.timedelta(seconds=10)
                return self.format_legacy_time(start), self.format_legacy_time(interval_end)
        except Exception:
            pass
        fallback_end = self.parse_legacy_time(end)
        return self.format_legacy_time(fallback_end - dt.timedelta(seconds=10)), self.format_legacy_time(fallback_end)

    def parse_legacy_time(self, value: str) -> dt.datetime:
        return dt.datetime.strptime(value, "%Y%m%dT%H%M%S.%f").replace(tzinfo=dt.UTC)

    def format_legacy_time(self, value: dt.datetime) -> str:
        return value.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S.%f")

    def auth_kwargs(self) -> dict[str, bool]:
        return {
            "basic": self.args.auth_mode == "basic",
            "bearer": self.args.auth_mode == "bearer",
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.list_bookmarks("preflight_list"))
        self.results.append(self.create_bookmark())
        if self.created_bookmark:
            self.results.append(self.edit_bookmark())
            self.results.append(self.delete_bookmark())
            self.results.append(self.verify_deleted())
        report = self.report()
        self.write_report(report)
        return report

    def list_bookmarks(self, name: str) -> dict[str, Any]:
        start = time.perf_counter()
        path = f"/archive/contents/bookmarks/{self.fixtures['host_name']}/{self.fixtures['end']}/{self.fixtures['begin']}"
        try:
            response = self.client.http_request("GET", path, **self.auth_kwargs(), max_items=25)
            bookmarks = self.extract_bookmarks(response.get("body"))
            codex = [item for item in bookmarks if str(item.get("comment", "")).startswith("codex-")]
            details = {
                "http_status": response["status"],
                "bookmark_count": len(bookmarks),
                "codex_bookmark_count": len(codex),
            }
            status = "PASS" if 200 <= response["status"] < 300 else "WARN"
            return self.result(name, "GET", path, status, details, start)
        except Exception as exc:
            return self.exception_result(name, "GET", path, exc, start)

    def create_bookmark(self) -> dict[str, Any]:
        start = time.perf_counter()
        payload = bookmark_create_payload(
            begin=self.fixtures["begin"],
            end=self.fixtures["end"],
            endpoint=self.fixtures["camera_ap"],
            storage_id=self.fixtures["archive_ap"],
            comment_suffix=self.fixtures["comment_suffix"],
        )
        attempts: list[dict[str, Any]] = []
        try:
            response: dict[str, Any] = {}
            path = BOOKMARK_CREATE_PATHS[0]
            for candidate in BOOKMARK_CREATE_PATHS:
                path = candidate
                response = self.client.http_request("POST", candidate, payload, **self.auth_kwargs(), max_items=25)
                attempts.append({"path": candidate, "http_status": response["status"]})
                if response["status"] != 501:
                    break
            self.created_bookmark = self.find_created_bookmark(payload[0]["comment"])
            details = {
                "http_status": response["status"],
                "attempts": attempts,
                "created_found": bool(self.created_bookmark),
                "comment_prefix": "codex-bookmark-smoke",
                "is_protected": False,
                "created_id": self.created_bookmark.get("id", ""),
            }
            status = "PASS" if 200 <= response["status"] < 300 and self.created_bookmark else "WARN"
            return self.result("create_bookmark", "POST", path, status, details, start)
        except Exception as exc:
            return self.exception_result("create_bookmark", "POST", path, exc, start)

    def edit_bookmark(self) -> dict[str, Any]:
        start = time.perf_counter()
        path = "/archive/contents/bookmarks/"
        edited = dict(self.created_bookmark)
        edited["hostname"] = self.fixtures["host_name"]
        edited["comment"] = f"{edited.get('comment', 'codex-bookmark-smoke')}-edited"
        try:
            response = self.client.http_request("POST", path, [edited], **self.auth_kwargs(), max_items=25)
            found = self.find_created_bookmark(str(edited["comment"]))
            if found:
                self.created_bookmark = found
            details = {
                "http_status": response["status"],
                "edited_found": bool(found),
                "created_id": self.created_bookmark.get("id", ""),
            }
            status = "PASS" if 200 <= response["status"] < 300 and found else "WARN"
            return self.result("edit_bookmark", "POST", path, status, details, start)
        except Exception as exc:
            return self.exception_result("edit_bookmark", "POST", path, exc, start)

    def delete_bookmark(self) -> dict[str, Any]:
        start = time.perf_counter()
        path = "/archive/contents/bookmarks/"
        payload = bookmark_delete_payload(self.created_bookmark, host_name=self.fixtures["host_name"])
        try:
            response = self.client.http_request("POST", path, payload, **self.auth_kwargs(), max_items=25)
            details = {
                "http_status": response["status"],
                "created_id": self.created_bookmark.get("id", ""),
                "delete_semantics": "endpoint and storage_id cleared",
            }
            status = "PASS" if 200 <= response["status"] < 300 else "WARN"
            return self.result("delete_bookmark", "POST", path, status, details, start)
        except Exception as exc:
            return self.exception_result("delete_bookmark", "POST", path, exc, start)

    def verify_deleted(self) -> dict[str, Any]:
        start = time.perf_counter()
        path = f"/archive/contents/bookmarks/{self.fixtures['host_name']}/{self.fixtures['end']}/{self.fixtures['begin']}"
        try:
            response = self.client.http_request("GET", path, **self.auth_kwargs(), max_items=25)
            bookmarks = self.extract_bookmarks(response.get("body"))
            created_id = self.created_bookmark.get("id")
            still_present = any(item.get("id") == created_id for item in bookmarks)
            details = {
                "http_status": response["status"],
                "created_id": created_id,
                "still_present": still_present,
            }
            status = "PASS" if 200 <= response["status"] < 300 and not still_present else "WARN"
            return self.result("post_rollback_verify", "GET", path, status, details, start)
        except Exception as exc:
            return self.exception_result("post_rollback_verify", "GET", path, exc, start)

    def find_created_bookmark(self, comment: str) -> dict[str, Any]:
        response = self.client.http_request(
            "GET",
            f"/archive/contents/bookmarks/{self.fixtures['host_name']}/{self.fixtures['end']}/{self.fixtures['begin']}",
            **self.auth_kwargs(),
            max_items=50,
        )
        bookmarks = self.extract_bookmarks(response.get("body"))
        return next((item for item in bookmarks if item.get("comment") == comment), {})

    def extract_bookmarks(self, body: Any) -> list[dict[str, Any]]:
        if isinstance(body, list):
            return [item for item in body if isinstance(item, dict)]
        if isinstance(body, dict):
            for key in ("bookmarks", "items"):
                value = body.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

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

    def exception_result(self, name: str, method: str, path: str, exc: Exception, start: float) -> dict[str, Any]:
        details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
        if self.args.verbose:
            details["traceback"] = traceback.format_exc()
        return self.result(name, method, path, "FAIL", details, start)

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
                "hours": self.args.hours,
                "mutate_bookmark": self.args.mutate_bookmark,
            },
            "fixtures": self.fixtures,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"bookmark-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"bookmark-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "bookmark-smoke-latest.json"
        latest_md = self.args.report_dir / "bookmark-smoke-latest.md"
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
            "# Axxon One Bookmark Mutation Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Auth mode: `{report['selection']['auth_mode']}`",
            "",
            "This smoke creates, edits, and removes only a temporary `codex-` bookmark.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Fixtures", ""])
        for key, value in report["fixtures"].items():
            if key == "comment_suffix":
                continue
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Results", "", "| Status | Step | Endpoint | ms | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} id={details.get('created_id', '')}".replace("|", "\\|")
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
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--auth-mode", choices=["basic", "bearer"], default="bearer")
    parser.add_argument("--mutate-bookmark", action="store_true")
    parser.add_argument("--i-understand-bookmark-mutation", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not args.mutate_bookmark:
        parser.error("--mutate-bookmark is required because this tool changes archive bookmarks")
    if args.i_understand_bookmark_mutation != CONFIRMATION:
        parser.error(f"--i-understand-bookmark-mutation must equal {CONFIRMATION}")
    return args


def main() -> int:
    smoke = BookmarkSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 and report["summary"].get("WARN", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
