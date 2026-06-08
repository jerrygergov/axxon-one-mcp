#!/usr/bin/env python3
"""No-op archive management dispatch smoke using a nonexistent volume id."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-archive-management-noop"


class ArchiveManagementNoopSmoke:
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
        self.fixtures["fake_volume_id"] = f"codex-nonexistent-{uuid.uuid4()}"

    def archive_stub_and_pb2(self) -> tuple[Any, Any]:
        archive_pb2 = self.client.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
        return self.client.common_stubs()["archive"], archive_pb2

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.fake_volume_state("pre_fake_volume_state"))
        self.results.append(self.format_fake_volume())
        self.results.append(self.reindex_fake_volume())
        self.results.append(self.cancel_reindex_fake_volume())
        self.results.append(self.fake_volume_state("post_fake_volume_state"))
        report = self.report()
        self.write_report(report)
        return report

    def fake_volume_state(self, group: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.archive_stub_and_pb2()
            response = stub.GetVolumesState(
                pb2.GetVolumesStateRequest(
                    access_point=self.fixtures["archive_ap"],
                    volume_ids=[self.fixtures["fake_volume_id"]],
                ),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            not_found = data.get("not_found_volumes", [])
            return self.result(
                group,
                "PASS" if self.fixtures["fake_volume_id"] in not_found else "WARN",
                {
                    "fake_volume_id_len": len(self.fixtures["fake_volume_id"]),
                    "volume_state_count": len(data.get("volumes_state", {})),
                    "not_found_count": len(not_found),
                    "fake_not_found": self.fixtures["fake_volume_id"] in not_found,
                },
                start,
            )
        except Exception as exc:
            return self.exception_result(group, exc, start)

    def format_fake_volume(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.archive_stub_and_pb2()
            response = stub.FormatVolumes(
                pb2.FormatVolumesRequest(
                    access_point=self.fixtures["archive_ap"],
                    volumes=[pb2.FormatVolumesRequest.Volume(id=self.fixtures["fake_volume_id"])],
                ),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            status_code = data.get("results", [{}])[0].get("status_code", "") if data.get("results") else ""
            return self.result(
                "format_fake_volume",
                "PASS" if status_code in ("NOT_FOUND", 1) else "WARN",
                {"result_count": len(data.get("results", [])), "status_code": status_code},
                start,
            )
        except Exception as exc:
            return self.exception_result("format_fake_volume", exc, start)

    def reindex_fake_volume(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.archive_stub_and_pb2()
            response = stub.Reindex(
                pb2.ReindexRequest(
                    access_point=self.fixtures["archive_ap"],
                    volume_ids=[self.fixtures["fake_volume_id"]],
                    full_reindex=pb2.ReindexRequest.FullReindexType(),
                ),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            return self.result(
                "reindex_fake_volume",
                "PASS",
                {"failed_volume_count": len(data.get("failed_volume_ids", [])), "response_keys": sorted(data.keys())},
                start,
            )
        except Exception as exc:
            return self.exception_result("reindex_fake_volume", exc, start)

    def cancel_reindex_fake_volume(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.archive_stub_and_pb2()
            response = stub.CancelReindex(
                pb2.CancelReindexRequest(
                    access_point=self.fixtures["archive_ap"],
                    volume_ids=[self.fixtures["fake_volume_id"]],
                ),
                timeout=self.args.timeout,
            )
            data = self.client.message_to_dict(response)
            return self.result("cancel_reindex_fake_volume", "PASS", {"response_keys": sorted(data.keys())}, start)
        except Exception as exc:
            return self.exception_result("cancel_reindex_fake_volume", exc, start)

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
            "fixtures": {
                "archive_ap": self.fixtures.get("archive_ap", ""),
                "fake_volume_id_prefix": "codex-nonexistent",
                "fake_volume_id_len": len(self.fixtures.get("fake_volume_id", "")),
            },
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"archive-management-noop-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"archive-management-noop-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "archive-management-noop-smoke-latest.json"
        latest_md = self.args.report_dir / "archive-management-noop-smoke-latest.md"
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
            "# Axxon One Archive Management No-Op Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Archive AP: `{report['fixtures']['archive_ap']}`",
            "",
            "Uses a `codex-nonexistent-*` volume id to verify archive-management method dispatch without formatting or reindexing a real volume.",
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
        return f"keys={sorted(details.keys())}"


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not args.i_understand_this_mutates or args.confirm != CONFIRMATION:
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def main() -> int:
    report = ArchiveManagementNoopSmoke(parse_args()).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
