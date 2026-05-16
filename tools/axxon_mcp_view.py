#!/usr/bin/env python3
"""Read-only live and archive viewing tools for the Axxon One MCP server.

URLs only — this module never proxies media bytes. Callers fetch URLs
directly with the Bearer token issued by AxxonApiClient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from axxon_api_client import AxxonApiClient, AxxonClientConfig


DEFAULT_MAX_BYTES = 1_048_576
DEFAULT_DURATION_S = 10
DEFAULT_FPS = 5
DEFAULT_SNAPSHOT_WIDTH = 640
SNAPSHOT_BATCH_LIMIT = 8
ARCHIVE_MJPEG_BYTE_CAP = 4_194_304
ARCHIVE_FRAME_THRESHOLD_MS = 60_000


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def public_config_summary(config: Any) -> dict[str, Any]:
    return {
        "host": getattr(config, "host", ""),
        "grpc_port": getattr(config, "grpc_port", None),
        "http_port": getattr(config, "http_port", None),
        "http_url": getattr(config, "http_url", ""),
        "username": getattr(config, "username", ""),
        "password_present": bool(getattr(config, "password", "")),
        "tls_cn": getattr(config, "tls_cn", ""),
        "ca": str(getattr(config, "ca", "")),
        "timeout": getattr(config, "timeout", None),
    }


@dataclass
class AxxonMcpView:
    """URL-only live and archive viewing tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = field(default=None, repr=False)

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        self._inventory = None
        return {
            "connected": True,
            "profile": public_config_summary(config),
        }

    def _ensure_inventory(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        if self._inventory is None:
            self._inventory = self.client.load_inventory()
        return self._inventory
