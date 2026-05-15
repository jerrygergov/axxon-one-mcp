#!/usr/bin/env python3
"""Read-only detail sweep for config, templates, maps, users, macros, and detectors."""

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


def read_groups() -> list[str]:
    return ["templates", "macros", "users", "maps", "detectors"]


class ConfigDetailSweep:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.inventory: dict[str, Any] = {}
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.inventory = self.client.load_inventory()

    def selected_groups(self) -> list[str]:
        if not self.args.group:
            return read_groups()
        wanted = set(self.args.group)
        return [group for group in read_groups() if group in wanted]

    def run_templates(self) -> dict[str, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stub = self.client.common_stubs()["config"]
        response = stub.ListTemplates(pb2.ListTemplatesRequest(view=pb2.ListTemplatesRequest.VIEW_MODE_STRIPPED), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        ids = [item.get("id", "") or item.get("template", {}).get("id", "") for item in data.get("items", [])]
        batch_shape = {}
        if ids:
            batch = stub.BatchGetTemplates(
                pb2.BatchGetTemplatesRequest(items=[pb2.BatchGetTemplatesRequest.Locator(id=ids[0])]),
                timeout=self.args.timeout,
            )
            batch_shape = self.client.shape(self.client.message_to_dict(batch))
        return {"count": len(data.get("items", [])), "shape": self.client.shape(data), "batch_shape": batch_shape}

    def run_macros(self) -> dict[str, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.logic.LogicService_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/logic/LogicService.proto", "LogicService")
        response = stub.ListMacros(pb2.ListMacrosRequest(view=pb2.ListMacrosRequest.VIEW_MODE_STRIPPED, page_size=50), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        stream_pages = 0
        stream_items = 0
        for page in stub.ListMacrosV2(pb2.ListMacrosRequest(view=pb2.ListMacrosRequest.VIEW_MODE_STRIPPED, page_size=50), timeout=self.args.timeout):
            stream_pages += 1
            stream_items += len(self.client.message_to_dict(page).get("items", []))
            if stream_pages >= 2:
                break
        config = self.client.message_to_dict(stub.GetConfig(pb2.GetConfigRequest(), timeout=self.args.timeout))
        return {
            "count": len(data.get("items", [])),
            "stream_pages": stream_pages,
            "stream_items": stream_items,
            "shape": self.client.shape(data),
            "config_shape": self.client.shape(config),
        }

    def run_users(self) -> dict[str, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.security.SecurityService_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/security/SecurityService.proto", "SecurityService")
        roles = self.client.message_to_dict(stub.ListRoles(pb2.ListRolesRequest(page_size=100), timeout=self.args.timeout))
        users = self.client.message_to_dict(stub.ListUsers(pb2.ListUsersRequest(page_size=100), timeout=self.args.timeout))
        return {
            "roles_count": len(roles.get("roles", [])),
            "users_count": len(users.get("users", [])),
            "roles_shape": self.client.shape(roles),
            "users_shape": self.client.shape(users),
        }

    def map_id_from(self, item: dict[str, Any]) -> str:
        return (
            item.get("meta", {}).get("map_id")
            or item.get("map_id")
            or item.get("id")
            or item.get("uid")
            or ""
        )

    def run_maps(self) -> dict[str, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.maps.MapService_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/maps/MapService.proto", "MapService")
        response = stub.ListMaps(pb2.ListMapsRequest(), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        ids = [self.map_id_from(item) for item in data.get("items", [])]
        ids = [item for item in ids if item]
        batch_shape: Any = {}
        image_shape: Any = {}
        if ids:
            batch = stub.BatchGetMaps(pb2.BatchGetMapsRequest(map_ids=ids[:1]), timeout=self.args.timeout)
            batch_shape = self.client.shape(self.client.message_to_dict(batch))
            try:
                image = stub.GetMapImage(pb2.GetMapImageRequest(map_id=ids[0]), timeout=self.args.timeout)
                image_shape = self.client.shape(self.client.message_to_dict(image))
            except Exception as exc:
                image_shape = {"warning": exc.__class__.__name__}
        return {"count": len(data.get("items", [])), "shape": self.client.shape(data), "batch_shape": batch_shape, "image_shape": image_shape}

    def run_detectors(self) -> dict[str, Any]:
        components = self.inventory.get("components", [])
        detectors = [
            item for item in components
            if "AVDetector" in item.get("access_point", "") or "Detector" in item.get("type", "") or "Detector" in item.get("display_name", "")
        ]
        vmda = [item for item in components if str(item.get("access_point", "")).endswith("/SourceEndpoint.vmda")]
        return {
            "detector_like_components": len(detectors),
            "vmda_endpoints": len(vmda),
            "sample_shape": self.client.shape(detectors[:1]),
        }

    def invoke(self, group: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            method = getattr(self, f"run_{group}")
            details = method()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "WARN"
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def run(self) -> dict[str, Any]:
        self.setup()
        for group in self.selected_groups():
            self.results.append(self.invoke(group))
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
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "username": self.args.username, "password": "<redacted>"},
            "selection": {"groups": self.selected_groups()},
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"config-detail-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"config-detail-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "config-detail-sweep-latest.json"
        latest_md = self.args.report_dir / "config-detail-sweep-latest.md"
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
            "# Axxon One Configuration Detail Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = details.get("error") or f"keys={len(details)}"
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:180]} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--group", action="append", choices=read_groups())
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    sweep = ConfigDetailSweep(parse_args())
    report = sweep.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
