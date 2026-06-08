#!/usr/bin/env python3
"""AuditEventInjector tools for Axxon One MCP (Phase 10).

Write-only audit-trail injection for compliance integrations. The service cannot
un-inject a journal record, so injection is gated behind an explicit approval env
(`AXXON_AUDIT_INJECT_APPROVE=1`) plus a per-call confirmation token; there is no
rollback. Direct gRPC against `AuditEventInjector`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

AUDIT_INJECT_APPROVE_ENV = "AXXON_AUDIT_INJECT_APPROVE"
AUDIT_INJECT_CONFIRMATION = "CONFIRM-audit-inject"
AUDIT_PROTO = "axxonsoft/bl/audit/Audit.proto"
AUDIT_PB2 = "axxonsoft.bl.audit.Audit_pb2"

# kind -> (gRPC method, required request fields). InjectMMExportEvent is omitted:
# it needs a live export job and errors on a bare stand.
AUDIT_KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "camera_viewing": ("InjectCameraViewingEvent", ("camera_ap",)),
    "ptz_control": ("InjectPtzControlEvent", ("camera_ap",)),
    "archive_viewing": ("InjectArchiveViewingEvent", ("camera_ap", "archive_ap")),
    "journal_export": ("InjectNgpJournalExportEvent", ("start", "end")),
    "client_app_option": ("InjectClientAppOptionEvent", ("group", "setting", "setting_value")),
    "ldap_setup": ("InjectLdapSetupEvent", ("ldap", "group", "setting", "setting_value")),
}

AUDIT_TOOL_NAMES = (
    "audit_connect_axxon_profile",
    "list_audit_event_kinds",
    "audit_inject",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(AUDIT_INJECT_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpAudit:
    """Phase 10 AuditEventInjector tools (write-only, approval-gated)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def audit_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "write-only",
            "approval_env": AUDIT_INJECT_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.audit_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.audit_connect_axxon_profile("env")
        return self.client

    def list_audit_event_kinds(self) -> dict[str, Any]:
        kinds = [
            {"kind": kind, "method": method, "required": list(fields)}
            for kind, (method, fields) in AUDIT_KINDS.items()
        ]
        return {"status": "ok", "count": len(kinds), "kinds": kinds}

    def audit_inject(self, kind: str, params: dict[str, Any] | None = None, confirmation: str = "") -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "disabled",
                "message": f"Set {AUDIT_INJECT_APPROVE_ENV}=1 to enable audit injection.",
                "approval_env": AUDIT_INJECT_APPROVE_ENV,
            }
        entry = AUDIT_KINDS.get(kind)
        if entry is None:
            return {"status": "error", "message": f"unknown audit event kind: {kind}", "kinds": list(AUDIT_KINDS)}
        if confirmation != AUDIT_INJECT_CONFIRMATION:
            return {"status": "gap", "message": f"audit_inject requires confirmation={AUDIT_INJECT_CONFIRMATION}"}
        method_name, required = entry
        params = params or {}
        missing = [field for field in required if not str(params.get(field) or "").strip()]
        if missing:
            return {"status": "error", "message": f"missing required param(s): {', '.join(missing)}", "required": list(required)}

        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(AUDIT_PROTO, "AuditEventInjector")
        pb2 = client.import_module(AUDIT_PB2)
        request = getattr(pb2, method_name + "Request")(**{field: params[field] for field in required})
        getattr(stub, method_name)(request, timeout=client.config.timeout)
        return {"status": "injected", "kind": kind, "method": method_name, "fields": list(required)}
