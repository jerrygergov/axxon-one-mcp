#!/usr/bin/env python3
"""VideowallService operator-control tools for Axxon One MCP (Phase 46).

Reversible videowall lifecycle plus a read helper:
- list_walls: ListWalls, the registered videowall coordinators (ungated).
- register_wall: RegisterWall, returns cookie_present + wall_id + seq_number.
- change_wall: ChangeWall by cookie + seq_number, bumps the wall payload.
- set_control_data: SetControlData by wall_id + seq_number.
- unregister_wall: UnregisterWall by cookie (reverses register_wall).

Mutations are gated behind `AXXON_VIDEOWALL_APPROVE=1` plus a per-call
confirmation token, mirroring the logic_control idiom. The raw register cookie
is never returned; callers get a `cookie_present` boolean plus the wall_id, and
change_wall/unregister_wall reference the wall_id while the tool resolves the
cookie it tracked internally at register time. Direct gRPC against
`VideowallService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

VIDEOWALL_APPROVE_ENV = "AXXON_VIDEOWALL_APPROVE"
VIDEOWALL_CONFIRMATION = "CONFIRM-videowall"
VIDEOWALL_PROTO = "axxonsoft/bl/videowall/Videowall.proto"
VIDEOWALL_PB2 = "axxonsoft.bl.videowall.Videowall_pb2"

VIDEOWALL_TOOL_NAMES = (
    "videowall_connect_axxon_profile",
    "list_walls",
    "register_wall",
    "change_wall",
    "set_control_data",
    "unregister_wall",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(VIDEOWALL_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpVideowall:
    """Phase 46 VideowallService operator-control tools (approval-gated mutations)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()
        self._cookies: dict[str, str] = {}

    def videowall_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "control",
            "approval_env": VIDEOWALL_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.videowall_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.videowall_connect_axxon_profile("env")
        return self.client

    def _gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {VIDEOWALL_APPROVE_ENV}=1 to enable videowall control.", "approval_env": VIDEOWALL_APPROVE_ENV}
        if confirmation != VIDEOWALL_CONFIRMATION:
            return {"status": "gap", "message": f"videowall control requires confirmation={VIDEOWALL_CONFIRMATION}"}
        return None

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(VIDEOWALL_PROTO, "VideowallService"), client.import_module(VIDEOWALL_PB2)

    def list_walls(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        walls: list[dict[str, Any]] = []
        unreachable: list[str] = []
        for resp in stub.ListWalls(pb2.ListWallsRequest(), timeout=self.ensure_client().config.timeout):
            unreachable.extend(resp.unreachable_objects)
            for wall in resp.walls:
                walls.append({"wall_id": wall.wall_id, "name": wall.name, "display_name": wall.display_name, "seq_number": wall.seq_number, "host_name": wall.host_name})
        return {"status": "ok", "count": len(walls), "walls": walls, "unreachable_objects": unreachable}

    def register_wall(self, name: str = "", display_name: str = "", host_name: str = "axxon-mcp", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if not str(name or "").strip():
            return {"status": "error", "message": "name is required"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.RegisterWallRequest(host_name=host_name, pid=os.getpid(), ppid=1, name=name, display_name=display_name or name, data=pb2.VideowallData(data=b""))
        resp = stub.RegisterWall(request, timeout=self.ensure_client().config.timeout)
        if resp.cookie:
            self._cookies[resp.wall_id] = resp.cookie
        return {"status": "registered", "cookie_present": bool(resp.cookie), "wall_id": resp.wall_id, "seq_number": resp.seq_number}

    def change_wall(self, wall_id: str = "", seq_number: int = 0, data: bytes = b"", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        cookie = self._cookies.get(str(wall_id or ""))
        if not cookie:
            return {"status": "error", "message": "unknown wall_id; register_wall first in this session"}
        stub, pb2 = self._stub_and_pb2()
        resp = stub.ChangeWall(pb2.ChangeWallRequest(cookie=cookie, data=pb2.VideowallData(data=data), seq_number=int(seq_number)), timeout=self.ensure_client().config.timeout)
        return {"status": "changed", "new_seq_number": resp.new_seq_number}

    def set_control_data(self, wall_id: str = "", seq_number: int = 0, data: bytes = b"", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if not str(wall_id or "").strip():
            return {"status": "error", "message": "wall_id is required (from register_wall)"}
        stub, pb2 = self._stub_and_pb2()
        resp = stub.SetControlData(pb2.SetControlDataRequest(wall_id=wall_id, seq_number=int(seq_number), data=pb2.ControlData(data=data)), timeout=self.ensure_client().config.timeout)
        return {"status": "set", "new_seq_number": resp.new_seq_number}

    def unregister_wall(self, wall_id: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        cookie = self._cookies.get(str(wall_id or ""))
        if not cookie:
            return {"status": "error", "message": "unknown wall_id; register_wall first in this session"}
        stub, pb2 = self._stub_and_pb2()
        stub.UnregisterWall(pb2.UnregisterWallRequest(cookie=cookie), timeout=self.ensure_client().config.timeout)
        self._cookies.pop(str(wall_id), None)
        return {"status": "unregistered", "wall_id": wall_id}
