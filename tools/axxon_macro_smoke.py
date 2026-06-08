#!/usr/bin/env python3
"""Controlled Axxon One macro create/change/remove smoke test."""

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


CONFIRMATION = "CONFIRM-macro-smoke"

MACRO_MUTATIONS_REQUIRING_APPROVAL = [
    "LogicService.ChangeMacros.add_disabled_empty_temp_macro",
    "LogicService.ChangeMacros.modify_disabled_empty_temp_macro",
    "LogicService.ChangeMacros.remove_disabled_empty_temp_macro",
    "LogicService.LaunchMacro.disabled_empty_temp_macro",
]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


class MacroSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_macro_id = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_grpc()

    @property
    def logic_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.logic.LogicService_pb2")

    @property
    def macro_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.logic.Macro_pb2")

    @property
    def stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/logic/LogicService.proto", "LogicService")

    def macro_config(self, name: str) -> Any:
        macro = self.macro_pb2
        return macro.MacroConfig(
            guid=self.created_macro_id,
            name=name,
            mode=macro.MacroMode(enabled=False, is_add_to_menu=False, common=macro.MacroModeCommon()),
        )

    def change_macros(self, request: Any) -> dict[str, Any]:
        response = self.stub.ChangeMacros(request, timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def add_macro(self) -> dict[str, Any]:
        self.created_macro_id = str(uuid.uuid4())
        return self.change_macros(
            self.logic_pb2.ChangeMacrosRequest(added_macros=[self.macro_config(f"codex-temp-macro-{self.short_stamp()}")])
        )

    def modify_macro(self) -> dict[str, Any]:
        return self.change_macros(
            self.logic_pb2.ChangeMacrosRequest(modified_macros=[self.macro_config(f"codex-temp-macro-updated-{self.short_stamp()}")])
        )

    def batch_get(self, macro_id: str | None = None) -> dict[str, Any]:
        response = self.stub.BatchGetMacros(
            self.logic_pb2.BatchGetMacrosRequest(macros_ids=[macro_id or self.created_macro_id]),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def launch_macro(self) -> dict[str, Any]:
        response = self.stub.LaunchMacro(
            self.logic_pb2.LaunchMacroRequest(macro_id=self.created_macro_id),
            timeout=self.args.timeout,
        )
        return self.client.message_to_dict(response)

    def remove_macro(self) -> dict[str, Any]:
        if not self.created_macro_id:
            return {"skipped": True}
        macro_id = self.created_macro_id
        body = self.change_macros(self.logic_pb2.ChangeMacrosRequest(removed_macros=[macro_id]))
        self.created_macro_id = ""
        return body

    def run_lifecycle(self) -> dict[str, Any]:
        self.add_macro()
        added = self.batch_get()
        added_items = added.get("items", [])
        if len(added_items) != 1:
            raise RuntimeError(f"BatchGetMacros after add returned {len(added_items)} items")
        self.modify_macro()
        modified = self.batch_get()
        modified_items = modified.get("items", [])
        if len(modified_items) != 1:
            raise RuntimeError(f"BatchGetMacros after modify returned {len(modified_items)} items")
        launch_response: dict[str, Any] = {}
        if self.args.launch_disabled_empty_macro:
            launch_response = self.launch_macro()
        macro_id = self.created_macro_id
        self.remove_macro()
        removed = self.batch_get(macro_id)
        not_found = removed.get("not_found_macros", [])
        if macro_id not in not_found:
            raise RuntimeError(f"removed macro not reported as not_found: {removed}")
        return {
            "macro_id": macro_id,
            "added_name": added_items[0].get("name", ""),
            "modified_name": modified_items[0].get("name", ""),
            "mode_keys": sorted((modified_items[0].get("mode") or {}).keys()),
            "not_found_macros": not_found,
            "launch_tested": bool(self.args.launch_disabled_empty_macro),
            "launch_response_keys": sorted(launch_response.keys()),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_macro_id:
            macro_id = self.created_macro_id
            try:
                body = self.remove_macro()
                cleanup_results.append({"object": macro_id, "status": "macro_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"object": macro_id, "status": "macro_cleanup_failed", "error": str(exc)[:400]})
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
        self.results.append({"group": "macro_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
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
            "approval_only_operations": MACRO_MUTATIONS_REQUIRING_APPROVAL,
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"macro-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"macro-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "macro-smoke-latest.json"
        latest_md = self.args.report_dir / "macro-smoke-latest.md"
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
            "# Axxon One Macro Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Creates a disabled common `codex-temp-*` macro with no rules, changes it, optionally launches only that disabled empty macro, reads it back, then removes it.",
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
        if result["group"] == "macro_lifecycle":
            return (
                f"macro={details.get('macro_id')} added={details.get('added_name')} "
                f"modified={details.get('modified_name')} launch_tested={details.get('launch_tested')} "
                f"launch_keys={details.get('launch_response_keys')} "
                f"not_found={details.get('not_found_macros')}"
            )
        return f"keys={len(details)}"

    def short_stamp(self) -> str:
        return dt.datetime.now(dt.UTC).strftime("%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--launch-disabled-empty-macro", action="store_true")
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
    smoke = MacroSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
