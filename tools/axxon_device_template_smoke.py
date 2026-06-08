#!/usr/bin/env python3
"""Controlled Axxon One device-template lifecycle smoke test."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-device-template-smoke"


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        out["properties"] = properties
    return out


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def prop_double(prop_id: str, value: float) -> dict[str, Any]:
    return {"id": prop_id, "value_double": value}


class DeviceTemplateSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_camera_uid = ""
        self.created_template_id = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_http_grpc()

    def change_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.checked_http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeConfig", payload)

    def change_templates(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.checked_http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeTemplates", payload)

    def checked_http_grpc(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.http_grpc(method, payload)
        if response.get("status") != 200:
            raise RuntimeError(f"{method} HTTP status {response.get('status')}: {self.client.sanitize(response.get('body'))}")
        body = response.get("body") or {}
        if body.get("failed"):
            raise RuntimeError(f"{method} failed: {self.client.sanitize(body.get('failed_reason', []))}")
        return body

    def create_temp_camera(self) -> str:
        stamp = self.short_stamp()
        display_id = "7" + stamp[-3:]
        name = f"codex-temp-template-camera-{stamp}"
        body = self.change_config(
            {
                "added": [
                    {
                        "uid": f"hosts/{self.args.tls_cn}",
                        "units": [
                            {
                                "type": "DeviceIpint",
                                "properties": [
                                    prop_string("vendor", "Virtual", properties=[prop_string("model", "Virtual several streams", properties=[])]),
                                    prop_string("display_name", name, properties=[]),
                                    prop_bool("blockingConfiguration", False),
                                    prop_string("display_id", display_id, properties=[]),
                                ],
                                "units": [],
                            }
                        ],
                    }
                ]
            }
        )
        created = body.get("added", [])
        if not created:
            raise RuntimeError(f"camera add returned no uid: {body}")
        self.created_camera_uid = created[0]
        return self.created_camera_uid

    def remove_camera(self) -> dict[str, Any]:
        if not self.created_camera_uid:
            return {"skipped": True}
        body = self.change_config({"removed": [{"uid": self.created_camera_uid}]})
        self.created_camera_uid = ""
        return body

    def template_body(self, template_id: str, name: str, latitude: float, longitude: float) -> dict[str, Any]:
        return {
            "id": template_id,
            "name": name,
            "unit": {
                "uid": self.created_camera_uid,
                "type": "DeviceIpint",
                "properties": [
                    prop_double("geoLocationLatitude", latitude),
                    prop_double("geoLocationLongitude", longitude),
                ],
                "units": [],
                "opaque_params": [{"id": "color", "value_string": "#00bcd4", "properties": []}],
            },
        }

    def create_template(self) -> dict[str, Any]:
        self.created_template_id = f"codex-{uuid.uuid4()}"
        name = f"codex-template-{self.short_stamp()}"
        return self.change_templates({"created": [self.template_body(self.created_template_id, name, 35.0, 45.0)]})

    def batch_get_template(self, template_id: str | None = None, etag: str = "") -> dict[str, Any]:
        item: dict[str, Any] = {"id": template_id or self.created_template_id}
        if etag:
            item["etag"] = etag
        response = self.client.http_grpc("axxonsoft.bl.config.ConfigurationService.BatchGetTemplates", {"items": [item]})
        if response.get("status") != 200:
            raise RuntimeError(f"BatchGetTemplates HTTP status {response.get('status')}: {self.client.sanitize(response.get('body'))}")
        return response.get("body") or {}

    def latest_etag(self, batch_get: dict[str, Any]) -> str:
        items = batch_get.get("items", [])
        if not items:
            raise RuntimeError(f"BatchGetTemplates returned no items: {batch_get}")
        etag = items[0].get("etag", "")
        if not etag:
            raise RuntimeError(f"BatchGetTemplates returned item without etag: {items[0]}")
        return etag

    def modify_template(self, etag: str) -> dict[str, Any]:
        name = f"codex-template-modified-{self.short_stamp()}"
        body = self.template_body(self.created_template_id, name, 38.0, 46.0)
        return self.change_templates({"modified": [{"etag": etag, "body": body}]})

    def set_assignment(self, template_ids: list[str]) -> dict[str, Any]:
        response = self.client.http_grpc(
            "axxonsoft.bl.config.ConfigurationService.SetTemplateAssignments",
            {"items": [{"unit_id": self.created_camera_uid, "template_ids": template_ids}]},
        )
        if response.get("status") != 200:
            raise RuntimeError(f"SetTemplateAssignments HTTP status {response.get('status')}: {self.client.sanitize(response.get('body'))}")
        body = response.get("body") or {}
        if body.get("failed"):
            raise RuntimeError(f"SetTemplateAssignments failed: {self.client.sanitize(body.get('failed'))}")
        return body

    def unassign_with_retry(self) -> tuple[dict[str, Any], int]:
        last_error = ""
        for attempt in range(max(1, self.args.unassign_attempts)):
            try:
                return self.set_assignment([]), attempt + 1
            except Exception as exc:
                last_error = str(exc)[:500]
                time.sleep(max(0.0, self.args.retry_delay_seconds))
                self.client.authenticate_http_grpc()
        raise RuntimeError(f"unassign failed after {self.args.unassign_attempts} attempts: {last_error}")

    def remove_template(self) -> dict[str, Any]:
        if not self.created_template_id:
            return {"skipped": True}
        body = self.change_templates({"removed": [self.created_template_id]})
        self.created_template_id = ""
        return body

    def read_camera_assignment(self) -> list[str]:
        self.client.authenticate_grpc()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        response = self.client.common_stubs()["config"].ListUnits(
            pb2.ListUnitsRequest(unit_uids=[self.created_camera_uid], display_mode=0),
            timeout=self.args.timeout,
        )
        data = self.client.message_to_dict(response)
        units = data.get("units", [])
        if not units:
            raise RuntimeError(f"camera not found: {self.created_camera_uid}")
        return list(units[0].get("assigned_templates", []))

    def run_lifecycle(self) -> dict[str, Any]:
        camera_uid = self.create_temp_camera()
        self.create_template()
        created_batch = self.batch_get_template()
        created_etag = self.latest_etag(created_batch)
        self.modify_template(created_etag)
        modified_batch = self.batch_get_template()
        modified_etag = self.latest_etag(modified_batch)
        self.set_assignment([self.created_template_id])
        assigned_templates = self.read_camera_assignment()
        if self.created_template_id not in assigned_templates:
            raise RuntimeError(f"template assignment missing from readback: {assigned_templates}")
        _, unassign_attempts = self.unassign_with_retry()
        unassigned_templates = self.read_camera_assignment()
        if self.created_template_id in unassigned_templates:
            raise RuntimeError(f"template still assigned after unassign: {unassigned_templates}")
        template_id = self.created_template_id
        self.remove_template()
        removed_batch = self.batch_get_template(template_id)
        self.remove_camera()
        return {
            "camera_uid": camera_uid,
            "template_id": template_id,
            "created_etag_len": len(created_etag),
            "modified_etag_len": len(modified_etag),
            "assignment_readback_count": len(assigned_templates),
            "unassign_attempts": unassign_attempts,
            "unassigned_readback_count": len(unassigned_templates),
            "removed_not_found": removed_batch.get("not_found", []),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_template_id:
            template_id = self.created_template_id
            try:
                body = self.remove_template()
                cleanup_results.append({"object": template_id, "status": "template_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"object": template_id, "status": "template_cleanup_failed", "error": str(exc)[:400]})
        if self.created_camera_uid:
            try:
                body = self.remove_camera()
                cleanup_results.append({"object": self.created_camera_uid, "status": "camera_removed", "failed": len(body.get("failed", []))})
            except Exception as exc:
                cleanup_results.append({"object": self.created_camera_uid, "status": "camera_cleanup_failed", "error": str(exc)[:400]})
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
        self.results.append({"group": "device_template_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
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
        json_path = self.args.report_dir / f"device-template-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"device-template-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "device-template-smoke-latest.json"
        latest_md = self.args.report_dir / "device-template-smoke-latest.md"
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
            "# Axxon One Device Template Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Creates an isolated virtual camera, creates and edits a `codex-*` template, assigns and unassigns it, then removes both objects.",
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
        if result["group"] == "device_template_lifecycle":
            return (
                f"template={details.get('template_id')} created_etag_len={details.get('created_etag_len')} "
                f"modified_etag_len={details.get('modified_etag_len')} unassign_attempts={details.get('unassign_attempts')} "
                f"removed_not_found={details.get('removed_not_found')}"
            )
        return f"keys={len(details)}"

    def short_stamp(self) -> str:
        return dt.datetime.now(dt.UTC).strftime("%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--unassign-attempts", type=int, default=4)
    parser.add_argument("--retry-delay-seconds", type=float, default=1.0)
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
    smoke = DeviceTemplateSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
