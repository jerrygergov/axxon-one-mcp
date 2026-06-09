#!/usr/bin/env python3
"""GlobalTrackerService read tool for Axxon One MCP (Phase A).

Read a global-tracker profile (GetProfile): cross-camera tracking profile metadata. A
server-streaming `read` RPC, no approval gate. Profile face images are never loaded
(load_images is forced off) and image bytes are never returned; only metadata and the LPR
string are summarized. The stream is item-capped. The other six GlobalTrackerService RPCs are
fixture-blocked on the stand and are intentionally not exposed here. Direct gRPC against
`GlobalTrackerService`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

GLOBAL_TRACKER_PROTO = "axxonsoft/bl/globalTracker/GlobalTracker.proto"
GLOBAL_TRACKER_PB2 = "axxonsoft.bl.globalTracker.GlobalTracker_pb2"

GLOBAL_TRACKER_TOOL_NAMES = (
    "global_tracker_connect_axxon_profile",
    "get_profile",
)

MAX_ITEMS = 100
DEFAULT_ITEMS = 20


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpGlobalTracker:
    """Phase A GlobalTrackerService read tool (cross-camera profile metadata, no images)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def global_tracker_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.global_tracker_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.global_tracker_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(GLOBAL_TRACKER_PROTO, "GlobalTrackerService"), client.import_module(GLOBAL_TRACKER_PB2)

    @staticmethod
    def _profile_summary(profile: Any) -> dict[str, Any]:
        which = profile.WhichOneof("data")
        summary: dict[str, Any] = {"id": profile.id, "type": profile.type, "data_kind": which}
        # Only the LPR string is surfaced; face image bytes (data_images) are never returned.
        if which == "data_string":
            summary["data_string"] = profile.data_string
        return summary

    def get_profile(self, profile_id: str = "", max_items: int | None = None) -> dict[str, Any]:
        """Read a global-tracker profile by id (metadata only; images never loaded/returned).

        Args:
            profile_id (str): Profile GUID to read.
            max_items (int, optional): Cap on streamed profile items; clamped to MAX_ITEMS.

        Returns:
            (dict): {"status": "ok", "tool": "get_profile", "count", "profiles", "truncated"}.
        """
        if not profile_id:
            return {"status": "gap", "tool": "get_profile", "message": "profile_id is required."}
        stub, pb2 = self._stub_and_pb2()
        cap = _clamp(int(max_items if max_items is not None else DEFAULT_ITEMS), 1, MAX_ITEMS)
        request = pb2.GetProfileRequest(id=profile_id, load_images=False)
        profiles: list[dict[str, Any]] = []
        truncated = False
        for response in stub.GetProfile(request, timeout=self.ensure_client().config.timeout):
            if response.HasField("profile"):
                profiles.append(self._profile_summary(response.profile))
            if len(profiles) >= cap:
                truncated = True
                break
        return {"status": "ok", "tool": "get_profile", "count": len(profiles), "profiles": profiles, "truncated": truncated}
