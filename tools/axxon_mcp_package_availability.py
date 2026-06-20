#!/usr/bin/env python3
"""InstallationPackageProvider tools for Axxon One MCP.

Check installer-package availability (CheckPackageAvailability) for a given OS and machine,
returning package metadata (id, product, version, size). DownloadInstallerPackage is exposed only
as a bounded streaming probe: installer bytes are counted, never persisted or returned. Direct
gRPC against `InstallationPackageProvider`.
"""

from __future__ import annotations

import time
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
    "download_installer_package_probe",
)

DEFAULT_INSTALLER_CHUNKS = 8
MAX_INSTALLER_CHUNKS = 64
DEFAULT_INSTALLER_BYTES = 4 * 1024 * 1024
MAX_INSTALLER_BYTES = 32 * 1024 * 1024
DEFAULT_INSTALLER_SECONDS = 10.0
MAX_INSTALLER_SECONDS = 60.0
DEFAULT_INSTALLER_CHUNK_KB = 64
MAX_INSTALLER_CHUNK_KB = 1024


def _cap_int(value: int | float | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _cap_float(value: int | float | None, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


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

    def download_installer_package_probe(
        self,
        package_id: str,
        chunk_size_kb: int = DEFAULT_INSTALLER_CHUNK_KB,
        start_from_chunk_index: int = 0,
        max_chunks: int | None = None,
        max_bytes: int | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Probe installer download availability with chunk/byte/time caps.

        The stream payload is consumed only long enough to count chunks and bytes. Raw installer
        data is never returned or written to disk.
        """
        if not package_id:
            return {"status": "error", "tool": "download_installer_package_probe", "message": "package_id is required."}
        stub, pb2 = self._stub_and_pb2()
        chunk_size = _cap_int(chunk_size_kb, default=DEFAULT_INSTALLER_CHUNK_KB, minimum=1, maximum=MAX_INSTALLER_CHUNK_KB)
        chunk_cap = _cap_int(max_chunks, default=DEFAULT_INSTALLER_CHUNKS, minimum=1, maximum=MAX_INSTALLER_CHUNKS)
        byte_cap = _cap_int(max_bytes, default=DEFAULT_INSTALLER_BYTES, minimum=1, maximum=MAX_INSTALLER_BYTES)
        timeout = _cap_float(timeout_s, default=DEFAULT_INSTALLER_SECONDS, minimum=1.0, maximum=MAX_INSTALLER_SECONDS)
        start_index = max(0, int(start_from_chunk_index or 0))
        request = pb2.DownloadInstallerPackageRequest(
            package_id=package_id,
            chunk_size_kb=chunk_size,
            start_from_chunk_index=start_index,
        )
        deadline = time.monotonic() + timeout
        chunks_seen = 0
        bytes_seen = 0
        last_index: int | None = None
        truncated = False
        stop_reason = "completed"
        for chunk in stub.DownloadInstallerPackage(request, timeout=timeout):
            chunks_seen += 1
            bytes_seen += len(getattr(chunk, "data", b""))
            last_index = int(getattr(chunk, "index", chunks_seen - 1))
            if chunks_seen >= chunk_cap:
                truncated, stop_reason = True, "chunk_cap"
                break
            if bytes_seen >= byte_cap:
                truncated, stop_reason = True, "byte_cap"
                break
            if time.monotonic() > deadline:
                truncated, stop_reason = True, "time_cap"
                break
        return {
            "status": "ok",
            "tool": "download_installer_package_probe",
            "package_id": package_id,
            "chunk_size_kb": chunk_size,
            "start_from_chunk_index": start_index,
            "chunks_seen": chunks_seen,
            "bytes_seen": bytes_seen,
            "total_size_bytes": None,
            "last_chunk_index": last_index,
            "truncated": truncated,
            "stop_reason": stop_reason,
        }
