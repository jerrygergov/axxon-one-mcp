#!/usr/bin/env python3
"""Discover read-only fixtures for API-book gap closure."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import socket
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def fixture_types() -> list[str]:
    return [
        "ptz",
        "control_panel",
        "water_level",
        "export_agent",
        "map",
        "template",
        "detector",
        "client_http",
        "embeddable_host",
        "rtsp_playback",
    ]


def export_agent_units_from_list_units(data: dict[str, Any]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for unit in data.get("units", []):
        for child in unit.get("units", []):
            if child.get("type") == "MMExportAgent":
                agents.append(child)
    return agents


def embeddable_signature(*, url: str, status: int, content_type: str, size: int, text_prefix: str) -> dict[str, Any]:
    lowered = text_prefix.casefold()
    url_lowered = url.casefold()
    return {
        "url": url,
        "http_status": status,
        "content_type": content_type,
        "bytes": size,
        "mentions_component": "component" in lowered or url_lowered.endswith("/embedded.html"),
        "mentions_video": "video" in lowered,
        "mentions_embed": "embed" in lowered or "iframe" in lowered or "embedded.js" in lowered,
    }


class FixtureDiscovery:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.inventory: dict[str, Any] = {}
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.inventory = self.client.load_inventory()

    def selected_types(self) -> list[str]:
        if not self.args.fixture_type:
            return fixture_types()
        wanted = set(self.args.fixture_type)
        return [item for item in fixture_types() if item in wanted]

    def components(self) -> list[dict[str, Any]]:
        return self.inventory.get("components", [])

    def discover_ptz(self) -> dict[str, Any]:
        telemetry = [
            item for item in self.components()
            if "/Telemetry" in item.get("access_point", "") or "telemetry" in json.dumps(item).casefold()
        ]
        return {"count": len(telemetry), "items": [self.component_summary(item) for item in telemetry[:10]]}

    def discover_control_panel(self) -> dict[str, Any]:
        found = []
        try:
            pb2 = self.client.import_module("axxonsoft.bl.domain.Domain_pb2")
            domain = self.client.common_stubs()["domain"]
            for page in domain.ListControlPanels(pb2.ListControlPanelsRequest(page_size=50), timeout=self.args.timeout):
                found.extend(self.client.message_to_dict(page).get("items", []))
                if len(found) >= 50:
                    break
        except Exception as exc:
            return {"count": 0, "warning": exc.__class__.__name__}
        return {"count": len(found), "shape": self.client.shape(found[:1])}

    def discover_water_level(self) -> dict[str, Any]:
        water = [
            item for item in self.components()
            if "water" in json.dumps(item).casefold()
        ]
        return {"count": len(water), "items": [self.component_summary(item) for item in water[:10]]}

    def discover_export_agent(self) -> dict[str, Any]:
        export_like = [
            item for item in self.components()
            if "export" in json.dumps(item).casefold()
        ]
        try:
            pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
            config = self.client.common_stubs()["config"]
            host_uid = f"hosts/{self.client.node_name()}"
            data = self.client.message_to_dict(
                config.ListUnits(pb2.ListUnitsRequest(unit_uids=[host_uid], display_mode=0), timeout=self.args.timeout)
            )
            export_like.extend(export_agent_units_from_list_units(data))
        except Exception as exc:
            return {
                "count": len(export_like),
                "warning": exc.__class__.__name__,
                "items": [self.component_summary(item) for item in export_like[:10]],
            }
        return {"count": len(export_like), "items": [self.component_summary(item) for item in export_like[:10]]}

    def discover_map(self) -> dict[str, Any]:
        try:
            pb2 = self.client.import_module("axxonsoft.bl.maps.MapService_pb2")
            maps = self.client.stub_from_proto("axxonsoft/bl/maps/MapService.proto", "MapService")
            data = self.client.message_to_dict(maps.ListMaps(pb2.ListMapsRequest(), timeout=self.args.timeout))
        except Exception as exc:
            return {"count": 0, "warning": exc.__class__.__name__}
        ids = [self.map_id(item) for item in data.get("items", [])]
        ids = [item for item in ids if item]
        image_shape: Any = {}
        if ids:
            try:
                image = maps.GetMapImage(pb2.GetMapImageRequest(map_id=ids[0]), timeout=self.args.timeout)
                image_shape = self.client.shape(self.client.message_to_dict(image))
            except Exception as exc:
                image_shape = {"warning": exc.__class__.__name__}
        return {"count": len(data.get("items", [])), "ids": ids[:10], "image_shape": image_shape}

    def discover_template(self) -> dict[str, Any]:
        try:
            pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
            config = self.client.common_stubs()["config"]
            data = self.client.message_to_dict(config.ListTemplates(pb2.ListTemplatesRequest(), timeout=self.args.timeout))
        except Exception as exc:
            return {"count": 0, "warning": exc.__class__.__name__}
        return {"count": len(data.get("items", [])), "shape": self.client.shape(data)}

    def discover_detector(self) -> dict[str, Any]:
        detectors = [
            item for item in self.components()
            if "AVDetector" in item.get("access_point", "") or "detector" in json.dumps(item).casefold()
        ]
        vmda = [item for item in self.components() if str(item.get("access_point", "")).endswith("/SourceEndpoint.vmda")]
        return {
            "detector_like_components": len(detectors),
            "vmda_endpoints": len(vmda),
            "items": [self.component_summary(item) for item in detectors[:15]],
        }

    def discover_client_http(self) -> dict[str, Any]:
        targets = [
            {"host": "127.0.0.1", "port": 8888, "purpose": "local Axxon Client HTTP API"},
            {"host": self.args.host, "port": 8888, "purpose": "remote host Client HTTP API"},
        ]
        checks = [self.socket_probe(item["host"], item["port"], item["purpose"]) for item in targets]
        reachable = [item for item in checks if item["reachable"]]
        return {"count": len(reachable), "checks": checks}

    def discover_embeddable_host(self) -> dict[str, Any]:
        component_hosts = []
        for path in ["/embedded.html", "/"]:
            url = self.args.http_url.rstrip("/") + path
            try:
                response = self.client.http_request("GET", path, raw_body=True, max_bytes=65536)
                body = response.get("body", {})
                text_prefix = str(body.get("text_prefix", ""))
                component_hosts.append(
                    embeddable_signature(
                        url=url,
                        status=int(response.get("status", 0)),
                        content_type=str(response.get("content_type", "")),
                        size=int(response.get("size", 0)),
                        text_prefix=text_prefix,
                    )
                )
            except Exception as exc:
                component_hosts.append({"url": url, "warning": exc.__class__.__name__})
        count = sum(
            1
            for item in component_hosts
            if item.get("http_status") == 200
            and item.get("mentions_component")
            and (item.get("mentions_video") or item.get("mentions_embed"))
        )
        return {"count": count, "checks": component_hosts}

    def discover_rtsp_playback(self) -> dict[str, Any]:
        checks = [
            self.socket_probe(self.args.host, 554, "RTSP/RTP UDP or TCP endpoint"),
            self.socket_probe(self.args.host, 8554, "RTSP over HTTP/TCP endpoint from descriptor"),
        ]
        rtsp_stat: dict[str, Any] = {}
        try:
            self.client.authenticate_http_grpc()
            stat = self.client.http_request("GET", "/rtsp/stat", bearer=True, raw_body=True, max_bytes=65536)
            rtsp_stat = {
                "http_status": stat.get("status"),
                "content_type": stat.get("content_type", ""),
                "bytes": stat.get("size", 0),
                "shape": self.client.shape(stat.get("body")),
            }
        except Exception as exc:
            rtsp_stat = {"warning": exc.__class__.__name__}
        count = sum(1 for item in checks if item["reachable"])
        if rtsp_stat.get("http_status") == 200:
            count += 1
        return {"count": count, "socket_checks": checks, "rtsp_stat": rtsp_stat}

    def socket_probe(self, host: str, port: int, purpose: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=min(2.0, self.args.timeout)):
                reachable = True
                error = ""
        except OSError as exc:
            reachable = False
            error = exc.__class__.__name__
        return {
            "host": host,
            "port": port,
            "purpose": purpose,
            "reachable": reachable,
            "error": error,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
        }

    def component_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "access_point": item.get("access_point") or item.get("uid", ""),
            "display_name": item.get("display_name", ""),
            "type": item.get("type", ""),
        }

    def map_id(self, item: dict[str, Any]) -> str:
        return item.get("meta", {}).get("map_id") or item.get("map_id") or item.get("id") or item.get("uid") or ""

    def invoke(self, fixture_type: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            details = getattr(self, f"discover_{fixture_type}")()
            found_count = details.get("count", details.get("detector_like_components", 0))
            status = "FOUND" if found_count else "MISSING"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "WARN"
        return {
            "fixture_type": fixture_type,
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for fixture_type in self.selected_types():
            self.results.append(self.invoke(fixture_type))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"FOUND": 0, "MISSING": 0, "WARN": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "username": self.args.username, "password": "<redacted>"},
            "selection": {"fixture_types": self.selected_types()},
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"fixture-discovery-{stamp}.json"
        md_path = self.args.report_dir / f"fixture-discovery-{stamp}.md"
        latest_json = self.args.report_dir / "fixture-discovery-latest.json"
        latest_md = self.args.report_dir / "fixture-discovery-latest.md"
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
            "# Axxon One Fixture Discovery",
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
        lines.extend(["", "## Results", "", "| Status | Fixture | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = details.get("warning") or details.get("error") or f"count={details.get('count', details.get('detector_like_components', 0))}"
            lines.append(f"| {result['status']} | `{result['fixture_type']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:180]} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--fixture-type", action="append", choices=fixture_types())
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    discovery = FixtureDiscovery(parse_args())
    report = discovery.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
