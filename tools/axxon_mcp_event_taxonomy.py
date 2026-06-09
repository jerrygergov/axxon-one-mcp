#!/usr/bin/env python3
"""EventDescription read tool for Axxon One MCP (Phase A).

Read the event grouping tags (GetEventGroupingTags): the field descriptors used to group and
filter events, useful when building event-search filters. A single unary `read` RPC, no approval
gate. Direct gRPC against `EventDescription`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

EVENT_TAXONOMY_PROTO = "axxonsoft/bl/logic/EventDescription.proto"
EVENT_TAXONOMY_PB2 = "axxonsoft.bl.logic.EventDescription_pb2"

EVENT_TAXONOMY_TOOL_NAMES = (
    "event_taxonomy_connect_axxon_profile",
    "get_event_grouping_tags",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpEventTaxonomy:
    """Phase A EventDescription read tool (event grouping tags / field descriptors)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def event_taxonomy_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.event_taxonomy_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.event_taxonomy_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(EVENT_TAXONOMY_PROTO, "EventDescription"), client.import_module(EVENT_TAXONOMY_PB2)

    def get_event_grouping_tags(self) -> dict[str, Any]:
        """Read the event grouping tags (field descriptors for event grouping/filtering).

        Returns:
            (dict): {"status": "ok", "tool": "get_event_grouping_tags", "count": int, "fields": [...]}.
        """
        stub, pb2 = self._stub_and_pb2()
        response = stub.GetEventGroupingTags(pb2.GetEventGroupingTagsRequest(), timeout=self.ensure_client().config.timeout)
        fields = list(response.tags.fields)
        return {
            "status": "ok",
            "tool": "get_event_grouping_tags",
            "count": len(fields),
            "fields": [{"id": f.id, "name": f.name, "type": f.type} for f in fields],
        }
