#!/usr/bin/env python3
"""InstallationPackageProvider read tool for Axxon One MCP (Phase A).

Check installer-package availability (CheckPackageAvailability) for a given OS and machine,
returning package metadata (id, product, version, size). A single unary `read` RPC, no approval
gate. The companion DownloadInstallerPackage RPC is intentionally not exposed here. Direct gRPC
against `InstallationPackageProvider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

PACKAGE_AVAILABILITY_PROTO = "axxonsoft/bl/package/InstallationPackageProvider.proto"
PACKAGE_AVAILABILITY_PB2 = "axxonsoft.bl.package.InstallationPackageProvider_pb2"

PACKAGE_AVAILABILITY_TOOL_NAMES = (
    "package_availability_connect_axxon_profile",
    "check_package_availability",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpPackageAvailability:
    """Phase A InstallationPackageProvider read tool (installer-package availability check)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def package_availability_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.package_availability_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.package_availability_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(PACKAGE_AVAILABILITY_PROTO, "InstallationPackageProvider"), client.import_module(PACKAGE_AVAILABILITY_PB2)

    def check_package_availability(self, system: str = "Linux", machine: str = "") -> dict[str, Any]:
        """Check installer-package availability for an OS ("Windows"|"Linux") and optional machine.

        Args:
            system (str, optional): Target OS name, "Windows" or "Linux".
            machine (str, optional): Target machine identifier; empty for the current node.

        Returns:
            (dict): {"status": "ok", "tool": "check_package_availability", "package_id", "product_name", "package_version", "package_size_bytes"}.
        """
        stub, pb2 = self._stub_and_pb2()
        request_type = pb2.CheckPackageAvailabilityRequest
        try:
            system_value = request_type.OperationSystem.Value(system)
        except (KeyError, ValueError):
            return {"status": "gap", "tool": "check_package_availability", "message": f"Unknown OS: {system!r}. Use 'Windows' or 'Linux'."}
        request = request_type(system=system_value, machine=machine)
        response = stub.CheckPackageAvailability(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "check_package_availability",
            "package_id": response.package_id,
            "product_name": response.product_name,
            "package_version": response.package_version,
            "package_size_bytes": response.package_size_bytes,
        }
