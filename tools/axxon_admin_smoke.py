#!/usr/bin/env python3
"""Live read-only smoke for Phase 5F-A admin MCP tools."""

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

from axxon_api_client import add_common_args, config_from_args  # noqa: E402
from axxon_mcp_admin import AxxonMcpAdmin  # noqa: E402


LATEST_BASENAME = "phase-5f-admin-smoke-latest"
REPORT_BASENAME = "phase-5f-admin-smoke"
DEFAULT_NOTIFIER_TIMEOUT = 5.0
DEFAULT_NOTIFIER_LIMIT = 25
NOTIFIER_TIMEOUT_MIN = 1.0
NOTIFIER_TIMEOUT_MAX = 30.0
NOTIFIER_LIMIT_MIN = 1
NOTIFIER_LIMIT_MAX = 100
ROLE_PAGE_SIZE_MIN = 1
ROLE_PAGE_SIZE_MAX = 100
SECRET_KEY_RE = re.compile(
    r"(password|passwd|pwd|secret|certificate|private[_-]?key|serial|license|fingerprint|hardware|"
    r"root[_-]?password|[A-Za-z0-9_-]*token[A-Za-z0-9_-]*|authorization|auth)",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"\bBearer\s+[^,\s;}\]]+", re.IGNORECASE)
QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<key>\b(?:password|passwd|pwd|secret|root[_-]?password|[A-Za-z0-9_-]*token[A-Za-z0-9_-]*)\b)"
    r"(?P<sep>\s*[:=]\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<key>\b(?:password|passwd|pwd|secret|root[_-]?password|[A-Za-z0-9_-]*token[A-Za-z0-9_-]*)\b)"
    r"(?P<sep>\s*[:=]\s*)[^,\s;}\]]+",
    re.IGNORECASE,
)
URL_USERINFO_RE = re.compile(r"(?P<prefix>\b[a-z][a-z0-9+.-]*://)(?P<userinfo>[^/@\s]+)@", re.IGNORECASE)
INTRINSIC_UID_RE = re.compile(r"\bhosts/[^\s,;}\])]+")
CA_PATH_TEXT_RE = re.compile(r"(?<![A-Za-z0-9_.-])/[^\s,;}\]]+\.crt\b")
USER_KEYS = {"username", "user", "login"}
TLS_CN_KEYS = {"tls_cn", "tls-cn", "tls_common_name"}
CA_KEYS = {"ca", "ca_path", "ca-file", "ca_file", "certificate_authority"}
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


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), maximum))


def _secret_key(key: Any) -> bool:
    return bool(SECRET_KEY_RE.search(str(key)))


def _identity_key(key: Any) -> str:
    normalized = str(key).lower()
    if normalized in USER_KEYS:
        return "user"
    if normalized in TLS_CN_KEYS:
        return "tls-cn"
    if normalized in CA_KEYS:
        return "ca"
    return ""


def _cli_connection_flags(argv: list[str]) -> list[str]:
    found: list[str] = []
    for arg in argv:
        for flag in CLI_CONNECTION_FLAGS:
            if arg == flag or arg.startswith(flag + "="):
                found.append(flag)
    return sorted(set(found))


def _replace_identity_text(text: str, needle: str, replacement: str) -> str:
    if not needle:
        return text
    pattern = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(needle)}(?![A-Za-z0-9_.-])")
    return pattern.sub(replacement, text)


def _http_url_host(http_url: str = "") -> str:
    if not http_url:
        return ""
    try:
        return urllib.parse.urlsplit(http_url).hostname or ""
    except ValueError:
        return ""


def _sanitize_text(
    value: str,
    host: str = "",
    username: str = "",
    tls_cn: str = "",
    ca_path: str = "",
    extra_hosts: tuple[str, ...] = (),
) -> str:
    text = value
    uid_placeholders: dict[str, str] = {}

    def protect_uid(match: re.Match[str]) -> str:
        placeholder = f"__AXXON_INTRINSIC_UID_{len(uid_placeholders)}__"
        uid_placeholders[placeholder] = match.group(0)
        return placeholder

    text = INTRINSIC_UID_RE.sub(protect_uid, text)
    text = URL_USERINFO_RE.sub(lambda m: f"{m.group('prefix')}<redacted-userinfo>@", text)
    for item in (host, *extra_hosts):
        if item:
            text = text.replace(item, "<demo-host>")
    if ca_path:
        text = text.replace(ca_path, "<redacted-ca>")
    text = CA_PATH_TEXT_RE.sub("<redacted-ca>", text)
    text = _replace_identity_text(text, username, "<demo-user>")
    text = _replace_identity_text(text, tls_cn, "<demo-tls-cn>")
    text = BEARER_RE.sub("Bearer <redacted>", text)
    text = QUOTED_SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}<redacted>", text)
    text = UNQUOTED_SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}<redacted>", text)
    for placeholder, uid in uid_placeholders.items():
        text = text.replace(placeholder, uid)
    return text


