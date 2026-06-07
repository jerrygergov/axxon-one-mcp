#!/usr/bin/env python3
"""ACFA action + VMDA cleanup control tools for Axxon One MCP (Phase 31).

Drive access-control units (AcfaService.PerformAction) and wipe a camera's VMDA
analytics (VMDAService.Cleanup). Both writes are approval-gated
(`AXXON_CONTROL_APPROVE=1`) plus a per-call confirmation token, mirroring the
audit-injector idiom. `list_unit_actions` is a read helper to discover the action
ids a unit accepts. Direct gRPC against `AcfaService` and `VMDAService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

CONTROL_APPROVE_ENV = "AXXON_CONTROL_APPROVE"
CONTROL_CONFIRMATION = "CONFIRM-control-action"
ACFA_PROTO = "axxonsoft/bl/acfa/AcfaService.proto"
ACFA_PB2 = "axxonsoft.bl.acfa.AcfaService_pb2"
VMDA_PROTO = "axxonsoft/bl/vmda/VMDA.proto"
VMDA_PB2 = "axxonsoft.bl.vmda.VMDA_pb2"

CONTROL_TOOL_NAMES = (
    "control_connect_axxon_profile",
    "list_unit_actions",
    "perform_unit_action",
    "vmda_cleanup",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(CONTROL_APPROVE_ENV) == "1"


def _vmda_database_ap(inventory: dict[str, Any]) -> str:
    def walk(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [s for v in value.values() for s in walk(v)]
        if isinstance(value, list):
            return [s for v in value for s in walk(v)]
        return [str(value)]

    for text in sorted(walk(inventory)):
        if "VMDA_DB" in text and text.endswith("/Database"):
            return text
    return ""


@dataclass
class AxxonMcpAcfaVmdaControl:
    """Phase 31 control tools (ACFA PerformAction + VMDA Cleanup, gated)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def control_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+write",
            "approval_env": CONTROL_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.control_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.control_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self, proto: str, service: str, pb2_name: str) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(proto, service), client.import_module(pb2_name)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {CONTROL_APPROVE_ENV}=1 to enable control actions.", "approval_env": CONTROL_APPROVE_ENV}
        if confirmation != CONTROL_CONFIRMATION:
            return {"status": "gap", "message": f"control actions require confirmation={CONTROL_CONFIRMATION}"}
        return None

    def list_unit_actions(self, uids: list[str] | None = None) -> dict[str, Any]:
        ids = [u for u in (uids or []) if u]
        if not ids:
            return {"status": "error", "tool": "list_unit_actions", "message": "provide at least one unit uid"}
        stub, pb2 = self._stub_and_pb2(ACFA_PROTO, "AcfaService", ACFA_PB2)
        request = pb2.ListUnitsActionsRequest(items=[pb2.ListUnitsActionsRequest.Unit(uid=u) for u in ids], portion_size=200)
        units: list[dict[str, Any]] = []
        for response in stub.ListUnitsActions(request, timeout=self.ensure_client().config.timeout):
            for ua in response.items:
                units.append({
                    "uid": ua.uid,
                    "actions": [{"id": a.id, "name": a.name, "input": [{"id": p.id, "type": p.type} for p in a.input]} for a in ua.actions],
                })
            if not response.more_data:
                break
        return {"status": "ok", "tool": "list_unit_actions", "count": len(units), "units": units}

    def perform_unit_action(
        self,
        uid: str = "",
        action_id: str = "",
        properties: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "perform_unit_action", **gated}
        if not uid or not action_id:
            return {"status": "error", "tool": "perform_unit_action", "message": "uid and action_id are required"}
        stub, pb2 = self._stub_and_pb2(ACFA_PROTO, "AcfaService", ACFA_PB2)
        request = pb2.PerformActionRequest(uid=uid, id=action_id)
        for prop in properties or []:
            request.properties.append(pb2.PropertyDescriptor(id=prop.get("id", ""), value_string=str(prop.get("value", ""))))
        response = stub.PerformAction(request, timeout=self.ensure_client().config.timeout)
        outputs = [{"id": p.id, "value": p.value_string} for p in response.properties]
        status = "action-error" if response.error_message else "applied"
        return {"status": status, "tool": "perform_unit_action", "uid": uid, "action_id": action_id, "error_message": response.error_message, "outputs": outputs}

    def vmda_cleanup(
        self,
        camera_id: str = "",
        schema_id: str = "vmda_schema",
        database: str = "",
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "vmda_cleanup", **gated}
        if not camera_id:
            return {"status": "error", "tool": "vmda_cleanup", "message": "camera_id is required"}
        client = self.ensure_client()
        stub, pb2 = self._stub_and_pb2(VMDA_PROTO, "VMDAService", VMDA_PB2)
        db = database or _vmda_database_ap(client.load_inventory() if hasattr(client, "load_inventory") else {})
        if not db:
            return {"status": "gap", "tool": "vmda_cleanup", "message": "no VMDA database (*/VMDA_DB.N/Database) found; pass database explicitly"}
        relative_camera = camera_id.split("/", 2)[-1] if camera_id.startswith("hosts/") else camera_id
        cs = pb2.CameraAndSchemaIDs(camera_ID=relative_camera, schema_ID=schema_id)
        response = stub.Cleanup(pb2.CleanupRequest(access_point=db, cs_IDs=cs), timeout=client.config.timeout)
        return {"status": "applied", "tool": "vmda_cleanup", "camera_id": relative_camera, "schema_id": schema_id, "database": db, "result": bool(response.result)}
