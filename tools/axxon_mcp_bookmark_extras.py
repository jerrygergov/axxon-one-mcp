#!/usr/bin/env python3
"""BookmarkService extra tools for Axxon One MCP (Phase 38).

Update an existing bookmark's message (UpdateBookmark), set its exported time
(SetExportedTime), and render its track (RenderTrack). The two writes are approval-gated
(`AXXON_BOOKMARK_EXTRAS_APPROVE=1`) plus a per-call confirmation token, mirroring the
archive-volume idiom. Direct gRPC against `BookmarkService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

BOOKMARK_EXTRAS_APPROVE_ENV = "AXXON_BOOKMARK_EXTRAS_APPROVE"
BOOKMARK_EXTRAS_CONFIRMATION = "CONFIRM-bookmark-extras"
BOOKMARK_PROTO = "axxonsoft/bl/bookmarks/BookmarkService.proto"
BOOKMARK_PB2 = "axxonsoft.bl.bookmarks.BookmarkService_pb2"

BOOKMARK_EXTRAS_TOOL_NAMES = (
    "bookmark_extras_connect_axxon_profile",
    "update_bookmark",
    "set_bookmark_exported_time",
    "render_bookmark_track",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(BOOKMARK_EXTRAS_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpBookmarkExtras:
    """Phase 38 BookmarkService extra tools (gated update/set-exported + render track read)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def bookmark_extras_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": BOOKMARK_EXTRAS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.bookmark_extras_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.bookmark_extras_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(BOOKMARK_PROTO, "BookmarkService"), client.import_module(BOOKMARK_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {BOOKMARK_EXTRAS_APPROVE_ENV}=1 to enable bookmark writes.", "approval_env": BOOKMARK_EXTRAS_APPROVE_ENV}
        if confirmation != BOOKMARK_EXTRAS_CONFIRMATION:
            return {"status": "gap", "message": f"bookmark writes require confirmation={BOOKMARK_EXTRAS_CONFIRMATION}"}
        return None

    def _get_bookmark(self, stub: Any, pb2: Any, bookmark_id: str) -> Any:
        return stub.GetBookmark(pb2.GetBookmarkRequest(id=bookmark_id), timeout=self.ensure_client().config.timeout).bookmark

    def update_bookmark(self, bookmark_id: str = "", message: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "update_bookmark", **gated}
        if not bookmark_id:
            return {"status": "error", "tool": "update_bookmark", "message": "provide a bookmark_id"}
        stub, pb2 = self._stub_and_pb2()
        bookmark = self._get_bookmark(stub, pb2, bookmark_id)
        bookmark.message = message
        response = stub.UpdateBookmark(pb2.UpdateBookmarkRequest(bookmark=bookmark), timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": "update_bookmark", "bookmark_id": response.bookmark.id, "message": response.bookmark.message}

    def set_bookmark_exported_time(self, bookmark_id: str = "", exported_time: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "set_bookmark_exported_time", **gated}
        if not bookmark_id or not exported_time:
            return {"status": "error", "tool": "set_bookmark_exported_time", "message": "provide a bookmark_id and an ISO-8601 exported_time"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.SetExportedTimeRequest(id=bookmark_id)
        request.exported_time.FromDatetime(datetime.fromisoformat(exported_time))
        stub.SetExportedTime(request, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": "set_bookmark_exported_time", "bookmark_id": bookmark_id, "exported_time": exported_time}

    def render_bookmark_track(self, bookmark_id: str = "") -> dict[str, Any]:
        if not bookmark_id:
            return {"status": "error", "tool": "render_bookmark_track", "message": "provide a bookmark_id"}
        stub, pb2 = self._stub_and_pb2()
        bookmark = self._get_bookmark(stub, pb2, bookmark_id)
        response = stub.RenderTrack(pb2.RenderTrackRequest(bookmark=bookmark), timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "render_bookmark_track", "bookmark_id": response.bookmark.id, "has_boundary": response.bookmark.HasField("boundary")}
