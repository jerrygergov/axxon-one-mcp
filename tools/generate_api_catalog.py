#!/usr/bin/env python3
"""Generate Axxon One gRPC/HTTP API catalogs from local proto files."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re


RPC_RE = re.compile(
    r"rpc\s+(?P<name>\w+)\s*\(\s*(?P<client_stream>stream\s+)?(?P<request>[\w.]+)\s*\)\s*"
    r"returns\s*\(\s*(?P<server_stream>stream\s+)?(?P<response>[\w.]+)\s*\)"
)
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;")
SERVICE_RE = re.compile(r"^\s*service\s+(\w+)\s*")
HTTP_VERB_RE = re.compile(r'^\s*(get|post|put|delete|patch)\s*:\s*"([^"]+)"')


READ_PREFIXES = (
    "Get",
    "List",
    "BatchGet",
    "Read",
    "Find",
    "Search",
    "Check",
    "Enumerate",
    "Probe",
    "Acquire",
    "Download",
    "Collect",
    "Is",
)
MUTATING_PREFIXES = (
    "Set",
    "Update",
    "Change",
    "Create",
    "Delete",
    "Remove",
    "Drop",
    "Bind",
    "Unbind",
    "Add",
    "Perform",
    "Raise",
    "Launch",
    "Start",
    "Stop",
    "Cancel",
    "Close",
    "Renew",
    "Approve",
    "Decline",
    "Inject",
    "Send",
    "Restore",
    "Format",
    "Resize",
    "Clear",
    "Reindex",
    "Register",
    "Unregister",
    "Configure",
    "Release",
    "KeepAlive",
    "Move",
    "Zoom",
    "Focus",
)

KNOWN_LIVE_STATUS = {
    "axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2": "tested-pass",
    "axxonsoft.bl.domain.DomainService.GetVersion": "tested-pass",
    "axxonsoft.bl.domain.DomainService.GetHostPlatformInfo": "tested-pass",
    "axxonsoft.bl.domain.DomainService.GetHostTimeZone": "tested-pass",
    "axxonsoft.bl.domain.DomainService.ListNodes": "tested-pass",
    "axxonsoft.bl.domain.DomainService.ListCameras": "tested-pass",
    "axxonsoft.bl.domain.DomainService.BatchGetCameras": "tested-pass",
    "axxonsoft.bl.domain.DomainService.ListArchives": "tested-pass",
    "axxonsoft.bl.domain.DomainService.ListComponents": "tested-pass",
    "axxonsoft.bl.config.ConfigurationService.ListUnits": "tested-pass",
    "axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPoints": "tested-pass",
    "axxonsoft.bl.config.ConfigurationService.ListTemplates": "tested-pass",
    "axxonsoft.bl.config.ConfigurationService.ChangeTemplates": "tested-pass-safe-record",
    "axxonsoft.bl.config.ConfigurationService.SetTemplateAssignments": "tested-pass-safe-record",
    "axxonsoft.bl.config.ConfigurationService.BatchGetTemplates": "tested-pass-safe-record",
    "axxonsoft.bl.archive.ArchiveService.GetArchiveTraits": "tested-pass",
    "axxonsoft.bl.archive.ArchiveService.GetVolumesState": "tested-pass",
    "axxonsoft.bl.archive.ArchiveService.GetDiskSpace": "tested-pass",
    "axxonsoft.bl.archive.ArchiveService.FormatVolumes": "tested-pass-safe-record",
    "axxonsoft.bl.archive.ArchiveService.Reindex": "tested-pass-safe-record",
    "axxonsoft.bl.archive.ArchiveService.CancelReindex": "tested-pass-safe-record",
    "axxonsoft.bl.archive.ArchiveService.GetHistory2": "tested-pass",
    "axxonsoft.bl.metadata.MetadataService.PullMetadata": "tested-pass",
    "axxonsoft.bl.mmexport.ExportService.ListSessions": "tested-pass",
    "axxonsoft.bl.mmexport.ExportService.StartSession": "tested-pass-safe-record",
    "axxonsoft.bl.mmexport.ExportService.GetSessionState": "tested-pass",
    "axxonsoft.bl.mmexport.ExportService.StopSession": "tested-pass-safe-record",
    "axxonsoft.bl.mmexport.ExportService.DestroySession": "tested-pass-safe-record",
    "axxonsoft.bl.mmexport.ExportService.DownloadFile": "tested-pass",
    "axxonsoft.bl.settings.DomainSettingsService.UpdateExportSettings": "tested-pass-safe-record",
    "axxonsoft.bl.security.SecurityService.ChangeConfig": "tested-pass-safe-record",
    "axxonsoft.bl.security.SecurityService.SetGlobalPermissions": "tested-pass-safe-record",
    "axxonsoft.bl.security.SecurityService.SetGroupsPermissions": "tested-pass-safe-record",
    "axxonsoft.bl.security.SecurityService.SetObjectPermissions": "tested-pass-safe-record",
    "axxonsoft.bl.security.SecurityService.SetMacrosPermissions": "tested-pass-safe-record",
    "axxonsoft.bl.license.LicenseService.LicenseKeyInfo": "tested-pass",
    "axxonsoft.bl.license.LicenseService.GetGlobalRestrictions": "tested-pass",
    "axxonsoft.bl.license.LicenseService.GetNodeRestrictions": "tested-pass",
    "axxonsoft.bl.license.LicenseService.IsPossibleToLaunch": "tested-pass",
    "axxonsoft.bl.statistics.StatisticService.GetStatistics": "tested-pass",
    "axxonsoft.bl.events.EventHistoryService.ReadCount": "tested-pass",
    "axxonsoft.bl.events.EventHistoryService.ReadEvents": "tested-pass",
    "axxonsoft.bl.events.EventHistoryService.ReadLprEvents": "tested-pass-empty",
    "axxonsoft.bl.config.SharedKVStorageService.Commit": "tested-pass-safe-record",
    "axxonsoft.bl.config.SharedKVStorageService.BatchGetRecords": "tested-pass",
    "axxonsoft.bl.config.SharedKVStorageService.GetRecordsStream": "tested-pass",
    "axxonsoft.bl.logic.LogicService.ChangeMacros": "tested-pass-safe-record",
    "axxonsoft.bl.maps.MapService.ChangeMaps": "tested-pass-safe-record",
    "axxonsoft.bl.maps.MapService.GetMapImage": "tested-pass-safe-record",
    "axxonsoft.bl.maps.MapService.GetMarkers": "tested-pass-safe-record",
    "axxonsoft.bl.maps.MapService.UpdateMarkers": "tested-pass-safe-record",
}
EXTRA_LIVE_STATUS: dict[str, str] = {}


@dataclass
class Rpc:
    package: str
    service: str
    method: str
    request: str
    response: str
    client_stream: bool
    server_stream: bool
    proto: str
    http: list[tuple[str, str]] = field(default_factory=list)

    @property
    def fqmn(self) -> str:
        return f"{self.package}.{self.service}.{self.method}"

    @property
    def streaming(self) -> str:
        if self.client_stream and self.server_stream:
            return "bidi"
        if self.client_stream:
            return "client"
        if self.server_stream:
            return "server"
        return "none"

    @property
    def safety(self) -> str:
        if self.http and any(verb in {"POST", "PUT", "DELETE", "PATCH"} for verb, _ in self.http):
            if self.method.startswith(READ_PREFIXES):
                return "review"
            return "mutating"
        if self.method.startswith(MUTATING_PREFIXES):
            return "mutating"
        if self.method.startswith(READ_PREFIXES):
            return "read"
        if self.server_stream and self.method.startswith(("Pull", "Stream", "Await")):
            return "stream_read"
        return "review"

    @property
    def live_status(self) -> str:
        return EXTRA_LIVE_STATUS.get(self.fqmn, KNOWN_LIVE_STATUS.get(self.fqmn, "pending"))


def parse_proto(path: Path, root: Path) -> list[Rpc]:
    package = ""
    service = ""
    service_depth = 0
    current_rpc: Rpc | None = None
    in_http = False
    methods: list[Rpc] = []
    rel = path.relative_to(root).as_posix()
    for line in path.read_text(errors="replace").splitlines():
        package_match = PACKAGE_RE.search(line)
        if package_match:
            package = package_match.group(1)

        service_match = SERVICE_RE.search(line)
        if service_match:
            service = service_match.group(1)
            service_depth = line.count("{") - line.count("}")
            continue

        if service:
            service_depth += line.count("{") - line.count("}")
            if service_depth <= 0 and "}" in line:
                service = ""
                current_rpc = None
                in_http = False
                continue

        if not service:
            continue

        rpc_match = RPC_RE.search(line)
        if rpc_match:
            current_rpc = Rpc(
                package=package,
                service=service,
                method=rpc_match.group("name"),
                request=rpc_match.group("request"),
                response=rpc_match.group("response"),
                client_stream=bool(rpc_match.group("client_stream")),
                server_stream=bool(rpc_match.group("server_stream")),
                proto=rel,
            )
            methods.append(current_rpc)
            in_http = False
            continue

        if current_rpc and "option (google.api.http)" in line:
            in_http = True
            continue

        if current_rpc and in_http:
            http_match = HTTP_VERB_RE.search(line)
            if http_match:
                current_rpc.http.append((http_match.group(1).upper(), http_match.group(2)))
            if "}" in line:
                in_http = False

    return methods


def parse_all(proto_root: Path) -> list[Rpc]:
    methods: list[Rpc] = []
    for path in sorted((proto_root / "axxonsoft").rglob("*.proto")):
        methods.extend(parse_proto(path, proto_root))
    return methods


def load_live_report(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    statuses: dict[str, str] = {}
    for result in data.get("results", []):
        fqmn = result.get("fqmn")
        if not fqmn:
            continue
        if fqmn in KNOWN_LIVE_STATUS:
            continue
        status = result.get("status")
        if status == "PASS":
            statuses[fqmn] = "tested-pass"
        elif status == "WARN":
            statuses[fqmn] = "tested-warn-fixture-needed"
        elif status == "FAIL":
            statuses[fqmn] = "tested-fail"
    return statuses


def load_summary(path: Path) -> dict[str, int] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    summary = data.get("summary")
    return summary if isinstance(summary, dict) else None


def write_csv(methods: list[Rpc], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "package",
                "service",
                "method",
                "fqmn",
                "request",
                "response",
                "streaming",
                "safety",
                "live_status",
                "http",
                "proto",
            ]
        )
        for rpc in methods:
            writer.writerow(
                [
                    rpc.package,
                    rpc.service,
                    rpc.method,
                    rpc.fqmn,
                    rpc.request,
                    rpc.response,
                    rpc.streaming,
                    rpc.safety,
                    rpc.live_status,
                    "; ".join(f"{verb} {route}" for verb, route in rpc.http),
                    rpc.proto,
                ]
            )


def write_markdown(methods: list[Rpc], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    services: dict[tuple[str, str, str], list[Rpc]] = {}
    for rpc in methods:
        services.setdefault((rpc.package, rpc.service, rpc.proto), []).append(rpc)

    http_count = sum(len(rpc.http) for rpc in methods)
    tested_count = sum(1 for rpc in methods if rpc.live_status != "pending")
    lines = [
        "# Axxon One API Audit Catalog",
        "",
        "Generated from local proto files.",
        "",
        "## Totals",
        "",
        f"- Services: {len(services)}",
        f"- RPC methods: {len(methods)}",
        f"- HTTP annotations: {http_count}",
        f"- Live-tested RPC methods recorded: {tested_count}",
        "",
        "## Safety Buckets",
        "",
    ]
    for bucket, count in sorted(Counter(rpc.safety for rpc in methods).items()):
        lines.append(f"- `{bucket}`: {count}")

    lines.extend(
        [
            "",
            "## Service Matrix",
            "",
            "| Package | Service | RPCs | HTTP | Read | Mutating | Review | Tested | Proto |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for (package, service, proto), rpcs in sorted(services.items()):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{package}`",
                    f"`{service}`",
                    str(len(rpcs)),
                    str(sum(len(rpc.http) for rpc in rpcs)),
                    str(sum(1 for rpc in rpcs if rpc.safety in {"read", "stream_read"})),
                    str(sum(1 for rpc in rpcs if rpc.safety == "mutating")),
                    str(sum(1 for rpc in rpcs if rpc.safety == "review")),
                    str(sum(1 for rpc in rpcs if rpc.live_status != "pending")),
                    f"`{proto}`",
                ]
            )
            + " |"
        )

    lines.extend(["", "## RPC Matrix", ""])
    for (package, service, proto), rpcs in sorted(services.items()):
        lines.extend(
            [
                f"### `{package}.{service}`",
                "",
                f"Proto: `{proto}`",
                "",
                "| Method | Request | Response | Stream | Safety | HTTP | Live |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for rpc in rpcs:
            http = "<br>".join(f"`{verb} {route}`" for verb, route in rpc.http) or ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{rpc.method}`",
                        f"`{rpc.request}`",
                        f"`{rpc.response}`",
                        f"`{rpc.streaming}`",
                        f"`{rpc.safety}`",
                        http,
                        f"`{rpc.live_status}`",
                    ]
                )
                + " |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_http_markdown(methods: list[Rpc], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(rpc, verb, route) for rpc in methods for verb, route in rpc.http]
    lines = [
        "# Axxon One HTTP Endpoint Catalog",
        "",
        "Generated from `google.api.http` annotations in local proto files.",
        "",
        f"- Endpoints: {len(rows)}",
        "",
        "| Verb | Path | gRPC Method | Safety | Live | Proto |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rpc, verb, route in sorted(rows, key=lambda item: (item[2], item[0].fqmn)):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{verb}`",
                    f"`{route}`",
                    f"`{rpc.fqmn}`",
                    f"`{rpc.safety}`",
                    f"`{rpc.live_status}`",
                    f"`{rpc.proto}`",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(methods: list[Rpc], out_dir: Path) -> None:
    services = {(rpc.package, rpc.service) for rpc in methods}
    http_count = sum(len(rpc.http) for rpc in methods)
    read_count = sum(1 for rpc in methods if rpc.safety in {"read", "stream_read"})
    mutating_count = sum(1 for rpc in methods if rpc.safety == "mutating")
    review_count = sum(1 for rpc in methods if rpc.safety == "review")
    tested_count = sum(1 for rpc in methods if rpc.live_status != "pending")
    lines = [
        "# Axxon One API Audit",
        "",
        "This folder tracks the one-by-one gRPC and HTTP API audit for plugin and vertical integration work.",
        "",
        "## Generated Artifacts",
        "",
        "- `grpc-api-catalog.md`: service-by-service RPC catalog.",
        "- `grpc-api-catalog.csv`: machine-readable RPC catalog.",
        "- `http-endpoints-catalog.md`: HTTP endpoint catalog from proto annotations.",
        "- `live-readonly-sweep-latest.md`: latest conservative live gRPC read sweep.",
        "- `live-readonly-sweep-latest.json`: machine-readable latest conservative live gRPC read sweep.",
        "- `http-grpc-sweep-latest.md`: latest HTTP `/grpc` parity sweep.",
        "- `http-grpc-sweep-latest.json`: machine-readable latest HTTP `/grpc` parity sweep.",
        "- `http-v1-sweep-latest.md`: latest safe `/v1` GET and read-like POST endpoint sweep.",
        "- `http-v1-sweep-latest.json`: machine-readable latest safe `/v1` endpoint sweep.",
        "- `mutating-fixture-sweep-latest.md`: latest controlled low-risk mutating fixture sweep.",
        "- `mutating-fixture-sweep-latest.json`: machine-readable latest controlled mutating fixture sweep.",
        "- `export-preflight-latest.md`: latest read-only export sessions/settings/fixture preflight.",
        "- `export-smoke-latest.md`: latest controlled gRPC export lifecycle smoke.",
        "- `http-export-smoke-latest.md`: latest controlled legacy HTTP export lifecycle smoke.",
        "- `archive-management-noop-smoke-latest.md`: latest no-op archive-management dispatch smoke.",
        "- `delete-video-noop-probe-latest.md`: latest no-op dispatch probe for the PDF legacy HTTP delete-video endpoint.",
        "- `mcp-live-smoke-latest.md`: latest read-only MCP live-inspection smoke against the demo stand.",
        "- `mcp-corpus/`: Phase 0 structured corpus and Phase 1 docs-query notes for the planned public Axxon One MCP server.",
        "- `pdf-gap-coverage-matrix.md`: machine-trackable PDF gap status, risk, tooling, report, and next step matrix.",
        "- `pdf-gap-coverage-summary.md`: summary counts and final gap disposition.",
        "- `client-sdk-usage.md`: reusable Python client examples for direct gRPC, HTTP `/grpc`, `/v1`, inventory, and archive fixtures.",
        "- `read-fixture-notes.md`: read-only fixture fixes and remaining subsystem-required warning groups.",
        "- `integration-playbooks.md`: API choices for common plugin and vertical-integration patterns.",
        "- `mutating-api-fixtures.md`: fixture and rollback strategy for write/destructive APIs.",
        "",
        "## Current Coverage",
        "",
        f"- Services: {len(services)}",
        f"- RPC methods: {len(methods)}",
        f"- HTTP annotations: {http_count}",
        f"- Read or stream-read heuristic: {read_count}",
        f"- Mutating heuristic: {mutating_count}",
        f"- Needs manual safety review: {review_count}",
        f"- Live-tested method entries already recorded: {tested_count}",
        "",
        "## Latest Sweep Results",
        "",
    ]
    for label, filename in (
        ("Direct gRPC read sweep", "live-readonly-sweep-latest.json"),
        ("HTTP `/grpc` parity sweep", "http-grpc-sweep-latest.json"),
        ("HTTP `/v1` safe endpoint sweep", "http-v1-sweep-latest.json"),
        ("Controlled mutating fixture sweep", "mutating-fixture-sweep-latest.json"),
    ):
        summary = load_summary(out_dir / filename)
        if summary is None:
            lines.append(f"- {label}: not run yet")
        else:
            lines.append(
                f"- {label}: PASS={summary.get('PASS', 0)}, "
                f"WARN={summary.get('WARN', 0)}, FAIL={summary.get('FAIL', 0)}"
            )
    lines.extend(
        [
            "- Demo-stand export preflight on 2026-05-11: PASS=3, WARN=1, FAIL=0; export sessions/settings, current archive interval discovery, and `hosts/Server/MMExportAgent.0` fixture discovery pass.",
            "- Demo-stand gRPC export lifecycle on 2026-05-11: PASS=2, WARN=0, FAIL=0; temporary `codex-*` archive snapshot export completed and downloaded a bounded JPEG result, then destroyed the session; temporary live export reached `S_RUNNING`, then stop/destroy cleanup passed.",
            "- Demo-stand legacy HTTP export lifecycle on 2026-05-11: PASS=1, WARN=0, FAIL=0; `POST /export/archive/...` returned HTTP 202, `GET /export/{id}/status` reached state 2, bounded `GET /export/{id}/file` returned JPEG bytes, and `DELETE /export/{id}` returned HTTP 204.",
            "- Demo-stand security mutation lifecycle on 2026-05-11: PASS=1, WARN=0, FAIL=0; temporary UUID-indexed `codex-*` role/user lifecycle, generated in-memory password set, temp-role global/object/group/macro permission updates, no-op password-policy/IP-filter/trusted-IP writes, temporary LDAP directory add/edit/remove, and rollback to baseline counts passed.",
            "- Demo-stand archive management no-op smoke on 2026-05-12: PASS=5, WARN=0, FAIL=0; no-op `FormatVolumes`, `Reindex`, and `CancelReindex` dispatch against a `codex-nonexistent-*` volume id returned `NOT_FOUND` or empty responses, and the fake volume remained absent before and after.",
            "- Demo-stand delete-video no-op probe on 2026-05-12: PASS=1, WARN=0, FAIL=0; the PDF `DELETE /archive/contents/bookmarks/` shape reached the server and returned HTTP 404 for a `codex-nonexistent-*` endpoint/storage pair without targeting real archive data.",
            "- Demo-stand fixture disposition on 2026-05-12: FOUND=5, MISSING=5, WARN=0; export agent, maps, detectors, RTSP playback, and the embeddable component at `/embedded.html` are present, while PTZ telemetry, control panels, water-level devices, and Client HTTP API remain missing. WebSocket `/events` still upgrades then closes during receive.",
            "- MCP Phase 0 corpus on 2026-05-12: generated `api_methods.json` with 361 gRPC methods, `http_endpoints.json` with 221 annotated endpoints, `task_recipes.json`, `fixtures.json`, `safety_policies.json`, and `known_behaviors.json`.",
            "- MCP Phase 1 docs-only server foundation on 2026-05-12: `arm64-docker/tools/axxon_mcp_docs.py` serves the corpus without credentials, `arm64-docker/tools/axxon_mcp_server.py` wraps it in FastMCP tools/resources, and unknown APIs return explicit `gap` results.",
            "- MCP Phase 2 read-only live inspection foundation on 2026-05-12: `arm64-docker/tools/axxon_mcp_live.py` reuses `AxxonApiClient` for redacted inventory summaries and fixture preflight; `axxon_mcp_server.py --enable-live` exposes live tools only when explicitly enabled.",
            "- MCP live-inspection demo smoke on 2026-05-12: read-only inventory summary returned 33 cameras, 14 archives, 35 detector entries, 18 AppDataDetector entries, 51 event suppliers, and 15 metadata endpoints; `subscribe detector events` preflight is `ready`.",
        ]
    )

    lines.extend(
        [
            "",
            "## Audit Rules",
            "",
            "- Use local proto definitions as the source of truth for method signatures.",
            "- Prefer live direct-gRPC tests for exact behavior.",
            "- Use HTTP `/grpc` and annotated `/v1/...` endpoints for HTTP parity checks.",
            "- Never run destructive/mutating APIs without an explicit fixture and rollback plan.",
            "- Record every live test result in generated or handwritten docs.",
            "- Keep credentials, tokens, serial numbers, and license keys out of docs.",
            "",
            "## Status Buckets",
            "",
            "- `tested-pass`: live tested successfully.",
            "- `tested-pass-empty`: API call works but returned no rows on this server.",
            "- `tested-pass-safe-record`: live tested with an isolated temporary record.",
            "- `tested-warn-fixture-needed`: live call reached the server but needs a better fixture, active subsystem, or non-empty parameter.",
            "- `tested-fail`: live test failed due to a tool or unexpected server error and needs investigation.",
            "- `pending`: not yet live tested.",
            "",
            "## Commands",
            "",
            "Use the reusable local API client in new tools:",
            "",
            "```text",
            "arm64-docker/tools/axxon_api_client.py",
            "```",
            "",
            "See:",
            "",
            "```text",
            "arm64-docker/docs/api-audit/client-sdk-usage.md",
            "```",
            "",
            "Runnable integration examples:",
            "",
            "```text",
            "arm64-docker/tools/examples/",
            "```",
            "",
            "Current core tools using the reusable client path: `axxon_api_probe.py`, "
            "`axxon_readonly_sweep.py`, `axxon_event_search.py`, `axxon_http_grpc_sweep.py`, "
            "`axxon_http_v1_sweep.py`, and `arm64-docker/tools/examples/`.",
            "",
            "Regenerate the proto-derived catalogs:",
            "",
            "```bash",
            "./arm64-docker/tools/generate_api_catalog.py",
            "```",
            "",
            "Run the conservative direct-gRPC read sweep:",
            "",
            "```bash",
            "AXXON_USERNAME=root AXXON_PASSWORD='<password>' \\",
            "/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_readonly_sweep.py",
            "```",
            "",
            "Run HTTP `/grpc` parity for direct-gRPC-passing unary read methods:",
            "",
            "```bash",
            "AXXON_USERNAME=root AXXON_PASSWORD='<password>' \\",
            "/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_grpc_sweep.py",
            "```",
            "",
            "Run the safe `/v1` GET plus read-like POST endpoint sweep:",
            "",
            "```bash",
            "AXXON_USERNAME=root AXXON_PASSWORD='<password>' \\",
            "/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_v1_sweep.py",
            "```",
            "",
            "Run the controlled SharedKV mutating fixture with rollback:",
            "",
            "```bash",
            "AXXON_USERNAME=root AXXON_PASSWORD='<password>' \\",
            "/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_mutating_fixture_sweep.py",
            "```",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--proto-root", type=Path, default=repo_root / "docs/grpc-proto-files")
    parser.add_argument("--out-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument(
        "--live-report",
        type=Path,
        action="append",
        help="Optional live sweep JSON report to fold into method statuses.",
    )
    args = parser.parse_args()

    global EXTRA_LIVE_STATUS
    live_reports = args.live_report or [args.out_dir / "live-readonly-sweep-latest.json"]
    EXTRA_LIVE_STATUS = {}
    for report in live_reports:
        EXTRA_LIVE_STATUS.update(load_live_report(report))

    methods = parse_all(args.proto_root)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(methods, args.out_dir / "grpc-api-catalog.csv")
    write_markdown(methods, args.out_dir / "grpc-api-catalog.md")
    write_http_markdown(methods, args.out_dir / "http-endpoints-catalog.md")
    write_readme(methods, args.out_dir)
    print(f"Generated {len(methods)} RPC methods into {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
