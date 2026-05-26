#!/usr/bin/env python3
"""Live approval-gated smoke for Phase 5F-B admin mutation workflows."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
import urllib.parse

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from axxon_admin_smoke import sanitize_evidence as _sanitize_admin_evidence  # noqa: E402
from axxon_api_client import AxxonApiClient, add_common_args, config_from_args  # noqa: E402
from axxon_mcp_admin_mutations import ADMIN_MUTATION_APPROVE_ENV, AxxonAdminMutationRegistry  # noqa: E402


CONFIRMATION = "CONFIRM-admin-mutation-smoke"
REPORT_BASENAME = "phase-5f-b-admin-mutation-smoke"
LATEST_BASENAME = "phase-5f-b-admin-mutation-smoke-latest"
WORKFLOWS = [
    "security_user_role_lifecycle",
    "security_role_permissions_update",
    "security_policy_noop_probe",
    "security_ldap_temp_lifecycle",
    "security_tfa_temp_user_lifecycle",
]
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
TFA_SECRET_KEYS = {
    "secret_key",
    "secret",
    "tfa_secret",
    "verification_code",
    "verification_codes",
    "totp",
    "totp_code",
    "otp",
    "otp_code",
}
TFA_TEXT_RE = re.compile(
    r"(?P<key>\b(?:secret_key|tfa_secret|verification_code|verification_codes|totp|totp_code|otp|otp_code)\b)"
    r"(?P<sep>\s*[:=]\s*)(?P<value>[A-Za-z0-9+/=_-]+)",
    re.IGNORECASE,
)


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
    try:
        return urllib.parse.urlsplit(http_url).hostname or ""
    except ValueError:
        return ""


def _sanitize_tfa_text(value: str) -> str:
    return TFA_TEXT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", value)


def _redact_tfa_value(value: Any) -> Any:
    if isinstance(value, list):
        return ["<redacted>" for _item in value]
    if isinstance(value, tuple):
        return ["<redacted>" for _item in value]
    return "<redacted>" if value else value


def sanitize_evidence(
    value: Any,
    host: str = "",
    username: str = "",
    tls_cn: str = "",
    ca_path: str = "",
    extra_hosts: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if str(key).lower() in TFA_SECRET_KEYS:
                redacted[key] = _redact_tfa_value(item)
            else:
                redacted[key] = sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts)
        return _sanitize_admin_evidence(redacted, host, username, tls_cn, ca_path, extra_hosts)
    if isinstance(value, list):
        return [sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts) for item in value]
    if isinstance(value, tuple):
        return [sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts) for item in value]
    if isinstance(value, str):
        return _sanitize_admin_evidence(_sanitize_tfa_text(value), host, username, tls_cn, ca_path, extra_hosts)
    return _sanitize_admin_evidence(value, host, username, tls_cn, ca_path, extra_hosts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    forbidden = _cli_connection_flags(raw_argv)
    if forbidden:
        parser.error(
            "connection and credential options must come from environment/config, not CLI: "
            + ", ".join(forbidden)
        )
    args = parser.parse_args(raw_argv)
    if not args.password:
        parser.error("password is required from environment/config, for example AXXON_PASSWORD")
    if not args.i_understand_this_mutates or args.confirm != CONFIRMATION:
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def report_paths(report_dir: Path, stamp: str) -> dict[str, Path]:
    return {
        "json": report_dir / f"{REPORT_BASENAME}-{stamp}.json",
        "md": report_dir / f"{REPORT_BASENAME}-{stamp}.md",
        "latest_json": report_dir / f"{LATEST_BASENAME}.json",
        "latest_md": report_dir / f"{LATEST_BASENAME}.md",
    }


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


def workflow_status(evidence: dict[str, Any]) -> str:
    statuses: list[str] = []
    for value in evidence.values():
        if isinstance(value, dict):
            statuses.append(payload_status(value))
    if evidence.get("status") == "error" or "error_type" in evidence:
        statuses.append("FAIL")
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


class AdminMutationSmoke:
    def __init__(self, args: argparse.Namespace, *, registry: Any | None = None) -> None:
        self.args = args
        self.started_at = dt.datetime.now(dt.UTC)
        self.registry = registry or self.default_registry()
        self.results: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}

    def default_registry(self) -> AxxonAdminMutationRegistry:
        config = config_from_args(self.args)
        return AxxonAdminMutationRegistry(
            client_factory=lambda: AxxonApiClient(config),
            enabled=os.environ.get(ADMIN_MUTATION_APPROVE_ENV) == "1",
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
            status = workflow_status(evidence)
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
        self.context["workflow_catalog"] = self.registry.list_workflows()
        for workflow in WORKFLOWS:
            self.record(workflow, lambda workflow=workflow: self.run_workflow(workflow))
        report = self.report()
        self.write_report(report)
        return report

    def run_workflow(self, workflow: str) -> dict[str, Any]:
        evidence: dict[str, Any] = {}
        plan = self.registry.plan(workflow, self.params_for(workflow))
        evidence["plan"] = plan
        plan_id = str(plan.get("plan_id") or "")
        confirmation = str(plan.get("confirmation_token") or "")
        rollback_confirmation = str(plan.get("rollback_confirmation_token") or "")
        if not plan_id:
            return evidence
        try:
            evidence["apply"] = self.registry.apply(plan_id, confirmation)
            evidence["verify"] = self.registry.verify(plan_id)
        except Exception as exc:  # noqa: BLE001 - rollback still needs to run for live smoke.
            evidence["status"] = "error"
            evidence["error_type"] = exc.__class__.__name__
            evidence["message"] = str(exc)[:800]
        finally:
            if rollback_confirmation:
                evidence["rollback"] = self.registry.rollback(plan_id, rollback_confirmation)
        return evidence

    def params_for(self, workflow: str) -> dict[str, Any]:
        if workflow in {
            "security_user_role_lifecycle",
            "security_role_permissions_update",
            "security_ldap_temp_lifecycle",
            "security_tfa_temp_user_lifecycle",
        }:
            return {"display_name_hint": "smoke"}
        return {}

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "host": self.args.host,
                "grpc_target": f"{self.args.host}:{self.args.grpc_port}",
                "http_url": self.args.http_url,
                "username": "<demo-user>" if self.args.username else "",
                "password": "<redacted>" if self.args.password else "",
                "tls_cn": "<demo-tls-cn>" if self.args.tls_cn else "",
                "ca": "<redacted-ca>" if self.args.ca else "",
            },
            "modes": {
                "mutation_approval_env": ADMIN_MUTATION_APPROVE_ENV,
                "mutation_approval_enabled": os.environ.get(ADMIN_MUTATION_APPROVE_ENV) == "1",
            },
            "workflow_catalog": self.context.get("workflow_catalog", {}),
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        paths = report_paths(self.args.report_dir, stamp)
        clean = self.sanitize(report)
        json_text = json.dumps(clean, indent=2, ensure_ascii=True, default=str) + "\n"
        paths["json"].write_text(json_text, encoding="utf-8")
        paths["latest_json"].write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(clean)
        paths["md"].write_text(md_text, encoding="utf-8")
        paths["latest_md"].write_text(md_text, encoding="utf-8")
        print(f"JSON report: {paths['json']}")
        print(f"Markdown report: {paths['md']}")
        print(f"Latest markdown: {paths['latest_md']}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Phase 5F-B Admin Mutation Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{report['target']['grpc_target']}`",
            f"- HTTP target: `{report['target']['http_url']}`",
            f"- Approval env: `{report['modes']['mutation_approval_env']}`",
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = AdminMutationSmoke(args).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
