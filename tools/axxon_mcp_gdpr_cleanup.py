#!/usr/bin/env python3
"""GDPR user-data cleanup tools for Axxon One MCP (Phase 30).

Remove a user's stored layouts and maps via LayoutManager.UserDataCleanup and
MapService.UserDataCleanup. Both writes are approval-gated
(`AXXON_GDPR_APPROVE=1`) plus a per-call confirmation token, mirroring the
audit-injector idiom. Each request takes a list of user ids; a user id that owns
nothing is a no-op on the wire. Direct gRPC against `LayoutManager` and
`MapService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

GDPR_APPROVE_ENV = "AXXON_GDPR_APPROVE"
GDPR_CONFIRMATION = "CONFIRM-gdpr-cleanup"
LAYOUT_PROTO = "axxonsoft/bl/layout/LayoutManager.proto"
LAYOUT_PB2 = "axxonsoft.bl.layout.LayoutManager_pb2"
MAPS_PROTO = "axxonsoft/bl/maps/MapService.proto"
MAPS_PB2 = "axxonsoft.bl.maps.MapService_pb2"

GDPR_CLEANUP_TOOL_NAMES = (
    "gdpr_cleanup_connect_axxon_profile",
    "layout_user_data_cleanup",
    "map_user_data_cleanup",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(GDPR_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpGdprCleanup:
    """Phase 30 GDPR cleanup tools (gated layout/map user-data removal)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def gdpr_cleanup_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": GDPR_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.gdpr_cleanup_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.gdpr_cleanup_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self, proto: str, service: str, pb2_name: str) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(proto, service), client.import_module(pb2_name)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {GDPR_APPROVE_ENV}=1 to enable GDPR cleanup writes.", "approval_env": GDPR_APPROVE_ENV}
        if confirmation != GDPR_CONFIRMATION:
            return {"status": "gap", "message": f"GDPR cleanup requires confirmation={GDPR_CONFIRMATION}"}
        return None

    def _cleanup(self, *, tool: str, proto: str, service: str, pb2_name: str, user_ids: list[str], confirmation: str) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": tool, **gated}
        ids = [uid for uid in (user_ids or []) if uid]
        if not ids:
            return {"status": "error", "tool": tool, "message": "provide at least one user id"}
        stub, pb2 = self._stub_and_pb2(proto, service, pb2_name)
        stub.UserDataCleanup(pb2.UserDataCleanupRequest(user_ids=ids), timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": tool, "user_ids": ids}

    def layout_user_data_cleanup(self, user_ids: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        return self._cleanup(tool="layout_user_data_cleanup", proto=LAYOUT_PROTO, service="LayoutManager", pb2_name=LAYOUT_PB2, user_ids=user_ids or [], confirmation=confirmation)

    def map_user_data_cleanup(self, user_ids: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        return self._cleanup(tool="map_user_data_cleanup", proto=MAPS_PROTO, service="MapService", pb2_name=MAPS_PB2, user_ids=user_ids or [], confirmation=confirmation)
