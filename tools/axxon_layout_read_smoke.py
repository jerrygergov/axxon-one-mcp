#!/usr/bin/env python3
"""Read-only layout and map-arrangement smoke for API-book examples."""

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


def layout_body_summary(item: dict[str, Any]) -> dict[str, Any]:
    body = item.get("body", {})
    cells = body.get("cells", {})
    arrangement = body.get("map_arrangement") or body.get("mapArrangement") or {}
    return {
        "layout_id": item.get("meta", {}).get("layout_id", "") or body.get("id", ""),
        "display_name": body.get("display_name", ""),
        "is_user_defined": body.get("is_user_defined"),
        "is_for_alarm": body.get("is_for_alarm"),
        "map_id": body.get("map_id", ""),
        "map_view_mode": body.get("map_view_mode", ""),
        "cells_count": len(cells),
        "has_map_arrangement": bool(arrangement),
        "map_arrangement_keys": sorted(arrangement.keys())[:20],
    }


class LayoutReadSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.layout_id_cache = ""

    def setup(self) -> None:
        self.client.authenticate_grpc()

    @property
    def layout_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.layout.LayoutManager_pb2")

    @property
    def images_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.layout.LayoutImagesManager_pb2")

    @property
    def layout_stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/layout/LayoutManager.proto", "LayoutManager")

    @property
    def images_stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/layout/LayoutImagesManager.proto", "LayoutImagesManager")

    def chosen_layout_id(self, data: dict[str, Any]) -> str:
        if self.layout_id_cache:
            return self.layout_id_cache
        current = data.get("current", "")
        if current:
            self.layout_id_cache = current
            return current
        for item in data.get("items", []):
            layout_id = item.get("meta", {}).get("layout_id") or item.get("body", {}).get("id")
            if layout_id:
                self.layout_id_cache = layout_id
                return layout_id
        return ""

    def run_list_layouts(self) -> dict[str, Any]:
        response = self.layout_stub.ListLayouts(
            self.layout_pb2.ListLayoutsRequest(view=self.layout_pb2.VIEW_MODE_FULL),
            timeout=self.args.timeout,
        )
        data = self.client.message_to_dict(response)
        layout_id = self.chosen_layout_id(data)
        body_summaries = [layout_body_summary(item) for item in data.get("items", [])]
        map_modes = Counter(str(item.get("map_view_mode", "")) for item in body_summaries)
        return {
            "current": data.get("current", ""),
            "chosen_layout_id": layout_id,
            "layouts": len(data.get("items", [])),
            "slideshows": len(data.get("slideshows", [])),
            "special_layouts_shape": self.client.shape(data.get("special_layouts", {})),
            "map_mode_counts": map_modes.most_common(),
            "layouts_with_map_id": sum(1 for item in body_summaries if item.get("map_id")),
            "layouts_with_map_arrangement": sum(1 for item in body_summaries if item.get("has_map_arrangement")),
            "samples": body_summaries[:10],
        }

    def run_batch_get(self) -> dict[str, Any]:
        if not self.layout_id_cache:
            self.run_list_layouts()
        if not self.layout_id_cache:
            return {"skipped": "no layout id"}
        request = self.layout_pb2.BatchGetLayoutsRequest(
            items=[self.layout_pb2.BatchGetLayoutsRequest.Locator(layout_id=self.layout_id_cache)]
        )
        response = self.layout_stub.BatchGetLayouts(request, timeout=self.args.timeout)
        data = self.client.message_to_dict(response)
        return {
            "requested_layout_id": self.layout_id_cache,
            "items": len(data.get("items", [])),
            "not_found_items": data.get("not_found_items", []),
            "sample": layout_body_summary(data.get("items", [{}])[0]) if data.get("items") else {},
        }

    def run_list_images(self) -> dict[str, Any]:
        if not self.layout_id_cache:
            self.run_list_layouts()
        if not self.layout_id_cache:
            return {"skipped": "no layout id"}
        response = self.images_stub.ListLayoutImages(
            self.images_pb2.ListLayoutImagesRequest(layout_id=self.layout_id_cache),
            timeout=self.args.timeout,
        )
        data = self.client.message_to_dict(response)
        return {
            "layout_id": self.layout_id_cache,
            "images": len(data.get("images", [])),
            "sample_shape": self.client.shape(data.get("images", [])[:1]),
        }

    def invoke(self, group: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            details = getattr(self, f"run_{group}")()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "WARN"
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def run(self) -> dict[str, Any]:
        self.setup()
        for group in ["list_layouts", "batch_get", "list_images"]:
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
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"layout-read-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"layout-read-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "layout-read-smoke-latest.json"
        latest_md = self.args.report_dir / "layout-read-smoke-latest.md"
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
            "# Axxon One Layout Read Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "This smoke is read-only. It does not call `LayoutManager.Update`, `LayoutsOnView`, or Client HTTP.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            if result["group"] == "list_layouts":
                note = f"layouts={details.get('layouts')} current={details.get('current', '')} map_ids={details.get('layouts_with_map_id')} map_arrangements={details.get('layouts_with_map_arrangement')}"
            elif result["group"] == "batch_get":
                note = f"requested={details.get('requested_layout_id', '')} items={details.get('items')} not_found={len(details.get('not_found_items', []))}"
            elif result["group"] == "list_images":
                note = f"layout={details.get('layout_id', '')} images={details.get('images')}"
            else:
                note = details.get("error") or f"keys={len(details)}"
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:220]} |")
        list_details = next((item.get("details", {}) for item in report["results"] if item.get("group") == "list_layouts"), {})
        if list_details.get("samples"):
            lines.extend(["", "## Layout Samples", "", "| Layout ID | Name | Map ID | Map View Mode | Cells | Has Arrangement | Arrangement Keys |", "| --- | --- | --- | --- | ---: | --- | --- |"])
            for sample in list_details.get("samples", []):
                keys = ", ".join(sample.get("map_arrangement_keys", []))
                lines.append(
                    f"| `{sample.get('layout_id', '')}` | {sample.get('display_name', '')} | `{sample.get('map_id', '')}` | `{sample.get('map_view_mode', '')}` | {sample.get('cells_count', 0)} | {sample.get('has_map_arrangement')} | {keys.replace('|', '\\|')[:160]} |"
                )
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    smoke = LayoutReadSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
