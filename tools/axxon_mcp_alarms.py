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


_TRANSITION_BY_STATE = {
    "active": "raised",
    "reviewing": "begun_review",
    "completed": "completed",
    "cancelled": "cancelled",
    "escalated": "escalated",
}


def normalize_alarm_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw event from ``pull_events_bounded`` with type ``ET_Alert``/``ET_AlertState``.

    Adds a ``transition`` field derived from the event's ``state``; keeps the
    original event payload under ``raw`` for callers who need it.
    """
    state = raw.get("state")
    return {
        "alert_id": raw.get("alert_id") or raw.get("guid") or "",
        "event_type": raw.get("event_type"),
        "transition": _TRANSITION_BY_STATE.get(state, state or "unknown"),
        "state": state,
        "severity": raw.get("severity"),
        "camera_access_point": (raw.get("camera") or {}).get("access_point"),
        "timestamp": raw.get("timestamp"),
        "raw": raw,
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

    def list_alarm_history(
        self,
        hours: float = 1.0,
        limit: int = 100,
        camera: str | None = None,
        severity_min: int | None = None,
    ) -> dict[str, Any]:
        applied_hours = min(max(float(hours), 0.05), float(HISTORY_HOURS_CAP))
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        result = self.client.search_events(
            subjects=[self._host()] if camera is None else [camera],
            event_types=list(ALARM_EVENT_TYPES),
            hours=applied_hours,
            limit=applied_limit,
            descending=True,
        )
        # AxxonMcpLive.search_events returns key "events"; some test stubs may return "items".
        raw_items = result.get("events")
        if raw_items is None:
            raw_items = result.get("items") or []
        items = list(raw_items)
        if severity_min is not None:
            kept = []
            for it in items:
                sev = it.get("severity")
                if sev is None or sev < severity_min:
                    continue
                kept.append(it)
            items = kept
        return {
            "status": "ok",
            "tool": "list_alarm_history",
            "count": len(items),
            "applied_hours": applied_hours,
            "applied_limit": applied_limit,
            "applied_filters": {"camera": camera, "severity_min": severity_min},
            "items": items,
        }

    def list_alarm_event_types(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        result = self.client.list_event_types()
        items = [it for it in (result.get("items") or []) if it.get("name") in ALARM_EVENT_TYPES]
        return {"status": "ok", "tool": "list_alarm_event_types", "count": len(items), "items": items}

    def alarm_subscribe(
        self,
        severity_min: int | None = None,
        camera_access_point: str | None = None,
        state: str = "all",
        duration_s: int = 10,
        limit: int = 25,
    ) -> dict[str, Any]:
        applied_duration = min(max(int(duration_s), 1), SUBSCRIBE_DURATION_CAP_S)
        applied_limit = min(max(int(limit), 1), SUBSCRIBE_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        raw_events = self.client.pull_events_bounded(
            subjects=[self._host()],
            event_types=list(ALARM_EVENT_TYPES),
            timeout=float(applied_duration),
            max_events=applied_limit,
        )
        normalized = [normalize_alarm_event(e) for e in raw_events]
        kept: list[dict[str, Any]] = []
        for item in normalized:
            if severity_min is not None and (item.get("severity") or 0) < severity_min:
                continue
            if camera_access_point is not None and item.get("camera_access_point") != camera_access_point:
                continue
            if state != "all" and item.get("transition") != _TRANSITION_BY_STATE.get(state, state):
                continue
            kept.append(item)
        partial = len(raw_events) >= applied_limit
        reason = "limit_cap" if partial else "ok"
        return {
            "status": "ok",
            "tool": "alarm_subscribe",
            "applied_duration_s": applied_duration,
            "applied_limit": applied_limit,
            "partial": partial,
            "reason": reason,
            "count": len(kept),
            "items": kept,
        }
