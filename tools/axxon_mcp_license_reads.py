#!/usr/bin/env python3
"""LicenseService read tools for Axxon One MCP (Phase 42).

Read the current license key (LicenseKey, metadata-only) and license restrictions
(Restrictions). Both are reads, so there is no approval gate. The license key value is never
returned; only key_present and key_length are reported. Direct gRPC against `LicenseService`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

LICENSE_PROTO = "axxonsoft/bl/license/LicenseService.proto"
LICENSE_PB2 = "axxonsoft.bl.license.LicenseService_pb2"

LICENSE_READS_TOOL_NAMES = (
    "license_reads_connect_axxon_profile",
    "get_license_key",
    "get_restrictions",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpLicenseReads:
    """Phase 42 LicenseService read tools (license key metadata + restrictions)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def license_reads_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read",
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.license_reads_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.license_reads_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(LICENSE_PROTO, "LicenseService"), client.import_module(LICENSE_PB2)

    def get_license_key(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        response = stub.LicenseKey(pb2.LicenseKeyRequest(), timeout=self.ensure_client().config.timeout)
        key = response.license_key
        return {"status": "ok", "tool": "get_license_key", "key_present": bool(key), "key_length": len(key)}

    def get_restrictions(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        response = stub.Restrictions(pb2.RestrictionsRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "get_restrictions",
            "restrictions_present": response.HasField("restrictions"),
            "available_present": response.HasField("available_restrictions"),
        }
