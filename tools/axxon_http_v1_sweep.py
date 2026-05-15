#!/usr/bin/env python3
"""Sweep safe Axxon One /v1 HTTP endpoints from proto annotations."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, config_from_args
from axxon_readonly_sweep import ReadOnlySweep


SAFE_POST_READ_PREFIXES = (
    "Get",
    "List",
    "BatchGet",
    "Search",
    "Find",
    "Read",
    "Check",
    "Is",
    "Enumerate",
)


class HttpV1Sweep:
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

    def load_endpoints(self) -> list[dict[str, str]]:
        with self.args.catalog.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        selected: list[dict[str, str]] = []
        service_filter = set(self.args.service or [])
        method_filter = set(self.args.method or [])
        for row in rows:
            fq_service = f"{row['package']}.{row['service']}"
            fqmn = row["fqmn"]
            if service_filter and row["service"] not in service_filter and fq_service not in service_filter:
                continue
            if method_filter and row["method"] not in method_filter and fqmn not in method_filter:
                continue
            if row["safety"] == "mutating":
                continue
            if not self.args.include_high_risk and self.grpc_fixture.should_skip(row):
                continue
            for http in self.parse_http(row["http"]):
                if not self.is_safe_endpoint(row, http):
                    continue
                if not self.args.include_fixture_needed and row["live_status"].startswith("tested-warn"):
                    continue
                endpoint = dict(row)
                endpoint.update(http)
                selected.append(endpoint)
        return selected[: self.args.max_methods or None]

    def is_safe_endpoint(self, row: dict[str, str], http: dict[str, str]) -> bool:
        if http["verb"] == "GET":
            return row["safety"] == "read" or (self.args.include_review_get and row["safety"] == "review")
        if self.args.get_only:
            return False
        if http["verb"] != "POST":
            return False
        if row["safety"] not in {"read", "review"}:
            return False
        return row["method"].startswith(SAFE_POST_READ_PREFIXES)

    def parse_http(self, value: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for chunk in value.split(";"):
            text = chunk.strip()
            if not text:
                continue
            verb, _, path = text.partition(" ")
            if not path:
                continue
            items.append({"verb": verb, "path": path})
        return items

    def request_data_for(self, row: dict[str, str]) -> dict[str, Any]:
        pb2_module, _stub = self.grpc_fixture.import_for_row(row)
        request = self.grpc_fixture.request_for(row, pb2_module)
        return self.client.to_json_data(request)

    def query_string(self, data: dict[str, Any]) -> str:
        return self.client.query_string(data)

    def query_value(self, value: Any) -> str:
        return self.client.query_value(value)

    def http_request(
        self,
        method: str,
        path: str,
        body: Any = None,
        basic: bool = False,
        bearer: bool = False,
        query: str = "",
    ) -> dict[str, Any]:
        return self.client.http_request(
            method,
            path,
            body=body,
            basic=basic,
            bearer=bearer,
            query=query,
            max_items=self.args.max_stream_pages,
        )

    def invoke(self, row: dict[str, str]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            data = self.request_data_for(row)
            query = self.query_string(data)
            if row["verb"] == "GET":
                response = self.http_request("GET", row["path"], bearer=True, query=query)
            else:
                response = self.http_request(row["verb"], row["path"], body=data, bearer=True)
            details = {
                "http_status": response["status"],
                "content_type": response["content_type"],
                "size": response["size"],
                "request_keys": sorted(data.keys()),
                "shape": self.shape(response.get("body")),
            }
            status = "PASS" if 200 <= response["status"] < 300 else "WARN"
            return self.result(row, status, details, start)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            return self.result(row, "FAIL", details, start)

    def shape(self, value: Any) -> Any:
        return self.client.shape(value)

    def result(self, row: dict[str, str], status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {
            "fqmn": row["fqmn"],
            "package": row["package"],
            "service": row["service"],
            "method": row["method"],
            "verb": row["verb"],
            "path": row["path"],
            "proto": row["proto"],
            "safety": row["safety"],
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        selected = self.load_endpoints()
        for row in selected:
            self.results.append(self.invoke(row))
        report = self.report(len(selected))
        self.write_report(report)
        return report

    def report(self, selected_count: int) -> dict[str, Any]:
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
                "selected_endpoints": selected_count,
                "timeout_seconds": self.args.timeout,
                "include_review_get": self.args.include_review_get,
                "include_fixture_needed": self.args.include_fixture_needed,
                "get_only": self.args.get_only,
            },
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"http-v1-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"http-v1-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "http-v1-sweep-latest.json"
        latest_md = self.args.report_dir / "http-v1-sweep-latest.md"
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
            "# Axxon One HTTP /v1 Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Selected endpoints: `{report['selection']['selected_endpoints']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Endpoint | Method | ms | Notes |", "| --- | --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = f"HTTP {details.get('http_status')} {details.get('content_type', '')}".replace("|", "\\|")
            if result["status"] == "FAIL":
                note = details.get("error", "")[:180].replace("|", "\\|")
            endpoint = f"{result['verb']} {result['path']}"
            lines.append(f"| {result['status']} | `{endpoint}` | `{result['fqmn']}` | {result['elapsed_ms']} | {note} |")
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
    parser.add_argument("--include-fixture-needed", action="store_true", help="Also test endpoints whose direct gRPC status is fixture-needed.")
    parser.add_argument("--include-review-get", action="store_true", help="Also test GET endpoints classified as review.")
    parser.add_argument("--get-only", action="store_true", help="Disable safe POST/read endpoint testing.")
    parser.add_argument("--skip-http", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    sweep = HttpV1Sweep(args)
    report = sweep.run()
    print("Summary:", report["summary"])
    return 1 if report["summary"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
