#!/usr/bin/env python3
"""Fixture-driven archive search smoke checks."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def search_modes() -> list[str]:
    return [
        "lpr",
        "face",
        "vmda",
        "heatmap",
        "build_heatmap",
        "stranger",
        "legacy_auto",
        "legacy_vmda",
        "legacy_heatmap",
        "face_appearance_rate",
    ]


def default_vmda_query() -> str:
    return (
        "figure fZone=polygon(0,0,1,0,1,1,0,1); "
        "set r = group[obj=vmda_object] { res = or(fZone((obj.left + obj.right) / 2, obj.bottom)) }; "
        "result = r.res;"
    )


def axxon_ts(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S.%f")


def build_execute_heatmap_query_request(
    heatmap_pb2: Any,
    *,
    camera_id: str,
    begin: str,
    end: str,
    query: str,
) -> Any:
    return heatmap_pb2.ExecuteHeatmapQueryRequest(
        camera_ID=camera_id,
        dt_posix_start_time=begin,
        dt_posix_end_time=end,
        query=query,
    )


def build_build_heatmap_request(
    heatmap_pb2: Any,
    primitive_pb2: Any,
    *,
    builder_ap: str,
    camera_id: str,
    begin: str,
    end: str,
    query: str,
    image_width: int,
    image_height: int,
    mask_width: int,
    mask_height: int,
) -> Any:
    return heatmap_pb2.BuildHeatmapRequest(
        access_point=builder_ap,
        camera_ID=camera_id,
        dt_posix_start_time=begin,
        dt_posix_end_time=end,
        query=query,
        mask_size=primitive_pb2.SizeInt(width=mask_width, height=mask_height),
        result_type=heatmap_pb2.RESULT_TYPE_IMAGE,
        image_size=primitive_pb2.SizeInt(width=image_width, height=image_height),
    )


def build_face_appearance_rate_body(image_bytes: bytes) -> dict[str, str]:
    return {"image": base64.b64encode(image_bytes).decode("ascii")}


class ArchiveSearchSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.inventory: dict[str, Any] = {}
        self.node_name = ""
        self.fixtures: dict[str, Any] = {}
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        self.client.authenticate_grpc()
        if any(mode.startswith("legacy_") or mode in {"face", "stranger", "face_appearance_rate"} for mode in self.selected_modes()):
            self.client.authenticate_http_grpc()
        self.inventory = self.client.load_inventory()
        nodes = self.inventory.get("nodes", [])
        self.node_name = self.args.node or (nodes[0].get("node_name") if nodes else self.args.tls_cn)
        camera_query = self.args.camera or ("Face" if any(mode in {"face", "stranger", "face_appearance_rate"} for mode in self.selected_modes()) else None)
        self.fixtures = {
            "camera_ap": self.camera_access_point(camera_query),
            "vmda_endpoint": self.vmda_endpoint(),
            "legacy_vmda_endpoint": self.legacy_vmda_endpoint(),
            "heatmap_builder_ap": self.heatmap_builder_access_point(),
            "range": self.time_range_summary(),
        }

    def selected_modes(self) -> list[str]:
        if not self.args.mode:
            return search_modes()
        wanted = set(self.args.mode)
        return [mode for mode in search_modes() if mode in wanted]

    def time_range(self) -> Any:
        primitive_pb2 = self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        end = dt.datetime.now(dt.UTC)
        begin = end - dt.timedelta(hours=self.args.hours)
        return primitive_pb2.TimeRange(begin_time=axxon_ts(begin), end_time=axxon_ts(end))

    def time_range_summary(self) -> dict[str, str]:
        end = dt.datetime.now(dt.UTC)
        begin = end - dt.timedelta(hours=self.args.hours)
        return {"begin": axxon_ts(begin), "end": axxon_ts(end)}

    def camera_access_point(self, query: str | None) -> str:
        cameras = self.inventory.get("cameras", [])
        if not query:
            camera = next((item for item in cameras if item.get("access_point")), {})
            return camera.get("access_point", "")
        key = query.casefold()
        for camera in cameras:
            labels = [
                str(camera.get("display_id", "")),
                str(camera.get("display_name", "")),
                str(camera.get("access_point", "")),
            ]
            if any(key in label.casefold() for label in labels):
                return camera.get("access_point", "")
        return ""

    def vmda_endpoint(self) -> str:
        endpoints = [
            item.get("access_point", "")
            for item in self.inventory.get("components", [])
            if str(item.get("access_point", "")).endswith("/SourceEndpoint.vmda")
        ]
        return next((item for item in endpoints if "AVDetector.1" in item), endpoints[0] if endpoints else "")

    def legacy_vmda_endpoint(self) -> str:
        endpoints = [
            item.get("access_point", "")
            for item in self.inventory.get("components", [])
            if str(item.get("access_point", "")).endswith("/SourceEndpoint.vmda")
        ]
        return endpoints[0] if endpoints else ""

    def heatmap_builder_access_point(self) -> str:
        for item in self.inventory.get("components", []):
            access_point = str(item.get("access_point", ""))
            if "/HeatMapBuilder" in access_point:
                return access_point
        if self.node_name:
            return f"hosts/{self.node_name}/HeatMapBuilder.0/HeatMapBuilder"
        return ""

    def image_fixture_summary(self, path: str | None) -> dict[str, Any] | None:
        if not path:
            return None
        data = Path(path).read_bytes()
        return {"path": str(Path(path).name), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def run_lpr(self) -> dict[str, Any]:
        event_pb2 = self.client.import_module("axxonsoft.bl.events.EventHistory_pb2")
        events = self.client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
        request = event_pb2.ReadLprEventsRequest(
            range=self.time_range(),
            limit=max(1, self.args.limit),
            descending=True,
            search_predicate=self.args.predicate or "",
            node_descriptions=[event_pb2.NodeDescription(node_name=self.node_name)],
        )
        if self.fixtures.get("camera_ap"):
            request.filters.filters.append(event_pb2.LprSearchFilter(subjects=[self.fixtures["camera_ap"]]))
        rows = []
        for page in events.ReadLprEvents(request, timeout=self.args.timeout):
            data = self.client.message_to_dict(page)
            rows.extend(data.get("items", []))
            if len(rows) >= self.args.limit:
                break
        return {
            "status": "PASS",
            "details": {
                "items": len(rows),
                "predicate_supplied": bool(self.args.predicate),
                "camera_ap": self.fixtures.get("camera_ap", ""),
                "shape": self.client.shape(rows[:1]),
            },
        }

    def run_vmda(self) -> dict[str, Any]:
        endpoint = self.fixtures.get("vmda_endpoint", "")
        if not endpoint:
            return {"status": "SKIP", "details": {"reason": "missing VMDA endpoint"}}
        vmda_pb2 = self.client.import_module("axxonsoft.bl.vmda.VMDA_pb2")
        vmda = self.client.stub_from_proto("axxonsoft/bl/vmda/VMDA.proto", "VMDAService")
        response = vmda.EnumerateSchemes(vmda_pb2.EnumerateSchemesRequest(access_point=endpoint), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        return {
            "status": "PASS",
            "details": {"endpoint": endpoint, "scheme_count": len(data.get("cs_IDs", [])), "shape": self.client.shape(data)},
        }

    def run_heatmap(self) -> dict[str, Any]:
        endpoint = self.fixtures.get("vmda_endpoint", "")
        if not endpoint:
            return {"status": "SKIP", "details": {"reason": "missing VMDA endpoint"}}
        heatmap_pb2 = self.client.import_module("axxonsoft.bl.heatmap.HeatMap_pb2")
        heatmap = self.client.stub_from_proto("axxonsoft/bl/heatmap/HeatMap.proto", "HeatMapService")
        time_range = self.fixtures["range"]
        request = build_execute_heatmap_query_request(
            heatmap_pb2,
            camera_id=endpoint,
            begin=time_range["begin"],
            end=time_range["end"],
            query=self.args.heatmap_query or default_vmda_query(),
        )
        pages = []
        for page in heatmap.ExecuteHeatmapQuery(request, timeout=self.args.timeout):
            data = self.client.message_to_dict(page)
            pages.append(data)
            if len(pages) >= self.args.limit:
                break
        return {
            "status": "PASS" if pages else "WARN",
            "details": {
                "endpoint": endpoint,
                "pages": len(pages),
                "heatmap_builder_ap": self.fixtures.get("heatmap_builder_ap", ""),
                "query_supplied": bool(self.args.heatmap_query),
                "shape": self.client.shape(pages[:1]),
            },
        }

    def run_build_heatmap(self) -> dict[str, Any]:
        endpoint = self.fixtures.get("vmda_endpoint", "")
        builder_ap = self.fixtures.get("heatmap_builder_ap", "")
        if not endpoint:
            return {"status": "SKIP", "details": {"reason": "missing VMDA endpoint"}}
        if not builder_ap:
            return {"status": "SKIP", "details": {"reason": "missing HeatMapBuilder access point"}}
        heatmap_pb2 = self.client.import_module("axxonsoft.bl.heatmap.HeatMap_pb2")
        primitive_pb2 = self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        heatmap = self.client.stub_from_proto("axxonsoft/bl/heatmap/HeatMap.proto", "HeatMapService")
        time_range = self.fixtures["range"]
        request = build_build_heatmap_request(
            heatmap_pb2,
            primitive_pb2,
            builder_ap=builder_ap,
            camera_id=endpoint,
            begin=time_range["begin"],
            end=time_range["end"],
            query=self.args.heatmap_query or default_vmda_query(),
            image_width=max(1, self.args.heatmap_image_width),
            image_height=max(1, self.args.heatmap_image_height),
            mask_width=max(1, self.args.heatmap_mask_width),
            mask_height=max(1, self.args.heatmap_mask_height),
        )
        response = heatmap.BuildHeatmap(request, timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        image_bytes = bytes(response.image_data)
        return {
            "status": "PASS" if response.result and image_bytes else "WARN",
            "details": {
                "builder_ap": builder_ap,
                "endpoint": endpoint,
                "result": bool(response.result),
                "heatmap_cells": len(response.heatmap),
                "image_bytes": len(image_bytes),
                "image_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes else "",
                "query_supplied": bool(self.args.heatmap_query),
                "mask_size": {
                    "width": max(1, self.args.heatmap_mask_width),
                    "height": max(1, self.args.heatmap_mask_height),
                },
                "image_size": {
                    "width": max(1, self.args.heatmap_image_width),
                    "height": max(1, self.args.heatmap_image_height),
                },
                "shape": self.client.shape(data),
            },
        }

    def run_fixture_mode(self, mode: str) -> dict[str, Any]:
        image = self.image_fixture_summary(self.args.face_image)
        if mode in {"face", "stranger"} and image is None:
            return {"status": "SKIP", "details": {"reason": "missing --face-image fixture"}}
        return {"status": "SKIP", "details": {"reason": "mode requires additional object fixture", "image": image}}

    def run_legacy_search(self, mode: str) -> dict[str, Any]:
        endpoint = self.fixtures.get("legacy_vmda_endpoint") or self.fixtures.get("vmda_endpoint", "")
        if not endpoint:
            return {"status": "SKIP", "details": {"reason": "missing VMDA endpoint"}}
        kind = mode.removeprefix("legacy_")
        legacy_endpoint = self.legacy_search_endpoint(kind, endpoint)
        query = self.legacy_search_body(kind, legacy_endpoint)
        start_response = self.client.http_request(
            "POST",
            f"/search/{kind}/{legacy_endpoint}/past/future",
            query["body"],
            bearer=True,
            query=query["query"],
            headers=query["headers"],
            raw_body=True,
            max_bytes=1024,
        )
        location = start_response.get("headers", {}).get("Location", "")
        if start_response.get("status") != 202 or not location:
            return {
                "status": "WARN",
                "details": {
                    "start_status": start_response.get("status"),
                    "location_received": bool(location),
                    "content_type": start_response.get("content_type", ""),
                },
            }
        result_response: dict[str, Any] = {}
        delete_response: dict[str, Any] = {}
        result_path = f"{location}/result" if kind == "heatmap" else f"{location}/result?limit={max(1, self.args.limit)}&offset=0"
        try:
            for attempt in range(max(1, self.args.poll_attempts)):
                result_response = self.client.http_request(
                    "GET",
                    result_path,
                    bearer=True,
                    raw_body=kind == "heatmap",
                    max_bytes=self.args.max_bytes,
                )
                if result_response.get("status") != 206:
                    break
                if attempt + 1 < self.args.poll_attempts:
                    time.sleep(self.args.poll_delay)
        finally:
            try:
                delete_response = self.client.http_request("DELETE", location, bearer=True, raw_body=True, max_bytes=1024)
            except Exception as exc:
                delete_response = {"status": 0, "error": str(exc)[:300]}
        result_body = result_response.get("body")
        event_count = len(result_body.get("events", [])) if isinstance(result_body, dict) else 0
        result_status = result_response.get("status")
        result_ok = (
            (result_status == 200 or (result_status == 206 and event_count > 0))
            and (kind != "heatmap" or result_response.get("size", 0) > 0)
        )
        delete_ok = 200 <= int(delete_response.get("status", 0)) < 300
        return {
            "status": "PASS" if result_ok and delete_ok else "WARN",
            "details": {
                "kind": kind,
                "start_status": start_response.get("status"),
                "location_received": True,
                "result_status": result_response.get("status"),
                "result_content_type": result_response.get("content_type", ""),
                "result_size": result_response.get("size", 0),
                "events": event_count,
                "result_shape": self.client.shape(result_response.get("body")),
                "delete_status": delete_response.get("status"),
                "poll_attempts": attempt + 1 if "attempt" in locals() else 0,
            },
        }

    def legacy_search_endpoint(self, kind: str, vmda_endpoint: str) -> str:
        if kind == "auto":
            detector = self.lpr_event_supplier()
            if detector:
                return detector.removeprefix("hosts/")
        if kind in {"face", "stranger"}:
            detector = self.face_event_supplier()
            if detector:
                return detector.removeprefix("hosts/")
        return vmda_endpoint.removeprefix("hosts/")

    def lpr_event_supplier(self) -> str:
        lpr_names = ("Lpr", "License", "plateRecognized")
        for item in self.inventory.get("components", []):
            access_point = str(item.get("access_point", ""))
            if not access_point.endswith("/EventSupplier"):
                continue
            haystack = json.dumps(item)
            if any(name.casefold() in haystack.casefold() for name in lpr_names):
                return access_point
        return ""

    def face_event_supplier(self) -> str:
        face_names = ("TvaFaceDetector", "Face detector", "faceAppeared", "DG_FACE_DETECTOR")
        for camera in self.inventory.get("cameras", []):
            for detector in camera.get("detectors", []):
                access_point = str(detector.get("accessPoint") or detector.get("access_point") or "")
                haystack = json.dumps(detector)
                if access_point.endswith("/EventSupplier") and any(name.casefold() in haystack.casefold() for name in face_names):
                    return access_point
        for item in self.inventory.get("components", []):
            access_point = str(item.get("access_point", ""))
            if not access_point.endswith("/EventSupplier"):
                continue
            haystack = json.dumps(item)
            if any(name.casefold() in haystack.casefold() for name in face_names):
                return access_point
        camera_ap = self.fixtures.get("camera_ap", "")
        if self.client.http_token and camera_ap:
            response = self.client.http_request(
                "GET",
                f"/camera/list?filter={camera_ap.removeprefix('hosts/')}",
                bearer=True,
                max_bytes=65536,
            )
            for camera in response.get("body", {}).get("cameras", []):
                for detector in camera.get("detectors", []):
                    access_point = str(detector.get("accessPoint") or detector.get("access_point") or "")
                    haystack = json.dumps(detector)
                    if access_point.endswith("/EventSupplier") and any(name.casefold() in haystack.casefold() for name in face_names):
                        return access_point
        return ""

    def run_face_appearance_rate(self) -> dict[str, Any]:
        if not self.args.face_image:
            return {"status": "SKIP", "details": {"reason": "missing --face-image fixture"}}
        detector = self.face_event_supplier()
        if not detector:
            return {"status": "SKIP", "details": {"reason": "missing face detector EventSupplier"}}
        image_bytes = Path(self.args.face_image).read_bytes()
        query = f"accuracy={self.args.face_accuracy:g}" if self.args.face_accuracy is not None else ""
        response = self.client.http_request(
            "POST",
            f"/faceAppearanceRate/{detector.removeprefix('hosts/')}/past/future",
            build_face_appearance_rate_body(image_bytes),
            bearer=True,
            query=query,
            max_bytes=4096,
        )
        body = response.get("body")
        ok = response.get("status") == 200 and isinstance(body, dict) and "rate" in body
        return {
            "status": "PASS" if ok else "WARN",
            "details": {
                "detector": detector,
                "status": response.get("status"),
                "content_type": response.get("content_type", ""),
                "image": self.image_fixture_summary(self.args.face_image),
                "shape": self.client.shape(body),
            },
        }

    def legacy_search_body(self, kind: str, legacy_endpoint: str = "") -> dict[str, Any]:
        query_parts = []
        headers: dict[str, str] = {}
        body: Any = {}
        if kind == "vmda" or kind == "heatmap":
            body = {"query": self.args.heatmap_query or default_vmda_query()}
        elif kind == "auto" and self.args.predicate:
            body = {"plate": self.args.predicate}
        elif kind == "face":
            if self.args.face_accuracy is not None:
                query_parts.append(f"accuracy={self.args.face_accuracy:g}")
            if self.args.face_image:
                body = build_face_appearance_rate_body(Path(self.args.face_image).read_bytes())
                if legacy_endpoint:
                    body["sources"] = [f"hosts/{legacy_endpoint}"]
            else:
                body = None
        elif kind == "stranger":
            if self.args.face_accuracy is not None:
                query_parts.append(f"accuracy={self.args.face_accuracy:g}")
            if self.args.stranger_threshold is not None:
                query_parts.append(f"threshold={self.args.stranger_threshold:g}")
            if self.args.stranger_op:
                query_parts.append(f"op={self.args.stranger_op}")
            body = None
        return {"body": body, "query": "&".join(query_parts), "headers": headers}

    def invoke(self, mode: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            if mode == "lpr":
                outcome = self.run_lpr()
            elif mode == "vmda":
                outcome = self.run_vmda()
            elif mode == "heatmap":
                outcome = self.run_heatmap()
            elif mode == "build_heatmap":
                outcome = self.run_build_heatmap()
            elif mode in {"legacy_auto", "legacy_vmda", "legacy_heatmap"}:
                outcome = self.run_legacy_search(mode)
            elif mode in {"face", "stranger"}:
                outcome = self.run_legacy_search(mode)
            elif mode == "face_appearance_rate":
                outcome = self.run_face_appearance_rate()
            else:
                outcome = self.run_fixture_mode(mode)
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            outcome = {"status": "WARN", "details": details}
        return {
            "mode": mode,
            "status": outcome["status"],
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": outcome.get("details", {}),
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for mode in self.selected_modes():
            self.results.append(self.invoke(mode))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "SKIP": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "username": self.args.username, "password": "<redacted>"},
            "selection": {"modes": self.selected_modes(), "hours": self.args.hours, "limit": self.args.limit},
            "fixtures": self.fixtures,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"archive-search-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"archive-search-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "archive-search-smoke-latest.json"
        latest_md = self.args.report_dir / "archive-search-smoke-latest.md"
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
            "# Axxon One Archive Search Smoke",
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
        lines.extend(["", "## Results", "", "| Status | Mode | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = details.get("reason") or details.get("error")
            if not note and result["mode"] == "build_heatmap":
                note = f"result={details.get('result')} image_bytes={details.get('image_bytes', 0)}"
            if not note and "events" in details:
                note = f"events={details.get('events', 0)} result_status={details.get('result_status')}"
            if not note and result["mode"] == "face_appearance_rate":
                note = f"status={details.get('status')} shape={details.get('shape', {})}"
            if not note:
                note = f"items={details.get('items', details.get('scheme_count', 0))}"
            lines.append(f"| {result['status']} | `{result['mode']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:180]} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--mode", action="append", choices=search_modes())
    parser.add_argument("--camera")
    parser.add_argument("--node")
    parser.add_argument("--predicate", help="LPR search predicate. Value is never written to reports.")
    parser.add_argument("--face-image")
    parser.add_argument("--face-accuracy", type=float)
    parser.add_argument("--stranger-threshold", type=float)
    parser.add_argument("--stranger-op", choices=["lt", "gt"], default="")
    parser.add_argument("--heatmap-query", default="", help="Optional HeatMapService query string. Value is not written to reports.")
    parser.add_argument("--heatmap-image-width", type=int, default=64)
    parser.add_argument("--heatmap-image-height", type=int, default=48)
    parser.add_argument("--heatmap-mask-width", type=int, default=32)
    parser.add_argument("--heatmap-mask-height", type=int, default=24)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-bytes", type=int, default=1048576)
    parser.add_argument("--poll-attempts", type=int, default=5)
    parser.add_argument("--poll-delay", type=float, default=0.5)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    smoke = ArchiveSearchSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
