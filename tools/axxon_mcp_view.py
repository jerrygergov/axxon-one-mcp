#!/usr/bin/env python3
"""Read-only live and archive viewing tools for the Axxon One MCP server.

URLs only — this module never proxies media bytes. Callers fetch URLs
directly with the Bearer token issued by AxxonApiClient.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    _SUPPORTED_LIVE_FORMATS = ("mjpeg", "hls", "mp4", "rtsp")

    def _legacy_ap(self, access_point: str) -> str:
        return access_point.removeprefix("hosts/")

    def _camera_index(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {cam.get("access_point", ""): cam for cam in inventory.get("cameras", []) if cam.get("access_point")}

    def _auth(self) -> dict[str, str]:
        return {"header": "Authorization", "scheme": "Bearer"}

    def live_view(
        self,
        camera_access_point: str,
        duration_s: int = DEFAULT_DURATION_S,
        fps: int = DEFAULT_FPS,
        width: int = DEFAULT_SNAPSHOT_WIDTH,
        format: str = "mjpeg",
    ) -> dict[str, Any]:
        if format not in self._SUPPORTED_LIVE_FORMATS:
            return {
                "status": "gap",
                "tool": "live_view",
                "message": f"Unsupported format '{format}'. Supported: {self._SUPPORTED_LIVE_FORMATS}",
            }
        inventory = self._ensure_inventory()
        cameras = self._camera_index(inventory)
        if camera_access_point not in cameras:
            return {
                "status": "gap",
                "tool": "live_view",
                "message": f"Camera not found in inventory: {camera_access_point}",
            }
        applied_duration = min(max(duration_s, 1), DEFAULT_DURATION_S)
        applied_fps = min(max(fps, 1), DEFAULT_FPS)
        applied_width = min(max(width, 64), 1920)
        legacy = self._legacy_ap(camera_access_point)
        base = self.client.config.http_url.rstrip("/")
        if format == "mjpeg":
            url = f"{base}/live/media/{legacy}?w={applied_width}&h=0&fps={applied_fps}"
        elif format == "hls":
            url = f"{base}/live/media/{legacy}?format=hls"
        elif format == "mp4":
            url = f"{base}/live/media/{legacy}?format=mp4"
        else:  # rtsp
            url = f"{base}/live/media/{legacy}?format=rtsp"
        if format == "mjpeg":
            caps = {
                "bytes": DEFAULT_MAX_BYTES,
                "time_s": applied_duration,
                "fps": applied_fps,
                "width": applied_width,
            }
        else:
            caps = {"bytes": DEFAULT_MAX_BYTES, "time_s": applied_duration}
        return {
            "status": "ok",
            "tool": "live_view",
            "camera": camera_access_point,
            "url": url,
            "auth": self._auth(),
            "format": format,
            "caps": caps,
        }

    def snapshot_batch(
        self,
        camera_access_points: list[str],
        ts: str = "now",
        width: int = DEFAULT_SNAPSHOT_WIDTH,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        cameras = self._camera_index(inventory)
        clamped = list(camera_access_points)[:SNAPSHOT_BATCH_LIMIT]
        applied_width = min(max(width, 64), 1920)
        base = self.client.config.http_url.rstrip("/")
        items: list[dict[str, Any]] = []
        for ap in clamped:
            if ap not in cameras:
                items.append({"status": "gap", "camera": ap, "message": "not in inventory"})
                continue
            legacy = self._legacy_ap(ap)
            if ts == "now":
                url = f"{base}/live/media/snapshot/{legacy}?w={applied_width}&h=0"
            else:
                ts_q = quote(ts, safe="")
                url = f"{base}/archive/media/{legacy}/{ts_q}?threshold={ARCHIVE_FRAME_THRESHOLD_MS}&w={applied_width}&h=0"
            items.append(
                {
                    "status": "ok",
                    "camera": ap,
                    "url": url,
                    "auth": self._auth(),
                    "caps": {"bytes": DEFAULT_MAX_BYTES},
                }
            )
        return {
            "status": "ok",
            "tool": "snapshot_batch",
            "ts": ts,
            "items": items,
            "applied_limit": SNAPSHOT_BATCH_LIMIT,
        }

    def _default_archive_ap(self, inventory: dict[str, Any]) -> str | None:
        for arc in inventory.get("archives", []):
            ap = arc.get("access_point")
            if ap:
                return ap
        return None

    def archive_scrub(
        self,
        camera_access_point: str,
        hours: int = 1,
        archive_access_point: str | None = None,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inventory):
            return {
                "status": "gap",
                "tool": "archive_scrub",
                "message": f"Camera not found in inventory: {camera_access_point}",
            }
        archive_ap = archive_access_point or self._default_archive_ap(inventory)
        if archive_ap is None:
            return {
                "status": "fixture-needed",
                "tool": "archive_scrub",
                "message": "No archive access point in inventory.",
                "fixture": {"required": ["MultimediaStorage.*/MultimediaStorage"], "missing": ["archive"]},
            }
        applied_hours = min(max(hours, 1), 24)
        begin, end = self.client.archive_time_range_legacy(hours=applied_hours)
        legacy = self._legacy_ap(camera_access_point)
        calendar = self.client.archive_calendar(camera_access_point, archive_ap)
        intervals = self.client.archive_intervals(legacy, begin, end, archive_ap=archive_ap)
        sample_ts = (intervals[-1].get("end") if intervals else end)
        sample_ts_q = quote(sample_ts, safe="")
        base = self.client.config.http_url.rstrip("/")
        sample_url = f"{base}/archive/media/{legacy}/{sample_ts_q}?threshold={ARCHIVE_FRAME_THRESHOLD_MS}&w={DEFAULT_SNAPSHOT_WIDTH}&h=0"
        return {
            "status": "ok",
            "tool": "archive_scrub",
            "camera": camera_access_point,
            "archive": archive_ap,
            "calendar": calendar,
            "intervals": intervals,
            "sample_frame_url": sample_url,
            "auth": self._auth(),
            "caps": {"bytes": DEFAULT_MAX_BYTES, "hours": applied_hours},
        }
