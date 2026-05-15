#!/usr/bin/env python3
"""Read-only preflight for archive volume, disk-space, and reindex fixtures."""

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


ARCHIVE_MUTATIONS_REQUIRING_APPROVAL = [
    {
        "rpc": "ArchiveService.FormatVolumes",
        "risk": "formats archive volumes",
        "requirement": "isolated non-production volume id and rollback/snapshot approval",
    },
    {
        "rpc": "ArchiveService.Reindex",
        "risk": "schedules archive volume reindexing",
        "requirement": "isolated archive or explicit maintenance-window approval",
    },
    {
        "rpc": "ArchiveService.CancelReindex",
        "risk": "changes active reindex state",
        "requirement": "only after this tool or an operator started a known test reindex",
    },
]


def volume_state_summary(volumes_state: dict[str, dict[str, Any]]) -> dict[str, Any]:
    states = Counter(str(item.get("state", "STATE_UNSPECIFIED")) for item in volumes_state.values())
    readonly_count = sum(1 for item in volumes_state.values() if item.get("readonly") is True)
    return {
        "volume_count": len(volumes_state),
        "states": dict(states),
        "readonly_count": readonly_count,
        "volume_id_lengths": sorted(len(str(volume_id)) for volume_id in volumes_state),
    }


class ArchiveManagementPreflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.client.load_inventory()
        self.fixtures["archive_ap"] = self.client.archive_access_point()

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.get_archive_traits())
        self.results.append(self.get_volumes_state())
        self.results.append(self.get_disk_space_for_first_volume())
        self.results.append(
            {
                "group": "approval_only_mutations",
                "status": "WARN",
                "elapsed_ms": 0,
                "details": {"not_executed": ARCHIVE_MUTATIONS_REQUIRING_APPROVAL},
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def archive_stub_and_pb2(self) -> tuple[Any, Any]:
        archive_pb2 = self.client.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
        return self.client.common_stubs()["archive"], archive_pb2

    def get_archive_traits(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, archive_pb2 = self.archive_stub_and_pb2()
            response = stub.GetArchiveTraits(
                archive_pb2.GetArchiveTraitsRequest(access_point=self.fixtures["archive_ap"]),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            return self.result(
                "get_archive_traits",
                "PASS",
                {"traits": data.get("traits", []), "trait_count": len(data.get("traits", []))},
                start,
            )
        except Exception as exc:
            return self.exception_result("get_archive_traits", exc, start)

    def get_volumes_state(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, archive_pb2 = self.archive_stub_and_pb2()
            response = stub.GetVolumesState(
                archive_pb2.GetVolumesStateRequest(access_point=self.fixtures["archive_ap"]),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            volumes_state = data.get("volumes_state", {})
            self.fixtures["volume_ids"] = sorted(volumes_state)
            status = "PASS" if volumes_state else "WARN"
            details = volume_state_summary(volumes_state)
            details["not_found_count"] = len(data.get("not_found_volumes", []))
            details["is_failover_mode"] = data.get("is_failover_mode", False)
            details["is_temporary_storage"] = data.get("is_temporary_storage", False)
            return self.result("get_volumes_state", status, details, start)
        except Exception as exc:
            return self.exception_result("get_volumes_state", exc, start)

    def get_disk_space_for_first_volume(self) -> dict[str, Any]:
        start = time.perf_counter()
        volume_ids = self.fixtures.get("volume_ids", [])
        if not volume_ids:
            return self.result("get_disk_space", "WARN", {"skipped": "no volume id found"}, start)
        try:
            stub, archive_pb2 = self.archive_stub_and_pb2()
            response = stub.GetDiskSpace(
                archive_pb2.GetDiskSpaceRequest(storage_access_point=self.fixtures["archive_ap"], volume_id=volume_ids[0]),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            space = data.get("space", {})
            details = {
                "volume_id_len": len(volume_ids[0]),
                "status_code": data.get("status_code", "OK"),
                "capacity_bytes_present": "capacity_bytes" in space,
                "free_bytes_present": "free_bytes" in space,
            }
            status = "PASS" if data.get("status_code", "OK") in ("OK", 0) else "WARN"
            return self.result("get_disk_space", status, details, start)
        except Exception as exc:
            return self.exception_result("get_disk_space", exc, start)

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
                "archive_ap": self.fixtures.get("archive_ap", ""),
                "volume_count": len(self.fixtures.get("volume_ids", [])),
                "volume_id_lengths": sorted(len(str(item)) for item in self.fixtures.get("volume_ids", [])),
            },
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"archive-management-preflight-{stamp}.json"
        md_path = self.args.report_dir / f"archive-management-preflight-{stamp}.md"
        latest_json = self.args.report_dir / "archive-management-preflight-latest.json"
        latest_md = self.args.report_dir / "archive-management-preflight-latest.md"
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
            "# Axxon One Archive Management Preflight",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Archive AP: `{report['fixtures']['archive_ap']}`",
            "",
            "Read-only preflight for archive-management mutations. It does not format, reindex, cancel reindex, resize, clear, delete, or link archive volumes.",
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
        if result["group"] == "get_volumes_state":
            return f"volume_count={details.get('volume_count')} states={details.get('states')} readonly_count={details.get('readonly_count')}"
        if result["group"] == "get_disk_space":
            return f"volume_id_len={details.get('volume_id_len')} status_code={details.get('status_code')} capacity_present={details.get('capacity_bytes_present')}"
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
    preflight = ArchiveManagementPreflight(parse_args())
    report = preflight.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
