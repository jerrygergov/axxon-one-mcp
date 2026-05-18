#!/usr/bin/env python3
"""Read-only tools for layouts, maps, and videowalls.

Mirrors the dataclass-with-factories pattern of axxon_mcp_view.py and
axxon_mcp_alarms.py. URLs are never returned; map image bytes are byte-capped
and only metadata is echoed in tool responses.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


LIST_LIMIT_CAP = 200
MAP_IMAGE_BYTES_CAP = 4_194_304
LAYOUT_VIEW_MODES = ("meta", "full")
LAYOUT_VIEW_MAP = {"meta": "VIEW_MODE_ONLY_META", "full": "VIEW_MODE_FULL"}
MAP_TYPE_CHOICES = ("MAP_TYPE_RASTER", "MAP_TYPE_GOOGLE", "MAP_TYPE_OSM")


def normalize_layout(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten LayoutFull or LayoutMeta to a stable schema."""
    meta = raw.get("meta") or {}
    body = raw.get("body") or {}
    cells = body.get("cells")
    return {
        "layout_id": meta.get("layout_id") or body.get("id") or "",
        "display_name": body.get("display_name"),
        "is_user_defined": body.get("is_user_defined"),
        "is_for_alarm": body.get("is_for_alarm"),
        "owned_by_user": bool(meta.get("owned_by_user")),
        "etag": meta.get("etag", ""),
        "has_write_access": bool(meta.get("has_write_access")),
        "cells_count": len(cells) if isinstance(cells, dict) else None,
        "map_id": body.get("map_id"),
    }


def normalize_map(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Map with meta to a stable schema."""
    meta = raw.get("meta") or {}
    sharing = meta.get("sharing") or {}
    return {
        "map_id": meta.get("id") or "",
        "name": meta.get("name", ""),
        "type": meta.get("type", ""),
        "access": meta.get("access", ""),
        "owner": sharing.get("owner", ""),
        "sharing_kind": sharing.get("kind", ""),
        "etag": meta.get("etag", ""),
        "image_etag": meta.get("image_etag", ""),
    }


def normalize_wall(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten WallInfo to a stable schema; never echoes the data blob."""
    data_b64 = (raw.get("data") or {}).get("data") or ""
    try:
        data_size = len(base64.b64decode(data_b64)) if data_b64 else 0
    except Exception:
        data_size = 0
    return {
        "wall_id": raw.get("wall_id", ""),
        "host_name": raw.get("host_name", ""),
        "pid": int(raw.get("pid") or 0),
        "ppid": int(raw.get("ppid") or 0),
        "name": raw.get("name", ""),
        "display_name": raw.get("display_name", ""),
        "seq_number": int(raw.get("seq_number") or 0),
        "data_size": data_size,
    }


def normalize_marker(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten a marker entry to a stable schema."""
    return {
        "marker_id": raw.get("id") or raw.get("marker_id") or "",
        "access_point": raw.get("access_point") or raw.get("ap") or "",
        "position": raw.get("position") or {},
        "marker_type": raw.get("marker_type") or raw.get("type") or "",
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
class AxxonMcpViewObjects:
    """Read-only tools for layouts, maps, and videowalls."""

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

    def _ensure_client(self) -> Any:
        if self.client is None:
            self.connect_axxon_profile("env")
        return self.client

    def list_layouts(self, view: str = "meta", limit: int = 50) -> dict[str, Any]:
        if view not in LAYOUT_VIEW_MODES:
            return {
                "status": "gap",
                "tool": "list_layouts",
                "message": f"view must be one of {LAYOUT_VIEW_MODES}, got {view!r}",
            }
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        applied_view = LAYOUT_VIEW_MAP[view]
        client = self._ensure_client()
        resp = client.list_layouts(view=applied_view)
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = [normalize_layout(it) for it in (body or {}).get("items", [])][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_layouts",
            "count": len(items),
            "applied_view": applied_view,
            "applied_limit": applied_limit,
            "current": (body or {}).get("current", ""),
            "items": items,
        }

    def get_layout(self, layout_id: str, etag: str | None = None) -> dict[str, Any]:
        client = self._ensure_client()
        resp = client.batch_get_layouts([{"layout_id": layout_id, "etag": etag or ""}])
        body = resp.get("body") if isinstance(resp, dict) else {}
        for raw in (body or {}).get("items", []):
            if (raw.get("meta") or {}).get("layout_id") == layout_id:
                return {"status": "ok", "tool": "get_layout", "item": normalize_layout(raw)}
        return {
            "status": "gap",
            "tool": "get_layout",
            "message": f"Layout not found: {layout_id}",
        }

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        client = self._ensure_client()
        client.layouts_on_view(layouts)
        return {"status": "ok", "tool": "layouts_on_view", "pushed": len(layouts)}

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        client = self._ensure_client()
        resp = client.list_layout_images(layout_id)
        if not isinstance(resp, dict) or resp.get("status") != 200:
            return {
                "status": "gap",
                "tool": "list_layout_images",
                "message": f"Layout not found or unreadable: {layout_id}",
            }
        body = resp.get("body") or {}
        items = list(body.get("images", []))
        return {
            "status": "ok",
            "tool": "list_layout_images",
            "layout_id": layout_id,
            "count": len(items),
            "items": items,
        }
