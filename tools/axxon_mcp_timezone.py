#!/usr/bin/env python3
"""TimeZoneManager tools for Axxon One MCP (Phase 19).

Read and change the server timezone, NTP sync, and the timezone database. The
three writes (`SetTimeZone`, `SetNTP`, `ChangeTimeZones`) are approval-gated
(`AXXON_TIMEZONE_APPROVE=1`) plus a per-call confirmation token, mirroring the
audit-injector idiom. TimeZoneManager carries no etag, so the writes are plain
builds. Direct gRPC against `TimeZoneManager`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from google.protobuf.duration_pb2 import Duration
from google.protobuf.wrappers_pb2 import BoolValue

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

TIMEZONE_APPROVE_ENV = "AXXON_TIMEZONE_APPROVE"
TIMEZONE_CONFIRMATION = "CONFIRM-timezone-set"
TIMEZONE_PROTO = "axxonsoft/bl/tz/TimeZonesManager.proto"
TIMEZONE_PB2 = "axxonsoft.bl.tz.TimeZonesManager_pb2"

TIMEZONE_TOOL_NAMES = (
    "timezone_connect_axxon_profile",
    "list_timezones",
    "get_timezone",
    "get_ntp",
    "set_timezone",
    "set_ntp",
    "change_timezones",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(TIMEZONE_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpTimezone:
    """Phase 19 TimeZoneManager tools (reads + gated timezone/NTP/database writes)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def timezone_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+write",
            "approval_env": TIMEZONE_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.timezone_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.timezone_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(TIMEZONE_PROTO, "TimeZoneManager"), client.import_module(TIMEZONE_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {TIMEZONE_APPROVE_ENV}=1 to enable timezone writes.", "approval_env": TIMEZONE_APPROVE_ENV}
        if confirmation != TIMEZONE_CONFIRMATION:
            return {"status": "gap", "message": f"timezone writes require confirmation={TIMEZONE_CONFIRMATION}"}
        return None

    def list_timezones(self, full: bool = False) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        view = pb2.ListTimeZonesRequest.VIEW_MODE_FULL if full else pb2.ListTimeZonesRequest.VIEW_MODE_STRIPPED
        resp = stub.ListTimeZones(pb2.ListTimeZonesRequest(view=view), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "count": len(resp.items),
            "items": [{"id": z.id, "name": z.name, "interval_count": len(z.intervals)} for z in resp.items],
        }

    def get_timezone(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        resp = stub.GetTimeZone(pb2.GetTimeZoneRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "current_timezone": {"id": resp.current_timezone.timezone_id, "name": resp.current_timezone.timezone_name},
            "daylight_saving_mode_off": resp.daylight_saving_mode_off.value,
            "available_count": len(resp.available_timezones),
            "available_timezones": [{"id": z.timezone_id, "name": z.timezone_name} for z in resp.available_timezones],
        }

    def get_ntp(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        resp = stub.GetNTP(pb2.ListNTPRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "ntp_url": resp.ntp.ntp_url,
            "sync_ip_devices": resp.ntp.sync_ip_devices,
            "refresh_rate_s": resp.ntp.refresh_rate.seconds,
        }

    def set_timezone(self, timezone_id: str = "", daylight_saving_mode_off: bool | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        if not timezone_id:
            return {"status": "error", "message": "timezone_id is required"}
        stub, pb2 = self._stub_and_pb2()
        req = pb2.SetTimeZoneRequest(timezone_id=timezone_id)
        if daylight_saving_mode_off is not None:
            req.daylight_saving_mode_off.CopyFrom(BoolValue(value=bool(daylight_saving_mode_off)))
        stub.SetTimeZone(req, timeout=self.ensure_client().config.timeout)
        current = stub.GetTimeZone(pb2.GetTimeZoneRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "applied",
            "current_timezone": {"id": current.current_timezone.timezone_id, "name": current.current_timezone.timezone_name},
            "daylight_saving_mode_off": current.daylight_saving_mode_off.value,
        }

    def set_ntp(self, ntp_url: str = "", sync_ip_devices: bool = False, refresh_rate_s: int | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        stub, pb2 = self._stub_and_pb2()
        ntp = pb2.NTP(ntp_url=ntp_url, sync_ip_devices=bool(sync_ip_devices))
        if refresh_rate_s is not None:
            ntp.refresh_rate.CopyFrom(Duration(seconds=int(refresh_rate_s)))
        stub.SetNTP(pb2.SetNTPRequest(ntp=ntp), timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "ntp_url": ntp_url, "sync_ip_devices": bool(sync_ip_devices), "refresh_rate_s": refresh_rate_s}

    def change_timezones(
        self,
        removed_zones: list[str] | None = None,
        added_zones: list[dict[str, str]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        removed_zones = removed_zones or []
        added_zones = added_zones or []
        if not removed_zones and not added_zones:
            return {"status": "error", "message": "provide at least one of removed_zones, added_zones"}
        stub, pb2 = self._stub_and_pb2()
        req = pb2.ChangeTimeZonesRequest(removed_zones=list(removed_zones))
        for z in added_zones:
            req.added_zones.append(pb2.TimeZone(id=z["id"], name=z.get("name", "")))
        stub.ChangeTimeZones(req, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "removed_zones": list(removed_zones), "added_zones": [z["id"] for z in added_zones]}
