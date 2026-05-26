#!/usr/bin/env python3
"""Read-only security, health, notifier, and schedule tools for Axxon One MCP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


ADMIN_MODE = "read-only"

ADMIN_TOOL_NAMES = (
    "admin_connect_axxon_profile",
    "security_inventory",
    "security_policy_summary",
    "role_permissions",
    "current_user_security",
    "license_status",
    "time_status",
    "system_health",
    "domain_event_subscribe",
    "node_event_subscribe",
    "schedule_descriptor_get",
)

_SENSITIVE_KEY_TOKENS = (
    "password",
    "passwd",
    "pwd",
    "authorization",
    "bearer",
    "token",
    "sessionid",
    "tfa",
    "otp",
    "secret",
    "license",
    "serial",
    "fingerprint",
    "hardware",
    "machineid",
    "hostid",
    "hwid",
)

_BEARER_TEXT_RE = re.compile(r"\bBearer\s+[^,\s;]+", re.IGNORECASE)
_SECRET_TEXT_KEY = (
    r"password|passwd|pwd|authorization|bearer|token|session[_-]?token|tfa[_-]?(secret|code|key)?|"
    r"otp|secret|license[_-]?key|serial[_-]?number|fingerprint|hardware[_-]?fingerprint|"
    r"machine[_-]?id|host[_-]?id|hwid"
)
_QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?P<key_quote>['\"]?)(?P<key>\b(?:{_SECRET_TEXT_KEY})\b)(?P=key_quote)"
    r"(?P<sep>\s*[:=]\s*)(?P<value_quote>['\"])(?P<value>.*?)(?P=value_quote)",
    re.IGNORECASE,
)
_UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?P<key_quote>['\"]?)(?P<key>\b(?:{_SECRET_TEXT_KEY})\b)(?P=key_quote)"
    r"(?P<sep>\s*[:=]\s*)[^,\s;}\]]+",
    re.IGNORECASE,
)


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


def _normalized_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def redact_admin_text(value: Any, limit: int = 240) -> str:
    text = str(value)
    text = _BEARER_TEXT_RE.sub("Bearer <redacted>", text)
    text = _QUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
        f"{match.group('sep')}<redacted>",
        text,
    )
    text = _UNQUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
        f"{match.group('sep')}<redacted>",
        text,
    )
    return text[:limit]


def redact_admin_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            out[key] = "<redacted>" if _is_sensitive_key(key) and item else redact_admin_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_admin_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_admin_secrets(item) for item in value)
    if isinstance(value, str):
        return redact_admin_text(value)
    return value


@dataclass
class AxxonMcpAdmin:
    """Read-only Phase 5F-A admin tool scaffold."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def admin_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "mode": ADMIN_MODE,
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.admin_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.admin_connect_axxon_profile("env")
        return self.client
