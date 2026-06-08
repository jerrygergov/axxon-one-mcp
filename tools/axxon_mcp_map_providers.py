#!/usr/bin/env python3
"""MapService map-provider tools for Axxon One MCP (Phase 34).

Configure map providers (ConfigureMapProviders) and read one by id (GetMapProvider).
The configure write is approval-gated (`AXXON_MAP_APPROVE=1`) plus a per-call
confirmation token, mirroring the audit-injector idiom. MapProvider messages come
from MapProvider_pb2; the stub is MapService. Direct gRPC.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

MAP_APPROVE_ENV = "AXXON_MAP_APPROVE"
MAP_CONFIRMATION = "CONFIRM-map-providers"
MAPS_PROTO = "axxonsoft/bl/maps/MapService.proto"
MAPS_PB2 = "axxonsoft.bl.maps.MapService_pb2"
PROVIDER_PB2 = "axxonsoft.bl.maps.MapProvider_pb2"

MAP_PROVIDERS_TOOL_NAMES = (
    "map_providers_connect_axxon_profile",
    "configure_map_providers",
    "get_map_provider",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(MAP_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpMapProviders:
    """Phase 34 MapService provider tools (gated configure + read)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def map_providers_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": MAP_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.map_providers_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.map_providers_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(MAPS_PROTO, "MapService"), client.import_module(MAPS_PB2), client.import_module(PROVIDER_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {MAP_APPROVE_ENV}=1 to enable map-provider writes.", "approval_env": MAP_APPROVE_ENV}
        if confirmation != MAP_CONFIRMATION:
            return {"status": "gap", "message": f"map-provider writes require confirmation={MAP_CONFIRMATION}"}
        return None

    def configure_map_providers(
        self,
        changed: list[dict[str, str]] | None = None,
        removed: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "configure_map_providers", **gated}
        changed = changed or []
        removed = [r.upper() for r in (removed or []) if r]
        if not changed and not removed:
            return {"status": "error", "tool": "configure_map_providers", "message": "provide at least one of changed, removed"}
        from google.protobuf.wrappers_pb2 import StringValue

        stub, pb2, provider_pb2 = self._stub_and_pb2()
        request = pb2.ConfigureMapProvidersRequest(removed=removed)
        # The server stores provider ids uppercase and GetMapProvider/remove are case-sensitive.
        for spec in changed:
            spec["id"] = spec.get("id", "").upper()
            provider = provider_pb2.MapProvider(id=spec["id"], name=spec.get("name", ""), etag=spec.get("etag", ""))
            if spec.get("api_key"):
                provider.api_key.CopyFrom(StringValue(value=spec["api_key"]))
            if spec.get("copyright"):
                provider.copyright.CopyFrom(StringValue(value=spec["copyright"]))
            request.changed.append(provider)
        response = stub.ConfigureMapProviders(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "tool": "configure_map_providers",
            "changed_ids": [s.get("id", "") for s in changed],
            "removed_ids": removed,
            "etags": dict(response.etags),
        }

    def get_map_provider(self, provider_id: str = "") -> dict[str, Any]:
        if not provider_id:
            return {"status": "error", "tool": "get_map_provider", "message": "provider_id is required"}
        stub, pb2, _ = self._stub_and_pb2()
        response = stub.GetMapProvider(pb2.GetMapProviderRequest(id=provider_id.upper()), timeout=self.ensure_client().config.timeout)
        p = response.map_provider
        return {
            "status": "ok",
            "tool": "get_map_provider",
            "provider": {"id": p.id, "name": p.name, "etag": p.etag, "map_types_count": len(p.map_types)},
        }
