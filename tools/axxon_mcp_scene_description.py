#!/usr/bin/env python3
"""NgpNodeService read tool for Axxon One MCP (Phase A).

Read the node scene descriptions (ListSceneDescription): per-camera scene geometry used by
analytics. A single unary `read` RPC with paging, no approval gate. Direct gRPC against
`NgpNodeService`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

SCENE_DESCRIPTION_PROTO = "axxonsoft/bl/node/Node.Ancillary.proto"
SCENE_DESCRIPTION_PB2 = "axxonsoft.bl.node.Node.Ancillary_pb2"

SCENE_DESCRIPTION_TOOL_NAMES = (
    "scene_description_connect_axxon_profile",
    "list_scene_description",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpSceneDescription:
    """Phase A NgpNodeService read tool (per-camera scene descriptions)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def scene_description_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.scene_description_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.scene_description_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(SCENE_DESCRIPTION_PROTO, "NgpNodeService"), client.import_module(SCENE_DESCRIPTION_PB2)

    def list_scene_description(self, page_token: str = "", page_size: int = 0) -> dict[str, Any]:
        """List per-camera scene descriptions (access point, camera, scene class), one page.

        Args:
            page_token (str, optional): Continuation token from a prior page.
            page_size (int, optional): Max entries per page; 0 lets the server choose.

        Returns:
            (dict): {"status": "ok", "tool": "list_scene_description", "count", "scenes", "next_page_token"}.
        """
        stub, pb2 = self._stub_and_pb2()
        request = pb2.ListSceneDescriptionRequest(page_token=page_token, page_size=page_size)
        response = stub.ListSceneDescription(request, timeout=self.ensure_client().config.timeout)
        scenes = list(response.scene_descriptions)
        return {
            "status": "ok",
            "tool": "list_scene_description",
            "count": len(scenes),
            "scenes": [
                {"access_point": s.access_point, "camera_access_point": s.camera_access_point, "scene_description_class": s.scene_description_class}
                for s in scenes
            ],
            "next_page_token": response.next_page_token,
        }
