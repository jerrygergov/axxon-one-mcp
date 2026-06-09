#!/usr/bin/env python3
"""DomainManager read tool for Axxon One MCP (Phase A).

Enumerate the domain topology (EnumerateNodes): the domain plus its member, free, and other
(transient/alien) nodes. A single unary `read` RPC, no approval gate. The DomainManager
mutations (AddNode / DropNode / ProclaimDomain) are intentionally not exposed here. Direct gRPC
against `DomainManager`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

DOMAIN_TOPOLOGY_PROTO = "axxonsoft/bl/domain/DomainManager.proto"
DOMAIN_TOPOLOGY_PB2 = "axxonsoft.bl.domain.DomainManager_pb2"

DOMAIN_TOPOLOGY_TOOL_NAMES = (
    "domain_topology_connect_axxon_profile",
    "enumerate_nodes",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpDomainTopology:
    """Phase A DomainManager read tool (domain + node enumeration)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def domain_topology_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.domain_topology_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.domain_topology_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(DOMAIN_TOPOLOGY_PROTO, "DomainManager"), client.import_module(DOMAIN_TOPOLOGY_PB2)

    def enumerate_nodes(self) -> dict[str, Any]:
        """Enumerate the domain and its member / free / other nodes.

        Returns:
            (dict): {"status": "ok", "tool": "enumerate_nodes", "domain", "node_count", "nodes", "free_node_count", "other_node_count"}.
        """
        stub, pb2 = self._stub_and_pb2()
        response = stub.EnumerateNodes(pb2.EnumerateNodesRequest(), timeout=self.ensure_client().config.timeout)
        nodes = list(response.nodes)
        return {
            "status": "ok",
            "tool": "enumerate_nodes",
            "domain": {"name": response.domain.name, "display_name": response.domain.display_name, "activated": response.domain.activated},
            "node_count": len(nodes),
            "nodes": [self._summarize_node(n) for n in nodes],
            "free_node_count": len(response.free_nodes),
            "other_node_count": len(response.other_nodes),
        }

    @staticmethod
    def _summarize_node(node: Any) -> dict[str, Any]:
        return {"name": node.name, "display_name": node.display_name, "state": node.state, "grpc_endpoints": list(node.grpc_endpoints)}
