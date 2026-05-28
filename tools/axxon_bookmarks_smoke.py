#!/usr/bin/env python3
"""Live read + lifecycle smoke for Phase 5G BookmarkService over HTTP /grpc."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable
import urllib.parse

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_admin_smoke import sanitize_evidence  # noqa: E402
from axxon_api_client import AxxonApiClient, add_common_args, config_from_args  # noqa: E402
from axxon_mcp_admin import _body  # noqa: E402
from axxon_mcp_bookmark_mutations import (  # noqa: E402
    BOOKMARK_MUTATION_APPROVE_ENV,
    AxxonBookmarkMutationRegistry,
)

CONFIRMATION = "CONFIRM-bookmark-mutation-smoke"
REPORT_BASENAME = "phase-5g-bookmarks-smoke"
LATEST_BASENAME = "phase-5g-bookmarks-smoke-latest"
CLI_CONNECTION_FLAGS = {
    "--host",
    "--grpc-port",
    "--http-port",
    "--http-url",
    "--username",
    "--password",
    "--tls-cn",
    "--ca",
    "--proto-dir",
    "--stubs-dir",
    "--timeout",
}
DEFAULT_RANGE_HOURS = 24


def _cli_connection_flags(argv: list[str]) -> list[str]:
    found: list[str] = []
    for arg in argv:
        for flag in CLI_CONNECTION_FLAGS:
            if arg == flag or arg.startswith(flag + "="):
                found.append(flag)
    return sorted(set(found))


def _http_url_host(http_url: str = "") -> str:
    if not http_url:
        return ""
    return urllib.parse.urlsplit(http_url).hostname or ""


def payload_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = str(payload.get("status") or "").lower()
        if status in {"ok", "pass", "planned", "applied", "verified", "rolled-back", "rolled_back"}:
            return "PASS"
        if status in {"fixture-needed", "skipped", "gap", "warn", "warning", "partial"}:
            return "WARN"
        if status in {"error", "fail", "failed", "rejected"}:
            return "FAIL"
    return "PASS"


def group_status(evidence: dict[str, Any]) -> str:
    statuses = [payload_status(value) for value in evidence.values() if isinstance(value, dict)]
    if evidence.get("status"):
        statuses.append(payload_status(evidence))
    if "error_type" in evidence:
        statuses.append("FAIL")
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _default_range() -> dict[str, str]:
    now = dt.datetime.now(dt.UTC)
    begin = now - dt.timedelta(hours=DEFAULT_RANGE_HOURS)
    fmt = "%Y%m%dT%H%M%S.000"
    return {"begin_time": begin.strftime(fmt), "end_time": now.strftime(fmt)}


class BookmarksSmoke:
    def __init__(self, args: argparse.Namespace, *, registry: Any | None = None, client: Any | None = None) -> None:
        self.args = args
        self.started_at = dt.datetime.now(dt.UTC)
        self.client = client or AxxonApiClient(config_from_args(args))
        self.registry = registry or self.default_registry()
        self.results: list[dict[str, Any]] = []

    def default_registry(self) -> AxxonBookmarkMutationRegistry:
        return AxxonBookmarkMutationRegistry(
            client_factory=lambda: self.client,
            enabled=os.environ.get(BOOKMARK_MUTATION_APPROVE_ENV) == "1",
        )

    @property
    def host(self) -> str:
        return str(getattr(self.args, "host", ""))

    def sanitize_extra_hosts(self) -> tuple[str, ...]:
        http_host = _http_url_host(str(getattr(self.args, "http_url", "")))
        return tuple(host for host in (http_host,) if host and host != self.host)

    def sanitize(self, value: Any) -> Any:
        return sanitize_evidence(
            value,
            host=self.host,
            username=str(getattr(self.args, "username", "")),
            tls_cn=str(getattr(self.args, "tls_cn", "")),
            ca_path=str(getattr(self.args, "ca", "")),
            extra_hosts=self.sanitize_extra_hosts(),
        )

    def record(self, group: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            evidence = func()
            status = group_status(evidence)
        except Exception as exc:  # noqa: BLE001 - live smoke reports structured failures.
            evidence = {"status": "error", "error_type": exc.__class__.__name__, "message": str(exc)[:800]}
            if self.args.verbose:
                import traceback

                evidence["traceback"] = traceback.format_exc()
            status = "FAIL"
        self.results.append(
            {
                "group": group,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "evidence": self.sanitize(evidence),
            }
        )
        return evidence

    def run(self) -> dict[str, Any]:
        self.record("bookmark_list", self.run_list)
        self.record("bookmark_lifecycle", self.run_lifecycle)
        report = self.report()
        self.write_report(report)
        return report

    @property
    def mutation_enabled(self) -> bool:
        return os.environ.get(BOOKMARK_MUTATION_APPROVE_ENV) == "1"

    def run_list(self) -> dict[str, Any]:
        time_range = _default_range()
        data = _body(self.client.bookmark_list(time_range, page_size=25))
        bookmarks = data.get("bookmarks", []) if isinstance(data, dict) else []
        return {
            "status": "ok",
            "range_hours": DEFAULT_RANGE_HOURS,
            "bookmark_count": len(bookmarks),
            "next_page_token_present": bool(data.get("next_page_token")),
        }

    def lifecycle_params(self) -> dict[str, Any]:
        camera_ap = str(getattr(self.args, "camera_access_point", "") or "")
        begin = str(getattr(self.args, "begin_time", "") or "")
        end = str(getattr(self.args, "end_time", "") or "")
        params: dict[str, Any] = {}
        if camera_ap:
            params["camera_access_point"] = camera_ap
        if begin and end:
            params["range"] = {"begin_time": begin, "end_time": end}
        return params

    def run_lifecycle(self) -> dict[str, Any]:
        params = self.lifecycle_params()
        plan = self.registry.plan("bookmark_lifecycle", params)
        evidence: dict[str, Any] = {"plan": plan}
        plan_id = str(plan.get("plan_id") or "")
        if not plan_id:
            return evidence
        if not self.mutation_enabled:
            evidence["status"] = "skipped"
            evidence["message"] = f"Set {BOOKMARK_MUTATION_APPROVE_ENV}=1 to exercise the bookmark lifecycle."
            return evidence
        if not ("camera_access_point" in params and "range" in params):
            evidence["status"] = "fixture-needed"
            evidence["required"] = ["camera_access_point", "range"]
            evidence["message"] = "Provide --camera-access-point and --begin-time/--end-time fixtures."
            return evidence
        confirmation = str(plan.get("confirmation_token") or "")
        rollback_confirmation = str(plan.get("rollback_confirmation_token") or "")
        try:
            evidence["apply"] = self.registry.apply(plan_id, confirmation)
            evidence["verify"] = self.registry.verify(plan_id)
        except Exception as exc:  # noqa: BLE001 - rollback still needs to run.
            evidence["status"] = "error"
            evidence["error_type"] = exc.__class__.__name__
            evidence["message"] = str(exc)[:800]
        finally:
            if rollback_confirmation:
                evidence["rollback"] = self.registry.rollback(plan_id, rollback_confirmation)
        return evidence

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "host": self.args.host,
                "http_url": self.args.http_url,
                "username": "<demo-user>" if self.args.username else "",
                "password": "<redacted>" if self.args.password else "",
                "tls_cn": "<demo-tls-cn>" if self.args.tls_cn else "",
                "ca": "<redacted-ca>" if self.args.ca else "",
            },
            "modes": {
                "mutation_approval_env": BOOKMARK_MUTATION_APPROVE_ENV,
                "mutation_approval_enabled": os.environ.get(BOOKMARK_MUTATION_APPROVE_ENV) == "1",
                "transport": "http-grpc",
            },
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        clean = self.sanitize(report)
        json_text = json.dumps(clean, indent=2, ensure_ascii=True, default=str) + "\n"
        (self.args.report_dir / f"{REPORT_BASENAME}-{stamp}.json").write_text(json_text, encoding="utf-8")
        (self.args.report_dir / f"{LATEST_BASENAME}.json").write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(clean)
        (self.args.report_dir / f"{REPORT_BASENAME}-{stamp}.md").write_text(md_text, encoding="utf-8")
        (self.args.report_dir / f"{LATEST_BASENAME}.md").write_text(md_text, encoding="utf-8")
        print(f"Latest markdown: {self.args.report_dir / f'{LATEST_BASENAME}.md'}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Phase 5G BookmarkService Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{report['target']['http_url']}`",
            f"- Transport: `{report['modes']['transport']}`",
            f"- Approval env: `{report['modes']['mutation_approval_env']}`",
            "",
            "Reads are non-mutating. The lifecycle workflow only writes a temporary `codex-` bookmark and removes it on rollback.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            note = self.note_for(result).replace("|", "\\|")[:260]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        evidence = result.get("evidence") or {}
        if not isinstance(evidence, dict):
            return str(evidence)
        if result["group"] == "bookmark_list":
            return f"count={evidence.get('bookmark_count', '')} status={evidence.get('status', '')}"
        plan = evidence.get("plan") if isinstance(evidence.get("plan"), dict) else {}
        applied = evidence.get("apply") if isinstance(evidence.get("apply"), dict) else {}
        verified = evidence.get("verify") if isinstance(evidence.get("verify"), dict) else {}
        rolled = evidence.get("rollback") if isinstance(evidence.get("rollback"), dict) else {}
        if evidence.get("message"):
            return str(evidence["message"])
        return (
            f"plan={plan.get('status', '')} apply={applied.get('status', '')} "
            f"verify={verified.get('status', '')} rollback={rolled.get('status', '')}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--camera-access-point", default="")
    parser.add_argument("--begin-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--verbose", action="store_true")
    forbidden = _cli_connection_flags(raw_argv)
    if forbidden:
        parser.error(
            "connection and credential options must come from environment/config, not CLI: " + ", ".join(forbidden)
        )
    args = parser.parse_args(raw_argv)
    if not args.password:
        parser.error("password is required from environment/config, for example AXXON_PASSWORD")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = BookmarksSmoke(args).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
