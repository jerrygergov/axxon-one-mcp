#!/usr/bin/env python3
"""Alarm-lifecycle MCP tools for the Axxon One MCP server.

Two dataclasses live here:

* ``AxxonMcpAlarms`` — read-only tools and a bounded alarm subscription.
* ``AxxonAlarmMutator`` — alarm lifecycle mutations, gated by an environment
  flag (default ``AXXON_ALARMS_APPROVE``) and per-call confirmation tokens.

Both reuse ``AxxonApiClient`` for transport. URLs are never returned; the
mutator never persists to disk. The module mirrors the dataclass-with-factories
shape used by ``axxon_mcp_view.py``.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


LIST_LIMIT_CAP = 200
HISTORY_HOURS_CAP = 24
SUBSCRIBE_DURATION_CAP_S = 30
SUBSCRIBE_LIMIT_CAP = 100

ALARM_EVENT_TYPES = ("ET_Alert", "ET_AlertState")

SEVERITY_CHOICES = ("confirmed_alarm", "suspicious_situation", "false_alarm")
PRIORITY_CHOICES = ("AP_MINIMUM", "AP_LOW", "AP_MEDIUM", "AP_HIGH")

CONFIRMATION_TOKENS = {
    "raise_alert": "CONFIRM-raise-alert",
    "alarm_begin_review": "CONFIRM-alarm-begin",
    "alarm_continue_review": "CONFIRM-alarm-continue",
    "alarm_cancel_review": "CONFIRM-alarm-cancel",
    "alarm_complete_review": "CONFIRM-alarm-complete",
    "alarm_escalate": "CONFIRM-alarm-escalate",
}


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
class AxxonMcpAlarms:
    """Read-only alarm tools + bounded alarm subscription."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = None

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
        self._inventory = None
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read-only",
        }

    def _ensure_inventory(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        if self._inventory is None:
            self._inventory = self.client.load_inventory()
        return self._inventory
