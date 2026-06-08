#!/usr/bin/env python3
"""Generate the Phase 0 structured corpus for a future Axxon One MCP server."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any


CORPUS_FILES = [
    "api_methods.json",
    "http_endpoints.json",
    "task_recipes.json",
    "fixtures.json",
    "safety_policies.json",
    "known_behaviors.json",
]


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def coverage_counts(matrix: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in matrix:
        status = str(row.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def load_api_methods(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        rows = csv.DictReader(file)
        return [
            {
                "package": row.get("package", ""),
                "service": row.get("service", ""),
                "method": row.get("method", ""),
                "fqmn": row.get("fqmn", ""),
                "request": row.get("request", ""),
                "response": row.get("response", ""),
                "streaming": row.get("streaming", ""),
                "safety_class": row.get("safety", ""),
                "live_status": row.get("live_status", ""),
                "http_annotation": row.get("http", ""),
                "proto": row.get("proto", ""),
            }
            for row in rows
        ]


def parse_http_catalog(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    endpoints: list[dict[str, str]] = []
    table_re = re.compile(
        r"^\|\s*`(?P<verb>[^`]+)`\s*\|\s*`(?P<path>[^`]+)`\s*\|\s*`(?P<grpc>[^`]+)`\s*\|\s*`(?P<safety>[^`]+)`\s*\|\s*`(?P<live>[^`]+)`\s*\|\s*`(?P<proto>[^`]+)`\s*\|"
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = table_re.match(line)
        if not match:
            continue
        endpoints.append(
            {
                "verb": match.group("verb"),
                "path": match.group("path"),
                "grpc_method": match.group("grpc"),
                "safety_class": match.group("safety"),
                "live_status": match.group("live"),
                "proto": match.group("proto"),
                "source": str(path),
            }
        )
    return endpoints


def extract_task_recipes(playbook_path: Path) -> list[dict[str, str]]:
    if not playbook_path.exists():
        return []
    recipes: list[dict[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in playbook_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current_title:
                recipes.append(recipe_from_section(current_title, current_lines, playbook_path))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)
    if current_title:
        recipes.append(recipe_from_section(current_title, current_lines, playbook_path))
    return recipes


def recipe_from_section(title: str, lines: list[str], source: Path) -> dict[str, str]:
    body = "\n".join(line.strip() for line in lines if line.strip())
    return {
        "task": title,
        "summary": body[:600],
        "source": str(source),
    }


def fixture_needed_rows(matrix: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for row in matrix:
        if row.get("status") != "fixture-needed":
            continue
        rows.append(
            {
                "pdf_area": str(row.get("pdf_area", "")),
                "pages": str(row.get("pages", "")),
                "risk": str(row.get("risk", "")),
                "tooling": str(row.get("tooling", "")),
                "report": str(row.get("report", "")),
                "missing_fixture": str(row.get("next_step", "")),
            }
        )
    return rows


def safety_policies() -> dict[str, Any]:
    return {
        "default_mode": "read-only",
        "classes": {
            "safe-read": {"requires_approval": False, "limits": ["timeout"]},
            "bounded-stream": {"requires_approval": False, "limits": ["timeout", "event_count", "byte_count"]},
            "fixture-heavy": {"requires_approval": False, "limits": ["fixture_preflight", "timeout"]},
            "mutation": {"requires_approval": True, "limits": ["dry_run", "confirmation", "rollback", "audit_log"]},
            "external-client": {"requires_approval": True, "limits": ["fixture_preflight", "state_snapshot", "rollback"]},
        },
        "redaction": [
            "passwords",
            "bearer_tokens",
            "grpc_token_metadata",
            "license_keys",
            "serial_numbers",
            "full_plate_values",
            "raw_security_payloads",
            "raw_images",
            "raw_video",
        ],
    }


def known_behaviors(matrix: list[dict[str, Any]], audit_dir: Path) -> dict[str, Any]:
    rows = [
        {
            "topic": "coverage_status",
            "coverage_counts": coverage_counts(matrix),
            "source": str(audit_dir / "pdf-gap-coverage-matrix.json"),
        },
        {
            "topic": "legacy_http_bookmarks",
            "behavior": "Demo stand can read legacy HTTP bookmarks with Bearer auth; documented legacy HTTP create endpoints return HTTP 501. Use gRPC BookmarkService for a runnable lifecycle.",
            "source": str(audit_dir / "bookmark-smoke-latest.md"),
        },
        {
            "topic": "legacy_http_delete_video",
            "behavior": "PDF DELETE /archive/contents/bookmarks/ dispatch is verified only with a codex-nonexistent no-op target; real archive deletion remains maintenance-window work.",
            "source": str(audit_dir / "delete-video-noop-probe-latest.md"),
        },
        {
            "topic": "websocket_events",
            "behavior": "Demo Web server upgrades /events to HTTP 101 but closes during receive in the current fixture.",
            "source": str(audit_dir / "subscription-smoke-latest.md"),
        },
        {
            "topic": "archive_storage_source_resolution",
            "behavior": "Device-embedded /Sources/src.* access points (under DeviceIpint.*) appear in inventory but are unresolvable for ArchiveService.GetHistory2 on this demo stand. Use MultimediaStorage.*/Sources/src.* archive sources instead. Camera SourceEndpoint access points are not valid GetHistory2 targets.",
            "source": str(audit_dir / "mcp-live-smoke-latest.md"),
        },
        {
            "topic": "tfa_mutations_unverified",
            "behavior": "SecurityService.EnableGoogleAuth/DisableGoogleAuth (proto SecurityService.proto:1000-1002) are split into a dedicated fixture-needed row. No live TFA mutation evidence exists on the demo stand; an OTP/authenticator fixture plus an isolated test user are required before enable/disable can be exercised with rollback.",
            "source": str(audit_dir / "security-mutation-smoke-latest.md"),
        },
        {
            "topic": "archive_management_destructive_paths",
            "behavior": "FormatVolumes/Reindex/CancelReindex are verified only via no-op dispatch against codex-nonexistent volume ids; cloud archive and link operations are documented from the PDF only. Real format/reindex/cancel-reindex/cloud/link operations remain approval-only until an isolated storage fixture or explicit maintenance-window approval is in place.",
            "source": str(audit_dir / "archive-management-noop-smoke-latest.md"),
        },
        {
            "topic": "operator_temp_camera_live_verified",
            "behavior": "MCP Phase 3 operator workflow temp_camera was live-verified end-to-end against the demo stand on 2026-05-13: plan -> bad-confirmation reject -> apply -> verify -> rollback -> post-verify clean. Audit log records every action.",
            "source": str(audit_dir / "mcp-operator-smoke-latest.md"),
        },
        {
            "topic": "operator_workflows_2026_05_14",
            "behavior": "MCP Phase 3 operator exposes 7 workflows, all live-verified end-to-end on demo 2026-05-14: temp_camera, temp_archive, temp_av_detector, temp_appdata_detector, temp_device_template, external_event_inject, temp_macro. temp_appdata_detector is the only chained workflow: when no vmda_source_ap is supplied it first creates a SceneDescription AVDetector, waits on DomainService.ListComponents for the SourceEndpoint.vmda to publish, then creates the AppDataDetector. Rollback removes both in reverse order. temp_device_template uses ConfigurationService.ChangeTemplates over HTTP /grpc; temp_macro uses LogicService.ChangeMacros over direct gRPC with a client-generated GUID; external_event_inject uses /v1/detectors/external:raiseOccasionalEvent with bearer auth and RFC3339 timestamp (Z suffix).",
            "source": str(audit_dir / "mcp-operator-smoke-latest.md"),
        },
        {
            "topic": "external_event_timestamp_format",
            "behavior": "/v1/detectors/external:raiseOccasionalEvent requires RFC3339 timestamps with Z suffix (e.g. 2026-05-14T14:48:55.123456Z). The compact %Y%m%dT%H%M%S.fff form is rejected with 'timestamp string too short' (INVALID_ARGUMENT on google.protobuf.Timestamp).",
            "source": str(audit_dir / "mcp-operator-smoke-latest.md"),
        },
        {
            "topic": "scene_avdetector_publishes_vmda_endpoint",
            "behavior": "Creating an AVDetector with detector=SceneDescription against a video source AP causes the server to materialize a SourceEndpoint.vmda component endpoint under the new AVDetector UID (format: <av_uid>/SourceEndpoint.vmda). The endpoint is published asynchronously and shows up in DomainService.ListComponents within a couple of seconds. The MCP operator's temp_appdata_detector workflow exploits this to chain-create a vmda source on demand when the caller has none.",
            "source": str(audit_dir / "mcp-operator-smoke-latest.md"),
        },
        {
            "topic": "appdata_detector_kind_mismatch",
            "behavior": "AppDataDetector and AVDetector have disjoint detector enums. Passing AVDetector kinds (e.g. MotionDetection, SceneDescription, NeuroTracker) as the detector property of an AppDataDetector causes ConfigurationService.ChangeConfig to reject the add as malformed. Valid AppDataDetector kinds include MoveInZone and other appdata-specific values.",
            "source": str(audit_dir / "mcp-operator-smoke-latest.md"),
        },
    ]
    return {"behaviors": rows}


def mutation_playbooks(audit_dir: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    playbook_dir = audit_dir / "mutation-playbooks"
    if not playbook_dir.exists():
        return out
    for path in sorted(playbook_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = next((line.removeprefix("#").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
        out.append({"name": path.stem, "title": title, "source": str(path)})
    return out


def generate_corpus(*, audit_dir: Path, output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = read_json(audit_dir / "pdf-gap-coverage-matrix.json", [])
    api_methods = load_api_methods(audit_dir / "grpc-api-catalog.csv")
    endpoints = parse_http_catalog(audit_dir / "http-endpoints-catalog.md")

    payloads = {
        "api_methods.json": {
            "source": str(audit_dir / "grpc-api-catalog.csv"),
            "method_count": len(api_methods),
            "methods": api_methods,
        },
        "http_endpoints.json": {
            "source": str(audit_dir / "http-endpoints-catalog.md"),
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        },
        "task_recipes.json": {
            "source": str(audit_dir / "integration-playbooks.md"),
            "recipes": extract_task_recipes(audit_dir / "integration-playbooks.md"),
            "mutation_playbooks": mutation_playbooks(audit_dir),
        },
        "fixtures.json": {
            "source": str(audit_dir / "pdf-gap-coverage-matrix.json"),
            "coverage_counts": coverage_counts(matrix),
            "fixture_needed": fixture_needed_rows(matrix),
        },
        "safety_policies.json": safety_policies(),
        "known_behaviors.json": known_behaviors(matrix, audit_dir),
    }
    for name, payload in payloads.items():
        write_json(output_dir / name, payload)
    return CORPUS_FILES.copy()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "docs/api-audit/mcp-corpus")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = generate_corpus(audit_dir=args.audit_dir, output_dir=args.output_dir)
    for name in written:
        print(args.output_dir / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
