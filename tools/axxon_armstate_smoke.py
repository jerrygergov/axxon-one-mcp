#!/usr/bin/env python3
"""Controlled temporary virtual camera arm-state smoke with rollback."""

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


CONFIRMATION = "CONFIRM-armstate-smoke"

ARMSTATE_MUTATIONS_REQUIRING_APPROVAL = [
    "ConfigurationService.ChangeConfig.add_temp_virtual_camera",
    "LogicService.ChangeArmState.temp_virtual_camera",
    "ConfigurationService.ChangeConfig.remove_temp_virtual_camera",
]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def temp_display_id() -> str:
    return "9" + dt.datetime.now(dt.UTC).strftime("%H%M%S")[-3:]


def prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        out["properties"] = properties
    return out


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def arm_state_name() -> str:
    return "CS_Arm"


class ArmStateSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_uid = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_http_grpc()

    def change_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeConfig", payload)
        if response.get("status") != 200:
            raise RuntimeError(f"ChangeConfig HTTP status {response.get('status')}")
        body = response.get("body") or {}
        if body.get("failed"):
            raise RuntimeError(f"ChangeConfig failed: {self.client.sanitize(body.get('failed_reason', []))}")
        return body

    def add_temp_camera(self) -> dict[str, Any]:
        display_id = temp_display_id()
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
                                    prop_string("display_name", f"codex-temp-armstate-{display_id}", properties=[]),
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
        self.created_uid = body.get("added", [""])[0]
        if not self.created_uid:
            raise RuntimeError(f"ChangeConfig add returned no uid: {body}")
        return {"body": body, "display_id": display_id}

    def remove_temp_camera(self) -> dict[str, Any]:
        if not self.created_uid:
            return {"skipped": True}
        uid = self.created_uid
        body = self.change_config({"removed": [{"uid": uid}]})
        self.created_uid = ""
        return body

    def camera_ap(self) -> str:
        return f"{self.created_uid}/SourceEndpoint.video:0:0"

    def change_arm_state(self) -> dict[str, Any]:
        self.client.authenticate_grpc()
        logic_pb2 = self.client.import_module("axxonsoft.bl.logic.LogicService_pb2")
        events_pb2 = self.client.import_module("axxonsoft.bl.events.Events_pb2")
        duration_pb2 = self.client.import_module("google.protobuf.duration_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/logic/LogicService.proto", "LogicService")
        response = stub.ChangeArmState(
            logic_pb2.ChangeArmStateRequest(
                camera_ap=self.camera_ap(),
                state=events_pb2.CameraArmStateEvent.ECameraArmState.Value(arm_state_name()),
                timeout=duration_pb2.Duration(seconds=max(1, self.args.arm_timeout_seconds)),
            ),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def run_lifecycle(self) -> dict[str, Any]:
        added = self.add_temp_camera()
        arm_response = self.change_arm_state()
        remove_response = self.remove_temp_camera()
        return {
            "camera_uid": added["body"].get("added", [""])[0],
            "display_id": added["display_id"],
            "camera_ap": self.camera_ap() if self.created_uid else f"{added['body'].get('added', [''])[0]}/SourceEndpoint.video:0:0",
            "arm_timeout_seconds": max(1, self.args.arm_timeout_seconds),
            "arm_response_keys": sorted(arm_response.keys()),
            "remove_response_keys": sorted(remove_response.keys()),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_uid:
            uid = self.created_uid
            try:
                body = self.remove_temp_camera()
                cleanup_results.append({"uid": uid, "status": "camera_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"uid": uid, "status": "camera_cleanup_failed", "error": str(exc)[:400]})
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
        self.results.append({"group": "armstate_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "approval_only_operations": ARMSTATE_MUTATIONS_REQUIRING_APPROVAL,
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"armstate-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"armstate-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "armstate-smoke-latest.json"
        latest_md = self.args.report_dir / "armstate-smoke-latest.md"
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
            "# Axxon One Arm State Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Creates a temporary virtual camera, calls `LogicService.ChangeArmState` with a short timeout, then removes the camera.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = details.get("error") or f"camera={details.get('camera_uid')} timeout={details.get('arm_timeout_seconds')} arm_keys={details.get('arm_response_keys')} remove_keys={details.get('remove_response_keys')}"
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:240]} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--arm-timeout-seconds", type=int, default=2)
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
    smoke = ArmStateSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
