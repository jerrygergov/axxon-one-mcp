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


def normalize_alarm(raw: dict[str, Any]) -> dict[str, Any]:
    """Map an Axxon active-alarm dict to a stable MCP-side schema.

    Source fields verified against ``GetActiveAlerts`` responses on the demo stand:
    ``guid``, ``timestamp``, ``node_info.name``, ``camera.access_point``,
    ``camera.friendly_name``, ``archive.access_point``, ``required_comment``,
    ``severity``.
    """
    camera = raw.get("camera") or {}
    archive = raw.get("archive") or {}
    node = raw.get("node_info") or {}
    return {
        "alert_id": raw.get("guid") or raw.get("alert_id") or "",
        "severity": raw.get("severity"),
        "camera_access_point": camera.get("access_point"),
        "camera_friendly_name": camera.get("friendly_name"),
        "archive_access_point": archive.get("access_point"),
        "node_name": node.get("name"),
        "timestamp": raw.get("timestamp"),
        "required_comment": raw.get("required_comment"),
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

    def _camera_index(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            cam.get("access_point", ""): cam
            for cam in inventory.get("cameras", [])
            if cam.get("access_point")
        }

    def _host(self) -> str:
        return f"hosts/{self.client.config.tls_cn}"

    def list_active_alerts(
        self,
        camera_access_point: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if camera_access_point is not None:
            inv = self._ensure_inventory()
            if camera_access_point not in self._camera_index(inv):
                return {
                    "status": "gap",
                    "tool": "list_active_alerts",
                    "message": f"Camera not in inventory: {camera_access_point}",
                }
            resp = self.client.get_active_alerts(camera_access_point)
            body = resp.get("body") if isinstance(resp, dict) else {}
            raw_items = (body or {}).get("alerts") or []
            items = [normalize_alarm(a) for a in raw_items][:applied_limit]
            return {
                "status": "ok",
                "tool": "list_active_alerts",
                "count": len(items),
                "applied_limit": applied_limit,
                "items": items,
            }
        # Node-wide
        if self.client is None:
            self.connect_axxon_profile("env")
        resp = self.client.batch_get_active_alerts([self._host()])
        body = resp.get("body") if isinstance(resp, dict) else {}
        pages = (body or {}).get("event_stream_items") or []
        flat: list[dict[str, Any]] = []
        unreachable_per_page: list[list[str]] = []
        for page in pages:
            flat.extend(page.get("alerts") or [])
            unreachable_per_page.append(list(page.get("unreachable_nodes") or []))
        # Only surface "unreachable" when every page agrees.
        if unreachable_per_page and all(u for u in unreachable_per_page):
            unreachable_intersection = sorted(set.intersection(*[set(u) for u in unreachable_per_page]))
        else:
            unreachable_intersection = []
        items = [normalize_alarm(a) for a in flat][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_active_alerts",
            "count": len(items),
            "applied_limit": applied_limit,
            "items": items,
            "unreachable_nodes": unreachable_intersection,
        }

    def get_active_alert(self, camera_access_point: str, alert_id: str) -> dict[str, Any]:
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            return {
                "status": "gap",
                "tool": "get_active_alert",
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        resp = self.client.get_active_alerts(camera_access_point)
        body = resp.get("body") if isinstance(resp, dict) else {}
        for raw in (body or {}).get("alerts") or []:
            if (raw.get("guid") or raw.get("alert_id")) == alert_id:
                return {"status": "ok", "tool": "get_active_alert", "item": normalize_alarm(raw)}
        return {
            "status": "gap",
            "tool": "get_active_alert",
            "message": f"Alert id not active on this camera: {alert_id}",
        }

    def filter_active_alerts(
        self,
        severity_min: int | None = None,
        camera: str | None = None,
        state: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        # `state` is reserved for when AlertState becomes available on the stream.
        if state not in ("all", "active", "reviewing", "completed", "cancelled", "escalated"):
            return {
                "status": "gap",
                "tool": "filter_active_alerts",
                "message": f"Unknown state filter: {state}",
            }
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        resp = self.client.batch_filter_active_alerts([self._host()], filter={})
        body = resp.get("body") if isinstance(resp, dict) else {}
        pages = (body or {}).get("event_stream_items") or []
        flat: list[dict[str, Any]] = []
        for page in pages:
            flat.extend(page.get("alerts") or [])
        normalized = [normalize_alarm(a) for a in flat]
        kept: list[dict[str, Any]] = []
        for item in normalized:
            if severity_min is not None:
                sev = item.get("severity")
                if sev is None or sev < severity_min:
                    continue
            if camera is not None and item.get("camera_access_point") != camera:
                continue
            kept.append(item)
            if len(kept) >= applied_limit:
                break
        return {
            "status": "ok",
            "tool": "filter_active_alerts",
            "count": len(kept),
            "applied_limit": applied_limit,
            "applied_filters": {"severity_min": severity_min, "camera": camera, "state": state},
            "items": kept,
        }
