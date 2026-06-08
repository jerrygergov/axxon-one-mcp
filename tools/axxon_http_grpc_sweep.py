#!/usr/bin/env python3
"""Sweep Axxon One HTTP /grpc parity for read-oriented methods."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, config_from_args
from axxon_readonly_sweep import ReadOnlySweep


class HttpGrpcSweep:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.grpc_fixture = ReadOnlySweep(args)
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.token = ""

    def setup(self) -> None:
        self.grpc_fixture.setup()
        self.authenticate_http()

    def authenticate_http(self) -> None:
        self.token = self.client.authenticate_http_grpc()

    def http_request(self, method: str, path: str, body: Any = None, basic: bool = False, bearer: bool = False) -> dict[str, Any]:
        return self.client.http_request(
            method,
            path,
            body=body,
            basic=basic,
            bearer=bearer,
            max_items=self.args.max_stream_pages,
        )

    def request_data_for(self, row: dict[str, str]) -> dict[str, Any]:
        pb2_module, _stub = self.grpc_fixture.import_for_row(row)
        request = self.grpc_fixture.request_for(row, pb2_module)
        return self.client.to_json_data(request)

    def invoke(self, row: dict[str, str]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            request_data = self.request_data_for(row)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(row, "FAIL", details, start)

        try:
            response = self.http_request(
                "POST",
                "/grpc",
                {"method": row["fqmn"], "data": request_data},
                bearer=True,
            )
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "shape": self.shape(response.get("body")),
            }
            status = "PASS" if response["status"] == 200 else "WARN"
            return self.result(row, status, details, start)
        except Exception as exc:
            details = {"transport_error_type": exc.__class__.__name__, "transport_error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(row, "WARN", details, start)

    def shape(self, value: Any) -> Any:
        return self.client.shape(value)

    def result(self, row: dict[str, str], status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {
            "fqmn": row["fqmn"],
            "package": row["package"],
            "service": row["service"],
            "method": row["method"],
            "proto": row["proto"],
            "streaming": row["streaming"],
            "safety": row["safety"],
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        selected = self.load_parity_catalog()
        for row in selected:
            self.results.append(self.invoke(row))
        report = self.report(len(selected), self.grpc_fixture.count_skipped())
        self.write_report(report)
        return report

    def load_parity_catalog(self) -> list[dict[str, str]]:
        rows = self.grpc_fixture.load_catalog()
        selected: list[dict[str, str]] = []
        for row in rows:
            if not self.args.include_fixture_needed and not row["live_status"].startswith("tested-pass"):
                continue
            if not self.args.include_server_streams and row["streaming"] == "server":
                continue
            selected.append(row)
        return selected

    def report(self, selected_count: int, skipped_count: int) -> dict[str, Any]:
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
                "catalog": str(self.args.catalog),
                "selected_methods": selected_count,
                "skipped_high_risk_read_methods": skipped_count,
                "timeout_seconds": self.args.timeout,
                "include_fixture_needed": self.args.include_fixture_needed,
                "include_server_streams": self.args.include_server_streams,
            },
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"http-grpc-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"http-grpc-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "http-grpc-sweep-latest.json"
        latest_md = self.args.report_dir / "http-grpc-sweep-latest.md"
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
            "# Axxon One HTTP /grpc Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Selected methods: `{report['selection']['selected_methods']}`",
            f"- Skipped high-risk read methods: `{report['selection']['skipped_high_risk_read_methods']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Method | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}"
            if result["status"] == "FAIL":
                note = details.get("error", "")[:180]
            elif "transport_error" in details:
                note = f"transport {details.get('transport_error_type')}: {details.get('transport_error', '')[:140]}"
            lines.append(f"| {result['status']} | `{result['fqmn']}` | {result['elapsed_ms']} | {note.replace('|', '\\|')} |")
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
    parser.add_argument("--catalog", type=Path, default=repo_root / "docs/api-audit/grpc-api-catalog.csv")
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--service", action="append", help="Limit to service name or fully qualified service.")
    parser.add_argument("--method", action="append", help="Limit to method name or fully qualified method.")
    parser.add_argument("--max-methods", type=int, default=0)
    parser.add_argument("--max-stream-pages", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--include-high-risk", action="store_true")
    parser.add_argument("--include-fixture-needed", action="store_true", help="Also test read methods that direct gRPC marked as fixture-needed.")
    parser.add_argument("--include-server-streams", action="store_true", help="Also test server-streaming methods over HTTP /grpc.")
    parser.add_argument("--skip-http", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    sweep = HttpGrpcSweep(args)
    report = sweep.run()
    print("Summary:", report["summary"])
    return 1 if report["summary"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
