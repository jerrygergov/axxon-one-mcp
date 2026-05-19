#!/usr/bin/env python3
"""Read-only detector and archive policy tools for the Axxon One MCP server.

Task 2 scaffolds connection and redaction only. Catalog, schema, detector
config, metadata, and archive policy behavior are added in later Phase 5E tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


DETECTOR_LIST_LIMIT_CAP = 200
METADATA_SAMPLE_TIMEOUT_DEFAULT = 5.0
METADATA_SAMPLE_TIMEOUT_CAP = 30.0
METADATA_SAMPLE_LIMIT_DEFAULT = 20
METADATA_SAMPLE_LIMIT_CAP = 200
SENSITIVE_PROPERTY_TOKENS = ("password", "token", "secret", "certificate", "private_key", "serial", "license")
DETECTOR_UNIT_TYPES = ("AVDetector", "AppDataDetector")
KNOWN_DETECTOR_KINDS = {
    "AVDetector": ("MotionDetection", "SceneDescription", "NeuroTracker"),
    "AppDataDetector": ("MoveInZone", "OneLineCrossing", "LongInZone", "LostObject", "AbandonedObject"),
}
PROPERTY_ID_FIELDS = ("id", "property_id", "propertyId", "path", "name")
PROPERTY_VALUE_FIELDS = ("string_list_value",)


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


def _sensitive_key(name: Any) -> bool:
    simplified = "".join(ch for ch in str(name).lower() if ch.isalnum())
    return any(token.replace("_", "") in simplified for token in SENSITIVE_PROPERTY_TOKENS)


def _sensitive_property_node(value: dict[Any, Any]) -> bool:
    return any(_sensitive_key(value.get(field, "")) for field in PROPERTY_ID_FIELDS)


def _property_value_field(name: Any) -> bool:
    return str(name).startswith("value_") or str(name) in PROPERTY_VALUE_FIELDS


def redact_sensitive_properties(value: Any) -> Any:
    if isinstance(value, dict):
        sensitive_node = _sensitive_property_node(value)
        return {
            key: "<redacted>"
            if _sensitive_key(key) or (sensitive_node and _property_value_field(key))
            else redact_sensitive_properties(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_properties(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_properties(item) for item in value)
    return value


@dataclass
class AxxonMcpDetectorArchive:
    """Read-only detector and archive policy tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def detector_archive_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
                "profile_name": profile,
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read-only",
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.detector_archive_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.detector_archive_connect_axxon_profile("env")
        return self.client
