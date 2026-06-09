#!/usr/bin/env python3
"""StateControlService tools for Axxon One MCP (Phase B).

Read and set device state directives (GetCurrentState, GetDefaultState, SetState) for
state-controllable access points such as PTZ patrol controllers. The two reads are ungated;
SetState is approval-gated (`AXXON_STATE_CONTROL_APPROVE=1`) plus a per-call confirmation token,
mirroring the ServerSettings / control idioms. SetState is reversible: read the current state,
set, then restore by setting the captured directive (or PRIORITY_DEFAULT_STATE to drop the
override). Direct gRPC against `StateControlService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

STATE_CONTROL_APPROVE_ENV = "AXXON_STATE_CONTROL_APPROVE"
STATE_CONTROL_CONFIRMATION = "CONFIRM-state-control-set"
STATE_CONTROL_PROTO = "axxonsoft/bl/state/StateControl.proto"
STATE_CONTROL_PB2 = "axxonsoft.bl.state.StateControl_pb2"

STATE_CONTROL_TOOL_NAMES = (
    "state_control_connect_axxon_profile",
    "get_current_state",
    "get_default_state",
    "set_state",
)


def _approval_from_env() -> bool:
    return os.environ.get(STATE_CONTROL_APPROVE_ENV) == "1"


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpStateControl:
    """Phase B StateControlService tools (state reads + gated SetState)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def state_control_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": STATE_CONTROL_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.state_control_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.state_control_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(STATE_CONTROL_PROTO, "StateControlService"), client.import_module(STATE_CONTROL_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {STATE_CONTROL_APPROVE_ENV}=1 to enable state changes.", "approval_env": STATE_CONTROL_APPROVE_ENV}
        if confirmation != STATE_CONTROL_CONFIRMATION:
            return {"status": "gap", "message": f"state changes require confirmation={STATE_CONTROL_CONFIRMATION}"}
        return None

    def get_current_state(self, access_point: str = "") -> dict[str, Any]:
        """Read the current state directive result (bool) for a state-controllable access point."""
        if not access_point:
            return {"status": "gap", "tool": "get_current_state", "message": "access_point is required."}
        stub, pb2 = self._stub_and_pb2()
        response = stub.GetCurrentState(pb2.GetCurrentStateRequest(access_point=access_point), timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "get_current_state", "access_point": access_point, "result": bool(response.result)}

    def get_default_state(self, access_point: str = "") -> dict[str, Any]:
        """Read the default state directive result (bool) for a state-controllable access point."""
        if not access_point:
            return {"status": "gap", "tool": "get_default_state", "message": "access_point is required."}
        stub, pb2 = self._stub_and_pb2()
        response = stub.GetDefaultState(pb2.GetDefaultStateRequest(access_point=access_point), timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "get_default_state", "access_point": access_point, "result": bool(response.result)}

    def set_state(self, access_point: str = "", directive: str = "STATE_DIRECTIVE_NEUTRAL", priority: str = "PRIORITY_USER", confirmation: str = "") -> dict[str, Any]:
        """Set a state directive on an access point. Approval-gated + per-call confirmation.

        Reversible: read get_current_state first, then restore by calling set_state with the prior
        directive (or directive=STATE_DIRECTIVE_NEUTRAL / priority=PRIORITY_DEFAULT_STATE to drop
        the override).

        Args:
            access_point (str): State-controllable access point.
            directive (str, optional): "STATE_DIRECTIVE_NEUTRAL" | "STATE_DIRECTIVE_OFF" | "STATE_DIRECTIVE_ON".
            priority (str, optional): "PRIORITY_DEFAULT_STATE" | "PRIORITY_DAEMON" | "PRIORITY_USER".
            confirmation (str): Must equal CONFIRM-state-control-set.

        Returns:
            (dict): {"status": "applied", "tool": "set_state", "result": bool} or a gate dict.
        """
        if not access_point:
            return {"status": "gap", "tool": "set_state", "message": "access_point is required."}
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        stub, pb2 = self._stub_and_pb2()
        try:
            directive_value = pb2.EStateDirective.Value(directive)
            priority_value = pb2.EPriority.Value(priority)
        except (KeyError, ValueError):
            return {"status": "gap", "tool": "set_state", "message": f"invalid directive/priority: {directive!r}/{priority!r}"}
        request = pb2.SetStateRequest(access_point=access_point, priority=priority_value, directive=directive_value)
        response = stub.SetState(request, timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "tool": "set_state", "access_point": access_point, "directive": directive, "priority": priority, "result": bool(response.result)}
