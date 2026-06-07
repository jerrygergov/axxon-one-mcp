#!/usr/bin/env python3
"""LayoutManager tools for Axxon One MCP (Phase 41).

Read layouts by id (BatchGetLayouts, etag-conditional), push a layout set to the view
(LayoutsOnView), and rename a layout (Update). The rename write is approval-gated
(`AXXON_LAYOUT_MANAGER_APPROVE=1`) plus a per-call confirmation token, mirroring the
config-change idiom. Direct gRPC against `LayoutManager`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

LAYOUT_MANAGER_APPROVE_ENV = "AXXON_LAYOUT_MANAGER_APPROVE"
LAYOUT_MANAGER_CONFIRMATION = "CONFIRM-layout-update"
LAYOUT_PROTO = "axxonsoft/bl/layout/LayoutManager.proto"
LAYOUT_PB2 = "axxonsoft.bl.layout.LayoutManager_pb2"

LAYOUT_MANAGER_TOOL_NAMES = (
    "layout_manager_connect_axxon_profile",
    "batch_get_layouts",
    "layouts_on_view",
    "update_layout_name",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(LAYOUT_MANAGER_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpLayoutManager:
    """Phase 41 LayoutManager tools (reads + gated reversible layout rename)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def layout_manager_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": LAYOUT_MANAGER_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.layout_manager_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.layout_manager_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(LAYOUT_PROTO, "LayoutManager"), client.import_module(LAYOUT_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {LAYOUT_MANAGER_APPROVE_ENV}=1 to enable layout updates.", "approval_env": LAYOUT_MANAGER_APPROVE_ENV}
        if confirmation != LAYOUT_MANAGER_CONFIRMATION:
            return {"status": "gap", "message": f"layout updates require confirmation={LAYOUT_MANAGER_CONFIRMATION}"}
        return None

    def _find_layout(self, stub: Any, pb2: Any, layout_id: str) -> Any:
        for item in stub.ListLayouts(pb2.ListLayoutsRequest(view=pb2.VIEW_MODE_FULL), timeout=self.ensure_client().config.timeout).items:
            if item.meta.layout_id == layout_id:
                return item
        return None

    def batch_get_layouts(self, layout_id: str = "", etag: str = "") -> dict[str, Any]:
        if not layout_id:
            return {"status": "error", "tool": "batch_get_layouts", "message": "provide a layout_id"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.BatchGetLayoutsRequest()
        loc = request.items.add()
        loc.layout_id = layout_id
        loc.etag = etag
        response = stub.BatchGetLayouts(request, timeout=self.ensure_client().config.timeout)
        items = [{"layout_id": it.meta.layout_id, "display_name": it.body.display_name, "etag": it.meta.etag} for it in response.items]
        return {"status": "ok", "tool": "batch_get_layouts", "item_count": len(items), "items": items, "not_found": list(response.not_found_items)}

    def layouts_on_view(self, layout_id: str = "", display_name: str = "") -> dict[str, Any]:
        if not layout_id:
            return {"status": "error", "tool": "layouts_on_view", "message": "provide a layout_id"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.LayoutsOnViewRequest()
        entry = request.layouts.add()
        entry.layout_id = layout_id
        entry.layout_display_name = display_name
        stub.LayoutsOnView(request, timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "layouts_on_view", "layout_id": layout_id}

    def update_layout_name(self, layout_id: str = "", display_name: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "update_layout_name", **gated}
        if not layout_id:
            return {"status": "error", "tool": "update_layout_name", "message": "provide a layout_id"}
        stub, pb2 = self._stub_and_pb2()
        layout = self._find_layout(stub, pb2, layout_id)
        if layout is None:
            return {"status": "error", "tool": "update_layout_name", "message": f"layout {layout_id} not found"}
        request = pb2.UpdateRequest()
        tagged = request.modified.add()
        tagged.etag = layout.meta.etag
        tagged.body.CopyFrom(layout.body)
        tagged.body.display_name = display_name
        stub.Update(request, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": "update_layout_name", "layout_id": layout_id, "display_name": display_name}
