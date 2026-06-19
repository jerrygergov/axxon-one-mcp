#!/usr/bin/env python3
"""Read-only BookmarkService tools for Axxon One MCP (Phase 5G)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary, redact_admin_secrets, _body

BOOKMARK_MODE = "read-only"
BOOKMARK_PAGE_CAP = 500
BOOKMARK_TOOL_NAMES = (
    "bookmark_connect_axxon_profile",
    "bookmark_list",
    "bookmark_get",
)

_SUMMARY_FIELDS = ("id", "message", "user_id", "range", "creation_time", "timestamp", "exported_time", "categories")


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _clamp_page_size(page_size: int) -> int:
    return min(max(int(page_size), 1), BOOKMARK_PAGE_CAP)


def _summarize_bookmark(bookmark: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(bookmark)
    return {key: redacted[key] for key in _SUMMARY_FIELDS if key in redacted}


@dataclass
class AxxonMcpBookmarks:
    """Read-only Phase 5G bookmark tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    last_page_size: int = 0

    def bookmark_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": BOOKMARK_MODE}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.bookmark_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.bookmark_connect_axxon_profile("env")
        return self.client

    def bookmark_list(self, time_range: dict[str, Any], limit: int = 100, page_token: str = "") -> dict[str, Any]:
        if not isinstance(time_range, dict) or not time_range.get("begin_time") or not time_range.get("end_time"):
            return {"status": "error", "message": "A range with begin_time and end_time is required."}
        self.last_page_size = _clamp_page_size(limit)
        response = getattr(self.ensure_client(), "bookmark_list")(
            time_range, page_size=self.last_page_size, page_token=page_token
        )
        data = _body(response)
        bookmarks = [_summarize_bookmark(item) for item in data.get("bookmarks", []) if isinstance(item, dict)]
        return {
            "status": "ok",
            "count": len(bookmarks),
            "bookmarks": bookmarks,
            "next_page_token": str(data.get("next_page_token") or ""),
            "caps": {"page_size": self.last_page_size},
        }

    def bookmark_get(self, bookmark_id: str) -> dict[str, Any]:
        response = getattr(self.ensure_client(), "bookmark_get")(bookmark_id)
        return {"status": "ok", "bookmark": _summarize_bookmark(_body(response).get("bookmark", {}))}
