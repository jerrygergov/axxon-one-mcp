#!/usr/bin/env python3
"""Controlled temporary layout update smoke with rollback."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-layout-mutation-smoke"
TEMP_LAYOUT_PREFIX = "codex-layout-"

LAYOUT_MUTATIONS_REQUIRING_APPROVAL = [
    "LayoutManager.Update.create_temp_layout",
    "LayoutManager.Update.modify_temp_layout",
    "LayoutManager.Update.remove_temp_layout",
    "LayoutManager.LayoutsOnView.temp_layout",
]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def temp_layout_id() -> str:
    return f"{TEMP_LAYOUT_PREFIX}{uuid.uuid4()}"


class LayoutMutationSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.created_layout_id = ""
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_grpc()

    @property
    def layout_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.layout.LayoutManager_pb2")

    @property
    def primitive_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")

    @property
    def stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/layout/LayoutManager.proto", "LayoutManager")

    def list_layouts(self) -> dict[str, Any]:
        response = self.stub.ListLayouts(
            self.layout_pb2.ListLayoutsRequest(view=self.layout_pb2.VIEW_MODE_FULL),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def batch_get(self, layout_id: str | None = None) -> dict[str, Any]:
        target = layout_id or self.created_layout_id
        response = self.stub.BatchGetLayouts(
            self.layout_pb2.BatchGetLayoutsRequest(
                items=[self.layout_pb2.BatchGetLayoutsRequest.Locator(layout_id=target)]
            ),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def temp_layout_body(self, layout_id: str, *, updated: bool = False) -> Any:
        layout_pb2 = self.layout_pb2
        primitive_pb2 = self.primitive_pb2
        layout = layout_pb2.Layout(
            id=layout_id,
            display_name=f"codex temp layout {'updated' if updated else 'created'}",
            is_user_defined=True,
            is_for_alarm=False,
            map_view_mode=layout_pb2.MAP_VIEW_MODE_LAYOUT_ONLY,
            map_arrangement=layout_pb2.MapArrangement(
                zoom_position=primitive_pb2.Point(x=0.25 if updated else 0.10, y=0.75 if updated else 0.10),
                zoom_value=2 if updated else 1,
                map_top_viewport_position=0.0,
                is_label_on=updated,
                is_blink_on=False,
                is_switch_layouts_on=False,
                is_top_view_on=False,
                show_offline_cameras=True,
                is_thumbnail_3d_on=False,
            ),
        )
        layout.cells[0].CopyFrom(
            layout_pb2.Cell(
                position=0,
                dimensions=primitive_pb2.Size(width=1.0, height=1.0),
                right_spring=1.0,
                bottom_spring=1.0,
            )
        )
        return layout

    def update(self, request: Any) -> dict[str, Any]:
        response = self.stub.Update(request, timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def create_layout(self) -> dict[str, Any]:
        self.created_layout_id = temp_layout_id()
        return self.update(
            self.layout_pb2.UpdateRequest(created=[self.temp_layout_body(self.created_layout_id)])
        )

    def latest_etag(self) -> str:
        data = self.batch_get()
        items = data.get("items", [])
        if not items:
            raise RuntimeError(f"BatchGetLayouts returned no created layout: {data}")
        etag = items[0].get("meta", {}).get("etag", "")
        if not etag:
            raise RuntimeError(f"BatchGetLayouts returned no layout etag: {items[0]}")
        return etag

    def modify_layout(self, etag: str) -> dict[str, Any]:
        return self.update(
            self.layout_pb2.UpdateRequest(
                modified=[
                    self.layout_pb2.TaggedLayout(
                        body=self.temp_layout_body(self.created_layout_id, updated=True),
                        etag=etag,
                    )
                ]
            )
        )

    def layouts_on_view(self) -> dict[str, Any]:
        response = self.stub.LayoutsOnView(
            self.layout_pb2.LayoutsOnViewRequest(
                layouts=[
                    self.layout_pb2.LayoutOnView(
                        layout_id=self.created_layout_id,
                        layout_display_name="codex temp layout updated",
                    )
                ]
            ),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def remove_layout(self, layout_id: str | None = None) -> dict[str, Any]:
        target = layout_id or self.created_layout_id
        if not target:
            return {"skipped": True}
        body = self.update(self.layout_pb2.UpdateRequest(removed=[target]))
        if target == self.created_layout_id:
            self.created_layout_id = ""
        return body

    def run_lifecycle(self) -> dict[str, Any]:
        before = self.list_layouts()
        before_count = len(before.get("items", []))
        current_before = before.get("current", "")
        create_response = self.create_layout()
        created_id = self.created_layout_id
        created_batch = self.batch_get()
        created_etag = self.latest_etag()
        modify_response = self.modify_layout(created_etag)
        modified_batch = self.batch_get()
        layouts_on_view_response = self.layouts_on_view()
        remove_response = self.remove_layout(created_id)
        removed_batch = self.batch_get(created_id)
        after = self.list_layouts()
        return {
            "layout_id": created_id,
            "before_count": before_count,
            "after_count": len(after.get("items", [])),
            "current_before": current_before,
            "current_after": after.get("current", ""),
            "create_created_layouts": create_response.get("created_layouts", []),
            "created_batch_items": len(created_batch.get("items", [])),
            "modify_response_keys": sorted(modify_response.keys()),
            "modified_batch_items": len(modified_batch.get("items", [])),
            "modified_name": (
                modified_batch.get("items", [{}])[0].get("body", {}).get("display_name", "")
                if modified_batch.get("items")
                else ""
            ),
            "modified_arrangement_keys": sorted(
                (
                    modified_batch.get("items", [{}])[0].get("body", {}).get("map_arrangement")
                    or modified_batch.get("items", [{}])[0].get("body", {}).get("mapArrangement")
                    or {}
                ).keys()
            ),
            "layouts_on_view_response_keys": sorted(layouts_on_view_response.keys()),
            "remove_response_keys": sorted(remove_response.keys()),
            "removed_not_found_items": removed_batch.get("not_found_items", []),
            "current_unchanged": current_before == after.get("current", ""),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_layout_id:
            layout_id = self.created_layout_id
            try:
                body = self.remove_layout(layout_id)
                cleanup_results.append({"object": layout_id, "status": "layout_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"object": layout_id, "status": "layout_cleanup_failed", "error": str(exc)[:400]})
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
        cleanup_results = self.cleanup()
        if cleanup_results:
            details["cleanup"] = cleanup_results
        self.results.append(
            {
                "group": "layout_mutation_lifecycle",
                "status": status,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "details": details,
            }
        )
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
                "grpc_target": f"{self.args.host}:{self.args.grpc_port}",
                "username": self.args.username,
                "password": "<redacted>",
            },
            "approval_only_operations": LAYOUT_MUTATIONS_REQUIRING_APPROVAL,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"layout-mutation-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"layout-mutation-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "layout-mutation-smoke-latest.json"
        latest_md = self.args.report_dir / "layout-mutation-smoke-latest.md"
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
            "# Axxon One Layout Mutation Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "Controlled smoke for a temporary `codex-layout-*` layout. It creates, modifies, calls `LayoutsOnView` for the temporary layout, removes it, and verifies rollback.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = (
                details.get("error")
                or f"layout={details.get('layout_id', '')} before={details.get('before_count')} after={details.get('after_count')} removed_not_found={len(details.get('removed_not_found_items', []))} current_unchanged={details.get('current_unchanged')}"
            )
            lines.append(
                f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:240]} |"
            )
        lines.append("")
        return "\n".join(lines)


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
    if not mutation_approved(args):
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def main() -> int:
    smoke = LayoutMutationSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
