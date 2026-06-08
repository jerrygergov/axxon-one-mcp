#!/usr/bin/env python3
"""ArchiveService volume tools for Axxon One MCP (Phase 37).

Read archive volume states (GetVolumesState) and resize a storage volume
(ArchiveService.Resize). The resize write is approval-gated
(`AXXON_ARCHIVE_VOLUME_APPROVE=1`) plus a per-call confirmation token, mirroring the
config-change idiom. Direct gRPC against `ArchiveService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

ARCHIVE_VOLUME_APPROVE_ENV = "AXXON_ARCHIVE_VOLUME_APPROVE"
ARCHIVE_VOLUME_CONFIRMATION = "CONFIRM-archive-resize"
ARCHIVE_PROTO = "axxonsoft/bl/archive/ArchiveSupport.proto"
ARCHIVE_PB2 = "axxonsoft.bl.archive.ArchiveSupport_pb2"

ARCHIVE_VOLUME_TOOL_NAMES = (
    "archive_volume_connect_axxon_profile",
    "list_volume_states",
    "resize_volume",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(ARCHIVE_VOLUME_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpArchiveVolume:
    """Phase 37 ArchiveService volume tools (read states + gated reversible resize)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def archive_volume_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": ARCHIVE_VOLUME_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.archive_volume_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.archive_volume_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(ARCHIVE_PROTO, "ArchiveService"), client.import_module(ARCHIVE_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {ARCHIVE_VOLUME_APPROVE_ENV}=1 to enable volume resize.", "approval_env": ARCHIVE_VOLUME_APPROVE_ENV}
        if confirmation != ARCHIVE_VOLUME_CONFIRMATION:
            return {"status": "gap", "message": f"volume resize requires confirmation={ARCHIVE_VOLUME_CONFIRMATION}"}
        return None

    def list_volume_states(self, access_point: str = "") -> dict[str, Any]:
        if not access_point:
            return {"status": "error", "tool": "list_volume_states", "message": "provide a storage access_point"}
        stub, pb2 = self._stub_and_pb2()
        response = stub.GetVolumesState(pb2.GetVolumesStateRequest(access_point=access_point), timeout=self.ensure_client().config.timeout)
        volumes = [
            {
                "volume_id": vid,
                "state": int(state.state),
                "used_bytes": int(state.used_bytes),
                "capacity_bytes": int(state.capacity_bytes),
            }
            for vid, state in response.volumes_state.items()
        ]
        return {"status": "ok", "tool": "list_volume_states", "volume_count": len(volumes), "volumes": volumes}

    def resize_volume(self, access_point: str = "", volume_id: str = "", new_size: int = 0, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "resize_volume", **gated}
        if not access_point or not volume_id or int(new_size) <= 0:
            return {"status": "error", "tool": "resize_volume", "message": "provide access_point, volume_id and a positive new_size"}
        stub, pb2 = self._stub_and_pb2()
        response = stub.Resize(pb2.ResizeRequest(access_point=access_point, volume_id=volume_id, new_size=int(new_size)), timeout=self.ensure_client().config.timeout)
        code = int(response.status_code)
        return {"status": "applied", "tool": "resize_volume", "status_code": code, "status_name": pb2.ResizeResponse.EStatusCode.Name(code)}
