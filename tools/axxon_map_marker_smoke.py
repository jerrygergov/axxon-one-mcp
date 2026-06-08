#!/usr/bin/env python3
"""Controlled Axxon One map and marker lifecycle smoke test."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-map-marker-smoke"

# 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


class MapMarkerSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_map_id = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_grpc()

    @property
    def maps_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.maps.MapService_pb2")

    @property
    def primitives_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")

    @property
    def stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/maps/MapService.proto", "MapService")

    def list_maps(self) -> dict[str, Any]:
        response = self.stub.ListMaps(self.maps_pb2.ListMapsRequest(view=self.maps_pb2.VIEW_MODE_FULL), timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def create_map_request(self, map_id: str) -> Any:
        maps = self.maps_pb2
        primitive = self.primitives_pb2
        marker_component = self.args.marker_component or self.first_camera_access_point()
        return maps.ChangeMapsRequest(
            created=[
                maps.CreateMap(
                    id=map_id,
                    map=maps.Map(
                        name=f"codex-temp-map-{self.short_stamp()}",
                        type=maps.MAP_TYPE_RASTER,
                        position=primitive.Point(x=0.0, y=0.0),
                        zoom=1,
                        image_meta=maps.MapImageMeta(
                            file_name="codex-map.png",
                            mime_type="image/png",
                            size=primitive.Size(width=1.0, height=1.0),
                            name="codex-map.png",
                            size_bytes=len(PNG_1X1),
                        ),
                    ),
                    image_data=PNG_1X1,
                    markers=[
                        maps.Marker(
                            position=primitive.Point(x=0.50, y=0.50),
                            component_name=marker_component,
                            display_title=True,
                            camera_marker=maps.CameraMarker(video_on=False),
                            icon_scale=1.0,
                        )
                    ],
                )
            ]
        )

    def first_camera_access_point(self) -> str:
        inventory = self.client.load_inventory()
        for camera in inventory.get("cameras", []):
            access_point = camera.get("access_point")
            if access_point:
                return access_point
        return ""

    def change_maps(self, request: Any) -> dict[str, Any]:
        response = self.stub.ChangeMaps(request, timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def create_map(self) -> dict[str, Any]:
        self.created_map_id = f"codex-{uuid.uuid4()}"
        return self.change_maps(self.create_map_request(self.created_map_id))

    def batch_get(self, map_id: str | None = None) -> dict[str, Any]:
        response = self.stub.BatchGetMaps(self.maps_pb2.BatchGetMapsRequest(map_ids=[map_id or self.created_map_id]), timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def latest_map_etag(self) -> str:
        data = self.batch_get()
        items = data.get("items", [])
        if not items:
            raise RuntimeError(f"BatchGetMaps returned no map: {data}")
        etag = items[0].get("meta", {}).get("etag", "")
        if not etag:
            raise RuntimeError(f"BatchGetMaps returned no map etag: {items[0]}")
        return etag

    def update_map_name(self, etag: str) -> dict[str, Any]:
        maps = self.maps_pb2
        primitive = self.primitives_pb2
        return self.change_maps(
            maps.ChangeMapsRequest(
                updated=[
                    maps.UpdateMap(
                        etag=etag,
                        map_id=self.created_map_id,
                        map=maps.Map(
                            name=f"codex-temp-map-updated-{self.short_stamp()}",
                            type=maps.MAP_TYPE_RASTER,
                            position=primitive.Point(x=0.1, y=0.1),
                            zoom=2,
                        ),
                    )
                ]
            )
        )

    def get_image(self) -> dict[str, Any]:
        response = self.stub.GetMapImage(self.maps_pb2.GetMapImageRequest(map_id=self.created_map_id), timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        image = data.get("image", {})
        return {
            "meta": image.get("meta", {}),
            "data_b64_len": len(image.get("data", "")),
            "etag_len": len(image.get("etag", "")),
        }

    def get_markers(self) -> dict[str, Any]:
        response = self.stub.GetMarkers(self.maps_pb2.GetMarkersRequest(map_id=self.created_map_id), timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def update_marker(self) -> dict[str, Any]:
        maps = self.maps_pb2
        primitive = self.primitives_pb2
        component = self.args.marker_component or self.first_camera_access_point()
        response = self.stub.UpdateMarkers(
            maps.UpdateMarkersRequest(
                changed=[
                    maps.UpdateMarkers(
                        map_id=self.created_map_id,
                        updated=[
                            maps.Marker(
                                position=primitive.Point(x=0.25, y=0.75),
                                component_name=component,
                                display_title=False,
                                camera_marker=maps.CameraMarker(video_on=False),
                                icon_scale=1.25,
                            )
                        ],
                    )
                ]
            ),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def remove_marker(self) -> dict[str, Any]:
        maps = self.maps_pb2
        component = self.args.marker_component or self.first_camera_access_point()
        response = self.stub.UpdateMarkers(
            maps.UpdateMarkersRequest(changed=[maps.UpdateMarkers(map_id=self.created_map_id, removed=[component])]),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def remove_map(self) -> dict[str, Any]:
        if not self.created_map_id:
            return {"skipped": True}
        map_id = self.created_map_id
        body = self.change_maps(self.maps_pb2.ChangeMapsRequest(removed=[map_id]))
        self.created_map_id = ""
        return body

    def run_lifecycle(self) -> dict[str, Any]:
        before_count = len(self.list_maps().get("items", []))
        create_info = self.create_map().get("info", [])
        created_batch = self.batch_get()
        created_etag = self.latest_map_etag()
        update_info = self.update_map_name(created_etag).get("info", [])
        updated_batch = self.batch_get()
        image = self.get_image()
        markers_before = self.get_markers()
        marker_update = self.update_marker().get("info", [])
        markers_after_update = self.get_markers()
        marker_remove = self.remove_marker().get("info", [])
        markers_after_remove = self.get_markers()
        map_id = self.created_map_id
        remove_info = self.remove_map().get("info", [])
        removed_batch = self.batch_get(map_id)
        after_count = len(self.list_maps().get("items", []))
        return {
            "map_id": map_id,
            "before_count": before_count,
            "after_count": after_count,
            "create_info": create_info,
            "update_info": update_info,
            "created_batch_items": len(created_batch.get("items", [])),
            "updated_batch_items": len(updated_batch.get("items", [])),
            "image_mime_type": image.get("meta", {}).get("mime_type") or image.get("meta", {}).get("mimeType", ""),
            "image_data_b64_len": image.get("data_b64_len", 0),
            "marker_count_before": len(markers_before.get("markers", {})),
            "marker_update_info": marker_update,
            "marker_count_after_update": len(markers_after_update.get("markers", {})),
            "marker_remove_info": marker_remove,
            "marker_count_after_remove": len(markers_after_remove.get("markers", {})),
            "remove_info": remove_info,
            "removed_not_found_map_ids": removed_batch.get("failed_map_ids", []),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_map_id:
            map_id = self.created_map_id
            try:
                body = self.remove_map()
                cleanup_results.append({"object": map_id, "status": "map_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"object": map_id, "status": "map_cleanup_failed", "error": str(exc)[:400]})
        return cleanup_results

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
        self.results.append({"group": "map_marker_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
        cleanup_results = self.cleanup()
        if cleanup_results:
            self.results.append({"group": "cleanup", "status": "WARN", "elapsed_ms": 0, "details": {"cleanup": cleanup_results}})
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
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"map-marker-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"map-marker-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "map-marker-smoke-latest.json"
        latest_md = self.args.report_dir / "map-marker-smoke-latest.md"
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
            "# Axxon One Map And Marker Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Creates a `codex-*` raster map with a tiny PNG and marker, changes it, reads image/markers, updates/removes the marker, then removes the map.",
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
        if result["group"] == "map_marker_lifecycle":
            return (
                f"map={details.get('map_id')} image_b64_len={details.get('image_data_b64_len')} "
                f"markers={details.get('marker_count_before')}->{details.get('marker_count_after_update')}->{details.get('marker_count_after_remove')} "
                f"removed_not_found={details.get('removed_not_found_map_ids')}"
            )
        return f"keys={len(details)}"

    def short_stamp(self) -> str:
        return dt.datetime.now(dt.UTC).strftime("%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--marker-component", default="", help="Optional component access point to bind the marker to.")
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
    smoke = MapMarkerSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