def sanitize_evidence(
    value: Any,
    host: str = "",
    username: str = "",
    tls_cn: str = "",
    ca_path: str = "",
    extra_hosts: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            identity = _identity_key(key)
            if identity == "user":
                out[key] = "<demo-user>" if item else item
            elif identity == "tls-cn":
                out[key] = "<demo-tls-cn>" if item else item
            elif identity == "ca":
                out[key] = "<redacted-ca>" if item else item
            elif _secret_key(key):
                if isinstance(item, str) and BEARER_RE.search(item):
                    out[key] = _sanitize_text(item, host, username, tls_cn, ca_path, extra_hosts)
                else:
                    out[key] = "<redacted>" if item else item
            else:
                out[key] = sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts)
        return out
    if isinstance(value, list):
        return [sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts) for item in value]
    if isinstance(value, tuple):
        return [sanitize_evidence(item, host, username, tls_cn, ca_path, extra_hosts) for item in value]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, str):
        return _sanitize_text(value, host, username, tls_cn, ca_path, extra_hosts)
    return value


def report_paths(report_dir: Path, stamp: str) -> dict[str, Path]:
    return {
        "json": report_dir / f"{REPORT_BASENAME}-{stamp}.json",
        "md": report_dir / f"{REPORT_BASENAME}-{stamp}.md",
        "latest_json": report_dir / f"{LATEST_BASENAME}.json",
        "latest_md": report_dir / f"{LATEST_BASENAME}.md",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--notifier-timeout", type=float, default=DEFAULT_NOTIFIER_TIMEOUT)
    parser.add_argument("--notifier-limit", type=int, default=DEFAULT_NOTIFIER_LIMIT)
    parser.add_argument("--notifier-subject", action="append", dest="notifier_subjects", default=[])
    parser.add_argument("--notifier-event-type", action="append", dest="notifier_event_types", default=[])
    parser.add_argument("--notifier-detailed", action="store_true")
    parser.add_argument("--include-node-notifier", action="store_true")
    parser.add_argument("--role-page-size", type=int, default=50)
    parser.add_argument("--schedule-uid", default=os.getenv("AXXON_SCHEDULE_UID", ""))
    parser.add_argument("--verbose", action="store_true")
    forbidden = _cli_connection_flags(raw_argv)
    if forbidden:
        parser.error(
            "connection and credential options must come from environment/config, not CLI: "
            + ", ".join(forbidden)
        )
    args = parser.parse_args(raw_argv)
    args.notifier_timeout = _clamp_float(args.notifier_timeout, NOTIFIER_TIMEOUT_MIN, NOTIFIER_TIMEOUT_MAX)
    args.notifier_limit = _clamp_int(args.notifier_limit, NOTIFIER_LIMIT_MIN, NOTIFIER_LIMIT_MAX)
    args.role_page_size = _clamp_int(args.role_page_size, ROLE_PAGE_SIZE_MIN, ROLE_PAGE_SIZE_MAX)
    return args


def result_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = str(payload.get("status") or "").lower()
        if status in {"ok", "pass", "connected"}:
            return "PASS"
        if status in {"fixture-needed", "skipped", "gap", "warn", "warning", "partial"}:
            return "WARN"
        if status in {"error", "fail", "failed", "rejected"}:
            return "FAIL"
        if status:
            return "WARN"
    return "PASS"


class AdminSmoke:
    def __init__(self, args: argparse.Namespace, *, tool: Any | None = None) -> None:
        self.args = args
        self.started_at = dt.datetime.now(dt.UTC)
        self.tool = tool or AxxonMcpAdmin(config_factory=lambda: config_from_args(args))
        self.results: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}

    @property
    def host(self) -> str:
        try:
            client = self.tool.ensure_client()
            return str(getattr(getattr(client, "config", None), "host", self.args.host))
        except Exception:
            return str(self.args.host)

    def sanitize_extra_hosts(self) -> tuple[str, ...]:
        http_host = _http_url_host(str(getattr(self.args, "http_url", "")))
        return tuple(host for host in (http_host,) if host and host != self.host)

    def sanitize(self, value: Any) -> Any:
        return sanitize_evidence(
            value,
            self.host,
            username=self.args.username,
            tls_cn=self.args.tls_cn,
            ca_path=str(self.args.ca),
            extra_hosts=self.sanitize_extra_hosts(),
        )

    def record(self, group: str, func: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        try:
            evidence = func()
            status = result_status(evidence)
        except Exception as exc:  # noqa: BLE001 - live smoke reports structured failures.
            evidence = {"status": "error", "error_type": exc.__class__.__name__, "message": str(exc)[:800]}
            if self.args.verbose:
                import traceback

                evidence["traceback"] = traceback.format_exc()
            status = "FAIL"
        clean = self.sanitize(evidence)
        self.results.append(
            {
                "group": group,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "evidence": clean,
            }
        )
        return evidence

    def run(self) -> dict[str, Any]:
        self.record("connect", lambda: self.tool.admin_connect_axxon_profile("env"))
        inventory = self.record("security_inventory", self.tool.security_inventory)
        self.context["security_inventory"] = inventory if isinstance(inventory, dict) else {}
        self.record("security_policy_summary", self.tool.security_policy_summary)
        role_id = self.role_id()
        if role_id:
            self.record("role_permissions", lambda: self.tool.role_permissions(role_id, page_size=self.args.role_page_size))
        else:
            self.record("role_permissions", lambda: self.fixture_needed("role_permissions", "No role id was discovered."))
        self.record("current_user_security", self.tool.current_user_security)
        self.record("license_status", self.tool.license_status)
        self.record("time_status", self.tool.time_status)
        self.record("system_health", self.tool.system_health)
        self.record("domain_event_subscribe", self.domain_event_subscribe)
        if self.args.include_node_notifier:
            self.record("node_event_subscribe", self.node_event_subscribe)
        uid = self.schedule_uid()
        if uid:
            self.record("schedule_descriptor_get", lambda: self.tool.schedule_descriptor_get(uid))
        else:
            self.record(
                "schedule_descriptor_get",
                lambda: self.fixture_needed("schedule_descriptor_get", "No schedule descriptor fixture UID was discovered."),
            )
        report = self.report()
        self.write_report(report)
        return report

    def domain_event_subscribe(self) -> dict[str, Any]:
        return self.tool.domain_event_subscribe(
            subjects=self.args.notifier_subjects,
            event_types=self.args.notifier_event_types,
            timeout_s=self.args.notifier_timeout,
            limit=self.args.notifier_limit,
            detailed=self.args.notifier_detailed,
        )

    def node_event_subscribe(self) -> dict[str, Any]:
        return self.tool.node_event_subscribe(
            subjects=self.args.notifier_subjects,
            event_types=self.args.notifier_event_types,
            timeout_s=self.args.notifier_timeout,
            limit=self.args.notifier_limit,
            detailed=self.args.notifier_detailed,
        )

    def role_id(self) -> str:
        roles = ((self.context.get("security_inventory") or {}).get("roles") or {}).get("items") or []
        for role in roles:
            if not isinstance(role, dict):
                continue
            if str(role.get("name") or "").lower() == "admin":
                return str(role.get("id") or role.get("index") or role.get("role_id") or role.get("roleId") or "")
        for role in roles:
            if isinstance(role, dict):
                value = role.get("id") or role.get("index") or role.get("role_id") or role.get("roleId")
                if value:
                    return str(value)
        return ""

    def schedule_uid(self) -> str:
        if self.args.schedule_uid:
            return str(self.args.schedule_uid)
        client = None
        ensure_client = getattr(self.tool, "ensure_client", None)
        if callable(ensure_client):
            try:
                client = ensure_client()
            except Exception:
                client = None
        if client is None:
            return ""
        inventory = getattr(client, "inventory", None) or {}
        if not inventory:
            load_inventory = getattr(client, "load_inventory", None)
            if callable(load_inventory):
                try:
                    inventory = load_inventory()
                except Exception:
                    inventory = {}
        for collection in ("cameras", "config_units", "components"):
            for item in inventory.get(collection, []):
                if not isinstance(item, dict):
                    continue
                value = str(item.get("uid") or item.get("access_point") or item.get("accessPoint") or "")
                if "/SourceEndpoint." in value:
                    value = value.split("/SourceEndpoint.", 1)[0]
                if value:
                    return value
        return ""

    def fixture_needed(self, tool: str, message: str) -> dict[str, Any]:
        return {"status": "fixture-needed", "tool": tool, "message": message}

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
                "read_only": True,
                "include_node_notifier": bool(self.args.include_node_notifier),
            },
            "defaults": {
                "notifier_timeout": self.args.notifier_timeout,
                "notifier_limit": self.args.notifier_limit,
                "role_page_size": self.args.role_page_size,
                "schedule_uid_provided": bool(self.args.schedule_uid),
            },
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
            "# Axxon One Phase 5F Admin Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{report['target']['grpc_target']}`",
            f"- HTTP target: `{report['target']['http_url']}`",
            f"- Node notifier: `{report['modes']['include_node_notifier']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            note = self.note_for(result).replace("|", "\\|")[:240]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        evidence = result.get("evidence") or {}
        if isinstance(evidence, dict):
            if evidence.get("message"):
                return str(evidence["message"])
            if evidence.get("error_type"):
                return f"{evidence.get('error_type')}: {evidence.get('message', '')}"
            if evidence.get("tool"):
                return f"tool={evidence['tool']} keys={sorted(evidence.keys())}"
            return f"keys={sorted(evidence.keys())}"
        return str(evidence)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = AdminSmoke(args).run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
