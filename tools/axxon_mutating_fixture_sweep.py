#!/usr/bin/env python3
"""Run controlled low-risk mutating Axxon One API fixtures."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_probe import Probe


class MutatingFixtureSweep:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.probe = Probe(args)
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []

    def setup(self) -> dict[str, Any]:
        self.probe.ensure_stubs()
        self.probe.import_proto_modules()
        self.probe.authenticate_grpc()
        return self.probe.stubs()

    def msg(self, message: Any) -> dict[str, Any]:
        return self.probe.msg(message)

    def run_shared_kv_fixture(self, stubs: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        shared = stubs["shared"]
        pb = self.probe.pb["shared_pb2"]
        prefix = ""
        key = f"codex-mutating-fixture-{uuid.uuid4()}"
        value = json.dumps(
            {
                "created_at": self.started_at.isoformat(),
                "fixture": "shared_kv_temp_record",
            }
        ).encode()
        details: dict[str, Any] = {
            "fixture": "shared_kv_temp_record",
            "prefix": prefix,
            "key": key,
            "rollback_verified": False,
        }
        try:
            details["cleanup_before"] = self.cleanup_shared_kv(shared, pb, "codex-mutating-fixture-")

            commit = shared.Commit(
                pb.SharedKVCommitRequest(prefix=prefix, set=[pb.SharedKVRecord(key=key, value=value)]),
                timeout=self.args.timeout,
            )
            details["set_error_code"] = commit.error_code
            if commit.error_code != 0:
                raise RuntimeError(f"SharedKV set failed: {self.msg(commit)}")
            revision = commit.updated[0].revision if commit.updated else ""
            details["revision_created"] = bool(revision)

            got = shared.BatchGetRecords(
                pb.BatchGetRecordsRequest(prefix=prefix, items=[pb.SharedKVRecordInfo(key=key)]),
                timeout=self.args.timeout,
            )
            details["batch_get_items"] = len(got.items)
            if not got.items or got.items[0].value != value:
                raise RuntimeError("SharedKV value was not readable after set")

            chunks = list(
                shared.GetRecordsStream(
                    pb.GetRecordsStreamRequest(
                        prefix=prefix,
                        chunk_size_kb=16,
                        items=[pb.SharedKVRecordInfo(key=key)],
                    ),
                    timeout=self.args.timeout,
                )
            )
            details["stream_chunks"] = len(chunks)

            removed = shared.Commit(
                pb.SharedKVCommitRequest(
                    prefix=prefix,
                    removed=[pb.SharedKVRecordInfo(key=key, revision=revision)],
                ),
                timeout=self.args.timeout,
            )
            details["remove_error_code"] = removed.error_code
            if removed.error_code != 0:
                raise RuntimeError(f"SharedKV remove failed: {self.msg(removed)}")

            listed_after = shared.ListRecords(
                pb.ListRecordsRequest(prefix=prefix, view=pb.ESHKV_FULL),
                timeout=self.args.timeout,
            )
            batch_after = shared.BatchGetRecords(
                pb.BatchGetRecordsRequest(prefix=prefix, items=[pb.SharedKVRecordInfo(key=key)]),
                timeout=self.args.timeout,
            )
            list_contains = any(item.key == key for item in listed_after.items)
            batch_has_value = any(item.key == key and bool(item.value) for item in batch_after.items)
            details["list_contains_after_remove"] = list_contains
            details["batch_has_value_after_remove"] = batch_has_value
            details["batch_get_after_remove_items"] = len(batch_after.items)
            details["rollback_verified"] = not list_contains and not batch_has_value
            if not details["rollback_verified"]:
                raise RuntimeError("SharedKV rollback verification failed")
            return self.result("SharedKV temporary write/read/stream/remove", "PASS", details, start)
        except Exception as exc:
            details["error_type"] = exc.__class__.__name__
            details["error"] = str(exc)[:800]
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            try:
                details["cleanup_after_error"] = self.cleanup_shared_kv(shared, pb, "codex-mutating-fixture-")
            except Exception as cleanup_exc:
                details["cleanup_error"] = str(cleanup_exc)[:800]
            return self.result("SharedKV temporary write/read/stream/remove", "FAIL", details, start)

    def cleanup_shared_kv(self, shared: Any, pb: Any, key_prefix: str) -> int:
        cleaned = 0
        records = shared.ListRecords(
            pb.ListRecordsRequest(prefix="", view=pb.ESHKV_FULL),
            timeout=self.args.timeout,
        )
        for item in records.items:
            if not item.key.startswith(key_prefix):
                continue
            response = shared.Commit(
                pb.SharedKVCommitRequest(
                    prefix="",
                    removed=[pb.SharedKVRecordInfo(key=item.key, revision=item.revision)],
                ),
                timeout=self.args.timeout,
            )
            if response.error_code == 0:
                cleaned += 1
        return cleaned

    def result(self, name: str, status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        stubs = self.setup()
        self.results.append(self.run_shared_kv_fixture(stubs))
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
                "host": self.args.host,
                "grpc_port": self.args.grpc_port,
                "tls_cn": self.args.tls_cn,
                "username": self.args.username,
                "password": "<redacted>",
            },
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"mutating-fixture-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"mutating-fixture-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "mutating-fixture-sweep-latest.json"
        latest_md = self.args.report_dir / "mutating-fixture-sweep-latest.md"
        json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        json_path.write_text(json_text)
        latest_json.write_text(json_text)
        md_text = self.render_markdown(report)
        md_path.write_text(md_text)
        latest_md.write_text(md_text)
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Mutating Fixture Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- TLS CN override: `{self.args.tls_cn}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Fixture | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            if result["status"] == "PASS":
                note = f"rollback_verified={details.get('rollback_verified')} stream_chunks={details.get('stream_chunks')}"
            else:
                note = details.get("error", "")[:180]
            lines.append(f"| {result['status']} | `{result['name']}` | {result['elapsed_ms']} | {note.replace('|', '\\|')} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("AXXON_HOST", "127.0.0.1"))
    parser.add_argument("--grpc-port", type=int, default=int(os.getenv("AXXON_GRPC_PORT", "20109")))
    parser.add_argument("--http-port", type=int, default=int(os.getenv("AXXON_HTTP_PORT", "8000")))
    parser.add_argument("--http-url", default=os.getenv("AXXON_HTTP_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--username", default=os.getenv("AXXON_USERNAME", "root"))
    parser.add_argument("--password", default=os.getenv("AXXON_PASSWORD"))
    parser.add_argument("--tls-cn", default=os.getenv("AXXON_TLS_CN", "F4E66972EC19"))
    parser.add_argument("--ca", type=Path, default=Path(os.getenv("AXXON_CA", str(repo_root / "docs/grpc-proto-files/api.ngp.root-ca.crt"))))
    parser.add_argument("--proto-dir", type=Path, default=repo_root / "docs/grpc-proto-files")
    parser.add_argument("--stubs-dir", type=Path, default=Path(os.getenv("AXXON_GRPC_STUBS", "/tmp/axxon-grpc-py")))
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-http", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    sweep = MutatingFixtureSweep(args)
    report = sweep.run()
    print("Summary:", report["summary"])
    return 1 if report["summary"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
