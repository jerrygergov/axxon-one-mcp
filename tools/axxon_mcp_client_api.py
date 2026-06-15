#!/usr/bin/env python3
"""Client HTTP API preflight + operation catalog for the Axxon One MCP (Phase 5).

The Axxon One desktop Client exposes a local HTTP API (default port 8888) for operator-screen
control: switch layout, add/remove cameras on a display, set archive/search/immersion modes,
read the current layout's cameras, select a display. That API requires a reachable Client HTTP API
target, which is not present on every deployment.

This module is read-only / knowledge:
- client_api_connect_axxon_profile: lazy, env-only profile connect (read mode, secrets redacted)
- client_api_preflight: socket-probe the Client HTTP API port locally and on the configured host;
  report reachability and a fixture gap, performing no display mutation
- list_client_api_operations: catalog the Client HTTP API operations, each marked fixture-needed
  with its risk and the required fixture (a reachable Client HTTP API target)

No display-control operation is ever executed here. Results are sanitized dicts; no password,
token, cookie, or CA material is returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import socket
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

DEFAULT_CLIENT_HTTP_PORT = 8888
SOCKET_TIMEOUT_S = 2.0

CLIENT_API_TOOL_NAMES = (
    "client_api_connect_axxon_profile",
    "client_api_preflight",
    "list_client_api_operations",
)

# Client HTTP API operations (operator-screen control). All require a reachable Client HTTP API
# target on the configured port, so every entry stays fixture-needed until that fixture exists.
_OPERATIONS = (
    {"operation": "SwitchLayout", "risk": "changes operator display state", "required_fixture": "reachable Client HTTP API target on the configured port; capture/restore current layout"},
    {"operation": "AddCameraToDisplay", "risk": "changes operator display composition", "required_fixture": "isolated display target plus a remove/restore step"},
    {"operation": "RemoveCameraFromDisplay", "risk": "changes operator display composition", "required_fixture": "restore-original-display step"},
    {"operation": "GetCurrentLayoutCameras", "risk": "read of operator screen state", "required_fixture": "reachable Client HTTP API target on the configured port"},
    {"operation": "SelectDisplay", "risk": "changes which display subsequent ops target", "required_fixture": "multi-display client fixture"},
    {"operation": "SetArchiveMode", "risk": "changes playback/live mode in the client UI", "required_fixture": "capture/restore previous mode"},
    {"operation": "SetSearchMode", "risk": "changes client UI search mode", "required_fixture": "capture/restore previous mode"},
    {"operation": "SetImmersionMode", "risk": "changes client UI immersion state", "required_fixture": "capture/restore previous mode"},
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def default_socket_probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class AxxonMcpClientApi:
    """Client HTTP API preflight + fixture-needed operation catalog (Phase 5). Read-only, no mutations."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    socket_probe: Callable[[str, int, float], bool] = default_socket_probe
    client: Any | None = None
    profile_name: str | None = None

    def client_api_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.client_api_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.client_api_connect_axxon_profile("env")
        return self.client

    def client_api_preflight(self, client_http_port: int = DEFAULT_CLIENT_HTTP_PORT) -> dict[str, Any]:
        """Socket-probe the Client HTTP API port locally and on the configured host (read-only)."""
        config = self.ensure_client().config
        host = str(getattr(config, "host", "")) or "localhost"
        port = int(client_http_port)
        targets = [
            {"host": "127.0.0.1", "port": port, "purpose": "local Axxon Client HTTP API"},
            {"host": host, "port": port, "purpose": "remote host Client HTTP API"},
        ]
        checks = []
        for target in targets:
            reachable = self.socket_probe(target["host"], target["port"], SOCKET_TIMEOUT_S)
            checks.append({**target, "reachable": bool(reachable)})
        reachable_count = sum(1 for c in checks if c["reachable"])
        return {
            "status": "ok",
            "tool": "client_api_preflight",
            "client_http_port": port,
            "reachable_count": reachable_count,
            "checks": checks,
            "fixture_gap": "" if reachable_count else "no Axxon Client HTTP API target reachable on the configured port",
        }

    def list_client_api_operations(self) -> dict[str, Any]:
        """Catalog the Client HTTP API operations, each marked fixture-needed (knowledge only, no wire)."""
        return {
            "status": "ok",
            "tool": "list_client_api_operations",
            "operations": [{**op, "status": "fixture-needed"} for op in _OPERATIONS],
            "note": "Run client_api_preflight to check whether a Client HTTP API target is reachable before requesting these.",
        }
