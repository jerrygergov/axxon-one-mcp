#!/usr/bin/env python3
"""LogicService operator-control tools for Axxon One MCP (Phase 16).

Two operator mutations plus a read helper:
- list_launchable_macros: ListMacros, classify manual vs autorule macros.
- launch_macro: LaunchMacro by id.
- change_arm_state: ChangeArmState for a bounded, auto-reverting window.

Mutations are gated behind `AXXON_LOGIC_CONTROL_APPROVE=1` plus a per-call
confirmation token, mirroring the audit-injector idiom. ChangeArmState always
sends a bounded timeout so the camera arm state auto-reverts; a permanent
(unbounded) change is not allowed. Direct gRPC against `LogicService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from google.protobuf.duration_pb2 import Duration

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

LOGIC_CONTROL_APPROVE_ENV = "AXXON_LOGIC_CONTROL_APPROVE"
LOGIC_CONTROL_CONFIRMATION = "CONFIRM-logic-control"
LOGIC_PROTO = "axxonsoft/bl/logic/LogicService.proto"
LOGIC_PB2 = "axxonsoft.bl.logic.LogicService_pb2"
EVENTS_PB2 = "axxonsoft.bl.events.Events_pb2"

ARM_TIMEOUT_CAP_S = 300
ARM_STATES = {"disarm": "CS_Disarm", "arm": "CS_Arm", "arm_private": "CS_ArmPrivate"}

LOGIC_CONTROL_TOOL_NAMES = (
    "logic_control_connect_axxon_profile",
    "list_launchable_macros",
    "launch_macro",
    "change_arm_state",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(LOGIC_CONTROL_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpLogicControl:
    """Phase 16 LogicService operator-control tools (approval-gated mutations)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def logic_control_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": LOGIC_CONTROL_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.logic_control_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.logic_control_connect_axxon_profile("env")
        return self.client

    def _gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {LOGIC_CONTROL_APPROVE_ENV}=1 to enable logic control.", "approval_env": LOGIC_CONTROL_APPROVE_ENV}
        if confirmation != LOGIC_CONTROL_CONFIRMATION:
            return {"status": "gap", "message": f"logic control requires confirmation={LOGIC_CONTROL_CONFIRMATION}"}
        return None

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(LOGIC_PROTO, "LogicService"), client.import_module(LOGIC_PB2)

    def list_launchable_macros(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        data = self.ensure_client().message_to_dict(stub.ListMacros(pb2.ListMacrosRequest(), timeout=self.ensure_client().config.timeout))
        macros = [
            {"id": item.get("guid", ""), "name": item.get("name", ""), "launchable": "common" in (item.get("mode") or {})}
            for item in data.get("items", [])
        ]
        return {"status": "ok", "count": len(macros), "macros": macros}

    def launch_macro(self, macro_id: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if not str(macro_id or "").strip():
            return {"status": "error", "message": "macro_id is required"}
        stub, pb2 = self._stub_and_pb2()
        stub.LaunchMacro(pb2.LaunchMacroRequest(macro_id=macro_id), timeout=self.ensure_client().config.timeout)
        return {"status": "launched", "macro_id": macro_id}

    def change_arm_state(self, camera_ap: str = "", state: str = "", timeout_s: int = 0, confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if not str(camera_ap or "").strip():
            return {"status": "error", "message": "camera_ap is required"}
        enum_name = ARM_STATES.get(str(state).lower())
        if enum_name is None:
            return {"status": "error", "message": f"state must be one of {list(ARM_STATES)}, got {state!r}"}
        if int(timeout_s) <= 0:
            return {"status": "error", "message": "timeout_s is required and must be positive so the arm state auto-reverts"}
        applied = min(int(timeout_s), ARM_TIMEOUT_CAP_S)
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(LOGIC_PROTO, "LogicService")
        pb2 = client.import_module(LOGIC_PB2)
        events = client.import_module(EVENTS_PB2)
        state_value = getattr(events.CameraArmStateEvent, enum_name)
        request = pb2.ChangeArmStateRequest(camera_ap=camera_ap, state=state_value, timeout=Duration(seconds=applied))
        stub.ChangeArmState(request, timeout=client.config.timeout)
        return {"status": "applied", "camera_ap": camera_ap, "state": state, "timeout_s": applied, "auto_reverts": True}
