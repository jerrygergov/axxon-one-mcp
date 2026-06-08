#!/usr/bin/env python3
"""Controlled export lifecycle smoke for Axxon One.

This tool starts temporary codex-scoped export sessions, downloads only bounded
chunks, and destroys every session it creates.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


EXPORT_CONFIRMATION = "CONFIRM-export-smoke"


def build_snapshot_export_options(
    export_pb2: Any,
    *,
    camera_ap: str,
    storage_ap: str,
    timestamp: str,
    file_name: str,
    max_file_size: int,
) -> Any:
    return export_pb2.Options(
        archive=export_pb2.ArchiveMode(
            sources=[export_pb2.ArchiveMode.Source(origin=camera_ap, storages=[storage_ap])],
            start_timestamp=timestamp,
        ),
        snapshot=export_pb2.SnapshotType(format=export_pb2.SnapshotType.JPEG),
        settings=[export_pb2.CommonSetting(file_name=file_name)],
        max_file_size=max_file_size,
        store_result_by_export_agent=False,
    )


def build_live_stop_export_options(
    export_pb2: Any,
    duration_pb2: Any,
    *,
    camera_ap: str,
    file_name: str,
    duration_seconds: int,
    max_file_size: int,
) -> Any:
    return export_pb2.Options(
        live=export_pb2.LiveMode(
            sources=[export_pb2.LiveMode.Source(origin=camera_ap)],
            duration=duration_pb2.Duration(seconds=duration_seconds),
        ),
        stream=export_pb2.StreamType(
            format=export_pb2.StreamType.MP4,
            settings=[export_pb2.StreamSetting(reject_audio=True)],
        ),
        settings=[export_pb2.CommonSetting(file_name=file_name)],
        max_file_size=max_file_size,
        store_result_by_export_agent=False,
    )


class ExportSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.client.authenticate_http_grpc()
        inventory = self.client.load_inventory()
        camera = next((item for item in inventory.get("cameras", []) if item.get("access_point")), {})
        self.fixtures["camera_ap"] = self.args.camera_ap or camera.get("access_point", "")
        self.fixtures["camera_legacy_ap"] = self.fixtures["camera_ap"].removeprefix("hosts/")
        self.fixtures["archive_ap"] = self.client.archive_access_point()
        self.fixtures["export_agent_ap"] = self.export_agent_access_point()
        self.fixtures["archive_timestamp"] = self.resolve_archive_timestamp()

    def export_agent_access_point(self) -> str:
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/config/ConfigurationService.proto", "ConfigurationService")
        response = stub.ListUnits(pb2.ListUnitsRequest(unit_uids=["hosts/Server"], display_mode=0), timeout=self.args.timeout)
        for unit in self.client.message_to_dict(response).get("units", []):
            for child in unit.get("units", []):
                if child.get("type") == "MMExportAgent":
                    return str(child.get("access_point", ""))
        return ""

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
            return intervals[-1].get("end") or intervals[-1].get("begin") or end
        return end

    def export_stub_and_pb2(self) -> tuple[Any, Any, Any]:
        export_pb2 = self.client.import_module("axxonsoft.bl.mmexport.Export_pb2")
        service_pb2 = self.client.import_module("axxonsoft.bl.mmexport.ExportService_pb2")
        return self.client.stub_from_proto("axxonsoft/bl/mmexport/ExportService.proto", "ExportService"), export_pb2, service_pb2

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.snapshot_export_lifecycle())
        self.results.append(self.stop_running_session_lifecycle())
        report = self.report()
        self.write_report(report)
        return report

    def snapshot_export_lifecycle(self) -> dict[str, Any]:
        start = time.perf_counter()
        session_id = ""
        destroyed = False
        try:
            stub, export_pb2, service_pb2 = self.export_stub_and_pb2()
            options = build_snapshot_export_options(
                export_pb2,
                camera_ap=self.fixtures["camera_ap"],
                storage_ap=self.fixtures["archive_ap"],
                timestamp=self.fixtures["archive_timestamp"],
                file_name=f"codex-export-smoke-{uuid.uuid4().hex[:8]}",
                max_file_size=self.args.max_file_size,
            )
            session_id = stub.StartSession(service_pb2.StartSessionRequest(session_options=options), timeout=self.args.timeout).started_session_id
            state = self.poll_state(stub, service_pb2, session_id, want_completed=True)
            files = list(state.result.files) if state and state.result else []
            download_summary = self.download_first_file(stub, service_pb2, session_id, files[0].path) if files else {}
            stub.DestroySession(service_pb2.DestroySessionRequest(session_id=session_id), timeout=self.args.timeout)
            destroyed = True
            return self.result(
                "snapshot_export_lifecycle",
                "PASS" if files and download_summary.get("bytes", 0) > 0 and destroyed else "WARN",
                {
                    "session_id_len": len(session_id),
                    "state": self.state_name(service_pb2, state.state if state else 0),
                    "file_count": len(files),
                    "first_file_size": int(files[0].size) if files else 0,
                    "first_file_mime": files[0].mime_type if files else "",
                    "download": download_summary,
                    "destroyed": destroyed,
                },
                start,
            )
        except Exception as exc:
            return self.exception_result("snapshot_export_lifecycle", exc, start, session_id=session_id, destroyed=destroyed)
        finally:
            if session_id and not destroyed:
                self.try_destroy(session_id)

    def stop_running_session_lifecycle(self) -> dict[str, Any]:
        start = time.perf_counter()
        session_id = ""
        destroyed = False
        try:
            stub, export_pb2, service_pb2 = self.export_stub_and_pb2()
            duration_pb2 = self.client.import_module("google.protobuf.duration_pb2")
            options = build_live_stop_export_options(
                export_pb2,
                duration_pb2,
                camera_ap=self.fixtures["camera_ap"],
                file_name=f"codex-export-stop-{uuid.uuid4().hex[:8]}",
                duration_seconds=self.args.live_duration_seconds,
                max_file_size=self.args.max_file_size,
            )
            session_id = stub.StartSession(service_pb2.StartSessionRequest(session_options=options), timeout=self.args.timeout).started_session_id
            running_state = self.poll_state(stub, service_pb2, session_id, want_running=True)
            stopped = stub.StopSession(service_pb2.StopSessionRequest(session_id=session_id), timeout=self.args.timeout)
            stub.DestroySession(service_pb2.DestroySessionRequest(session_id=session_id), timeout=self.args.timeout)
            destroyed = True
            return self.result(
                "stop_running_session_lifecycle",
                "PASS" if session_id and destroyed else "WARN",
                {
                    "session_id_len": len(session_id),
                    "running_state": self.state_name(service_pb2, running_state.state if running_state else 0),
                    "stop_response_shape": self.client.shape(self.client.message_to_dict(stopped)),
                    "destroyed": destroyed,
                },
                start,
            )
        except Exception as exc:
            return self.exception_result("stop_running_session_lifecycle", exc, start, session_id=session_id, destroyed=destroyed)
        finally:
            if session_id and not destroyed:
                self.try_destroy(session_id)

    def poll_state(self, stub: Any, service_pb2: Any, session_id: str, *, want_completed: bool = False, want_running: bool = False) -> Any:
        last_state = None
        for _ in range(max(1, self.args.poll_attempts)):
            response = stub.GetSessionState(service_pb2.GetSessionStateRequest(session_id=session_id), timeout=self.args.timeout)
            last_state = response.session_state
            state = int(last_state.state)
            if want_running and state == 1:
                return last_state
            if want_completed and state == 2:
                return last_state
            time.sleep(max(0.1, self.args.poll_delay))
        return last_state

    def download_first_file(self, stub: Any, service_pb2: Any, session_id: str, file_path: str) -> dict[str, Any]:
        total = 0
        chunks = 0
        digest = hashlib.sha256()
        for chunk in stub.DownloadFile(
            service_pb2.DownloadFileRequest(
                session_id=session_id,
                file_path=file_path,
                chunk_size_kb=max(1, self.args.chunk_size_kb),
            ),
            timeout=self.args.timeout,
        ):
            data = bytes(chunk.data)
            total += len(data)
            chunks += 1
            digest.update(data)
            if total >= self.args.max_download_bytes:
                break
        return {"bytes": total, "chunks": chunks, "sha256": digest.hexdigest() if total else ""}

    def try_destroy(self, session_id: str) -> None:
        try:
            stub, _, service_pb2 = self.export_stub_and_pb2()
            stub.DestroySession(service_pb2.DestroySessionRequest(session_id=session_id), timeout=self.args.timeout)
        except Exception:
            pass

    def state_name(self, export_pb2: Any, value: int) -> str:
        try:
            return export_pb2.EState.Name(int(value))
        except Exception:
            return str(value)

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
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "selection": {
                "hours": self.args.hours,
                "poll_attempts": self.args.poll_attempts,
                "max_download_bytes": self.args.max_download_bytes,
                "chunk_size_kb": self.args.chunk_size_kb,
            },
            "fixtures": {
                "camera_ap": self.fixtures.get("camera_ap", ""),
                "archive_ap": self.fixtures.get("archive_ap", ""),
                "export_agent_ap": self.fixtures.get("export_agent_ap", ""),
                "archive_timestamp": self.fixtures.get("archive_timestamp", ""),
            },
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"export-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"export-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "export-smoke-latest.json"
        latest_md = self.args.report_dir / "export-smoke-latest.md"
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
            "# Axxon One Export Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Starts only temporary `codex-*` export sessions and destroys every session it creates.",
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
            note = self.note_for(result).replace("|", "\\|")[:220]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        details = result.get("details", {})
        if details.get("error"):
            return details["error"]
        if result["group"] == "snapshot_export_lifecycle":
            download = details.get("download", {})
            return f"state={details.get('state')} files={details.get('file_count')} first_size={details.get('first_file_size')} downloaded={download.get('bytes')} destroyed={details.get('destroyed')}"
        if result["group"] == "stop_running_session_lifecycle":
            return f"running_state={details.get('running_state')} stopped_shape={details.get('stop_response_shape')} destroyed={details.get('destroyed')}"
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--camera-ap", default="")
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument("--poll-attempts", type=int, default=20)
    parser.add_argument("--poll-delay", type=float, default=1.0)
    parser.add_argument("--max-download-bytes", type=int, default=262144)
    parser.add_argument("--chunk-size-kb", type=int, default=16)
    parser.add_argument("--max-file-size", type=int, default=1048576)
    parser.add_argument("--live-duration-seconds", type=int, default=30)
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
        parser.error("--i-understand-this-mutates is required because this tool starts export sessions and writes export files")
    if args.confirm != EXPORT_CONFIRMATION:
        parser.error(f"--confirm must equal {EXPORT_CONFIRMATION}")
    return args


def main() -> int:
    report = ExportSmoke(parse_args()).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
