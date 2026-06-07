#!/usr/bin/env python3
"""ConfigurationService unit-config tools for Axxon One MCP (Phase 36).

Read similar units (ListSimilarUnits) and creatable factories (BatchGetFactories), and
apply reversible single-property unit changes (ChangeConfig / ChangeConfigStream). The two
writes are approval-gated (`AXXON_CONFIG_CHANGE_APPROVE=1`) plus a per-call confirmation
token, mirroring the batch-alerts idiom. Direct gRPC against `ConfigurationService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

CONFIG_CHANGE_APPROVE_ENV = "AXXON_CONFIG_CHANGE_APPROVE"
CONFIG_CHANGE_CONFIRMATION = "CONFIRM-config-change"
CONFIG_PROTO = "axxonsoft/bl/config/ConfigurationService.proto"
CONFIG_PB2 = "axxonsoft.bl.config.ConfigurationService_pb2"

CONFIG_CHANGE_TOOL_NAMES = (
    "config_change_connect_axxon_profile",
    "list_similar_units",
    "batch_get_factories",
    "change_unit_property",
    "change_unit_property_stream",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(CONFIG_CHANGE_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpConfigChange:
    """Phase 36 ConfigurationService tools (reads + gated reversible unit changes)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def config_change_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": CONFIG_CHANGE_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.config_change_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.config_change_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(CONFIG_PROTO, "ConfigurationService"), client.import_module(CONFIG_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {CONFIG_CHANGE_APPROVE_ENV}=1 to enable unit config changes.", "approval_env": CONFIG_CHANGE_APPROVE_ENV}
        if confirmation != CONFIG_CHANGE_CONFIRMATION:
            return {"status": "gap", "message": f"unit config changes require confirmation={CONFIG_CHANGE_CONFIRMATION}"}
        return None

    def _similar_brief(self, unit: Any) -> dict[str, Any]:
        return {
            "uid": getattr(unit, "uid", ""),
            "type": getattr(unit, "type", ""),
            "display_name": getattr(unit, "display_name", ""),
            "display_id": getattr(unit, "display_id", ""),
        }

    def list_similar_units(self, uid: str = "", node_name: str = "Server", page_size: int = 50, page_token: str = "", by_unit_type: bool = False) -> dict[str, Any]:
        if not uid:
            return {"status": "error", "tool": "list_similar_units", "message": "provide a unit uid"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.ListSimilarUnitsRequest(uid=uid, node_name=node_name, page_size=int(page_size), page_token=page_token)
        if by_unit_type:
            request.search_mode = pb2.ListSimilarUnitsRequest.BY_UNIT_TYPE
        response = stub.ListSimilarUnits(request, timeout=self.ensure_client().config.timeout)
        units = [self._similar_brief(u) for u in response.similar_units]
        return {"status": "ok", "tool": "list_similar_units", "unit_count": len(units), "units": units, "next_page_token": response.next_page_token}

    def batch_get_factories(self, unit_types: list[str] | None = None, parent_uid: str = "", ignore_possible_limits: bool = True) -> dict[str, Any]:
        types = [t for t in (unit_types or []) if t]
        if not types:
            return {"status": "error", "tool": "batch_get_factories", "message": "provide at least one unit_type"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.BatchGetFactoriesRequest()
        for ut in types:
            f = request.factories.add()
            f.unit_type = ut
            f.parent_uid = parent_uid
            f.ignore_possible_limits = bool(ignore_possible_limits)
        response = stub.BatchGetFactories(request, timeout=self.ensure_client().config.timeout)
        items = [{"unit_type": it.requested.unit_type, "status": int(it.status), "factory_type": getattr(it.factory, "type", "")} for it in response.items]
        return {"status": "ok", "tool": "batch_get_factories", "item_count": len(items), "items": items}

    def _build_change_request(self, pb2: Any, uid: str, unit_type: str, property_id: str, value_string: str) -> Any:
        request = pb2.ChangeConfigRequest()
        unit = request.changed.add()
        unit.uid = uid
        unit.type = unit_type
        prop = unit.properties.add()
        prop.id = property_id
        prop.value_string = value_string
        return request

    def change_unit_property(self, uid: str = "", unit_type: str = "", property_id: str = "", value_string: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "change_unit_property", **gated}
        if not uid or not unit_type or not property_id:
            return {"status": "error", "tool": "change_unit_property", "message": "provide uid, unit_type and property_id"}
        stub, pb2 = self._stub_and_pb2()
        request = self._build_change_request(pb2, uid, unit_type, property_id, value_string)
        response = stub.ChangeConfig(request, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": "change_unit_property", "failed": [u.uid for u in response.failed], "added": list(response.added)}

    def change_unit_property_stream(self, uid: str = "", unit_type: str = "", property_id: str = "", value_string: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "change_unit_property_stream", **gated}
        if not uid or not unit_type or not property_id:
            return {"status": "error", "tool": "change_unit_property_stream", "message": "provide uid, unit_type and property_id"}
        stub, pb2 = self._stub_and_pb2()
        request = self._build_change_request(pb2, uid, unit_type, property_id, value_string)
        failed: list[str] = []
        for response in stub.ChangeConfigStream(request, timeout=self.ensure_client().config.timeout):
            failed.extend(u.uid for u in response.failed)
        return {"status": "applied", "tool": "change_unit_property_stream", "failed": failed}
