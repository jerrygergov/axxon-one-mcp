#!/usr/bin/env python3
"""Opt-in gRPC BookmarkService create/update/delete lifecycle smoke."""

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


CONFIRMATION = "CONFIRM-grpc-bookmark-smoke"


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def bookmark_request_data(*, camera_ap: str, archive_ap: str, message_suffix: str) -> dict[str, Any]:
    return {
        "message": f"codex-grpc-bookmark-smoke-{message_suffix}",
        "protection": "NOT_PROTECTED",
        "access": "PUBLIC",
        "categories": ["codex-smoke"],
        "camera_descriptions": [
            {
                "camera_access_point": camera_ap,
                "bindings": [{"access_point": archive_ap}],
            }
        ],
    }


class GrpcBookmarkSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}
        self.created_id = ""
        self.created_message = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_grpc()
        inventory = self.client.load_inventory()
        camera = self.choose_camera(inventory.get("cameras", []))
        camera_ap = camera.get("access_point", "")
        if not camera_ap:
            raise RuntimeError("no camera access point available")
        self.fixtures = {
            "camera_ap": camera_ap,
            "archive_ap": self.client.archive_access_point(),
            "range_begin": self.started_at - dt.timedelta(seconds=max(1, self.args.duration_seconds)),
            "range_end": self.started_at,
            "message_suffix": self.started_at.strftime("%Y%m%dT%H%M%S"),
        }

    def choose_camera(self, cameras: list[dict[str, Any]]) -> dict[str, Any]:
        preferred_names = {"Tracker", "Face", "LPR + MMR", "Traffic Analyzer RR 1"}
        for camera in cameras:
            if camera.get("display_name") in preferred_names and camera.get("access_point"):
                return camera
        return next((camera for camera in cameras if camera.get("access_point")), {})

    def bookmark_modules(self) -> tuple[Any, Any, Any]:
        service_pb2 = self.client.import_module("axxonsoft.bl.bookmarks.BookmarkService_pb2")
        bookmark_pb2 = self.client.import_module("axxonsoft.bl.bookmarks.Bookmark_pb2")
        primitive_pb2 = self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        return service_pb2, bookmark_pb2, primitive_pb2

    def timestamp(self, value: dt.datetime) -> Any:
        timestamp_pb2 = self.client.import_module("google.protobuf.timestamp_pb2")
        out = timestamp_pb2.Timestamp()
        out.FromDatetime(value.astimezone(dt.UTC))
        return out

    def time_range(self, primitive_pb2: Any) -> Any:
        return primitive_pb2.TimeRangeTS(
            begin_time=self.timestamp(self.fixtures["range_begin"]),
            end_time=self.timestamp(self.fixtures["range_end"]),
        )

    def build_bookmark(self, *, message: str | None = None, existing: Any | None = None) -> Any:
        _service_pb2, bookmark_pb2, primitive_pb2 = self.bookmark_modules()
        bookmark = bookmark_pb2.Bookmark()
        if existing is not None:
            bookmark.CopyFrom(existing)
        else:
            data = bookmark_request_data(
                camera_ap=self.fixtures["camera_ap"],
                archive_ap=self.fixtures["archive_ap"],
                message_suffix=self.fixtures["message_suffix"],
            )
            bookmark.range.CopyFrom(self.time_range(primitive_pb2))
            bookmark.protection = bookmark_pb2.NOT_PROTECTED
            bookmark.access = bookmark_pb2.PUBLIC
            bookmark.categories.extend(data["categories"])
            description = bookmark.camera_descriptions.descriptions.add()
            description.camera_access_point = data["camera_descriptions"][0]["camera_access_point"]
            binding = description.bindings.add()
            binding.access_point = data["camera_descriptions"][0]["bindings"][0]["access_point"]
            message = data["message"]
        bookmark.message = message or bookmark.message
        self.created_message = bookmark.message
        return bookmark

    def stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/bookmarks/BookmarkService.proto", "BookmarkService")

    def run_lifecycle(self) -> dict[str, Any]:
        service_pb2, _bookmark_pb2, primitive_pb2 = self.bookmark_modules()
        stub = self.stub()

        created = stub.CreateBookmark(
            service_pb2.CreateBookmarkRequest(bookmark=self.build_bookmark()),
            timeout=self.args.timeout,
        )
        created_data = self.client.message_to_dict(created)
        created_bookmark = created.bookmark
        self.created_id = created_bookmark.id
        if not self.created_id:
            raise RuntimeError(f"CreateBookmark returned no id: {created_data}")

        listed_created = self.list_bookmarks(stub, service_pb2, primitive_pb2, message=self.created_message)
        if self.created_id not in {item.get("id") for item in listed_created}:
            raise RuntimeError(f"created bookmark not found by ListBookmarks filter: id={self.created_id}")

        edited_message = f"{self.created_message}-edited"
        updated = stub.UpdateBookmark(
            service_pb2.UpdateBookmarkRequest(bookmark=self.build_bookmark(message=edited_message, existing=created_bookmark)),
            timeout=self.args.timeout,
        )
        updated_bookmark = updated.bookmark
        if updated_bookmark.message != edited_message:
            raise RuntimeError(f"UpdateBookmark readback message mismatch: {updated_bookmark.message!r}")
        self.created_message = edited_message

        listed_updated = self.list_bookmarks(stub, service_pb2, primitive_pb2, message=edited_message)
        if self.created_id not in {item.get("id") for item in listed_updated}:
            raise RuntimeError(f"updated bookmark not found by ListBookmarks filter: id={self.created_id}")

        deleted_id = self.created_id
        stub.DeleteBookmark(service_pb2.DeleteBookmarkRequest(id=deleted_id), timeout=self.args.timeout)
        self.created_id = ""

        listed_deleted = self.list_bookmarks(stub, service_pb2, primitive_pb2, message=edited_message)
        still_present = any(item.get("id") == deleted_id for item in listed_deleted)
        if still_present:
            raise RuntimeError(f"bookmark still present after DeleteBookmark: id={deleted_id}")

        return {
            "created_id_len": len(deleted_id),
            "camera_ap": self.fixtures["camera_ap"],
            "archive_ap": self.fixtures["archive_ap"],
            "message_prefix": "codex-grpc-bookmark-smoke",
            "created_filter_count": len(listed_created),
            "updated_filter_count": len(listed_updated),
            "deleted_filter_count": len(listed_deleted),
            "range_seconds": self.args.duration_seconds,
        }

    def list_bookmarks(self, stub: Any, service_pb2: Any, primitive_pb2: Any, *, message: str) -> list[dict[str, Any]]:
        request = service_pb2.ListBookmarksRequest(
            range=self.time_range(primitive_pb2),
            page_size=100,
            filter=service_pb2.Filter(camera_access_points=[self.fixtures["camera_ap"]], message=message),
        )
        bookmarks: list[dict[str, Any]] = []
        while True:
            response = stub.ListBookmarks(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            bookmarks.extend(data.get("bookmarks", []))
            if not response.next_page_token:
                break
            request.page_token = response.next_page_token
        return bookmarks

    def cleanup(self) -> list[dict[str, Any]]:
        if not self.created_id:
            return []
        try:
            service_pb2, _bookmark_pb2, _primitive_pb2 = self.bookmark_modules()
            self.stub().DeleteBookmark(service_pb2.DeleteBookmarkRequest(id=self.created_id), timeout=self.args.timeout)
            cleanup = [{"object": self.created_id, "status": "bookmark_deleted"}]
            self.created_id = ""
            return cleanup
        except Exception as exc:
            return [{"object": self.created_id, "status": "bookmark_cleanup_failed", "error": str(exc)[:400]}]

    def run(self) -> dict[str, Any]:
        self.setup()
        start = time.perf_counter()
        try:
            details = self.run_lifecycle()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "FAIL"
        self.results.append({"group": "grpc_bookmark_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
        cleanup_results = self.cleanup()
        if cleanup_results:
            cleanup_status = "PASS" if all(item.get("status") == "bookmark_deleted" for item in cleanup_results) else "WARN"
            self.results.append({"group": "cleanup", "status": cleanup_status, "elapsed_ms": 0, "details": {"cleanup": cleanup_results}})
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "fixtures": {
                "camera_ap": self.fixtures.get("camera_ap", ""),
                "archive_ap": self.fixtures.get("archive_ap", ""),
                "range_begin": self.fixtures.get("range_begin", "").isoformat() if self.fixtures.get("range_begin") else "",
                "range_end": self.fixtures.get("range_end", "").isoformat() if self.fixtures.get("range_end") else "",
                "message_prefix": "codex-grpc-bookmark-smoke",
            },
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"grpc-bookmark-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"grpc-bookmark-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "grpc-bookmark-smoke-latest.json"
        latest_md = self.args.report_dir / "grpc-bookmark-smoke-latest.md"
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
            "# Axxon One gRPC BookmarkService Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Camera AP: `{report['fixtures']['camera_ap']}`",
            f"- Archive AP: `{report['fixtures']['archive_ap']}`",
            "",
            "Creates a temporary `codex-grpc-bookmark-smoke-*` bookmark through `BookmarkService.CreateBookmark`, updates it, verifies listing filters, and deletes it.",
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
        if result["group"] == "grpc_bookmark_lifecycle":
            return (
                f"created_id_len={details.get('created_id_len')} created_filter_count={details.get('created_filter_count')} "
                f"updated_filter_count={details.get('updated_filter_count')} deleted_filter_count={details.get('deleted_filter_count')}"
            )
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--duration-seconds", type=int, default=10)
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
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def main() -> int:
    smoke = GrpcBookmarkSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
