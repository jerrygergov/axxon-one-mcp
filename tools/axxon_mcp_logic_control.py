#!/usr/bin/env python3
"""LogicService operator-control tools for Axxon One MCP (Phase 16, 46).

Operator mutations plus read helpers:
- list_launchable_macros: ListMacros, classify manual vs autorule macros.
- launch_macro: LaunchMacro by id.
- change_arm_state: ChangeArmState for a bounded, auto-reverting window.
- change_config: ChangeConfig, overriding only the fields the caller passes
  (round-trippable against GetConfig).
- change_counters: ChangeCounters, add a counter by guid+name or remove by guid.
- counter_action: CounterAction START/STOP/CLEANUP on a counter guid.

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
MACRO_PB2 = "axxonsoft.bl.logic.Macro_pb2"
EVENTS_PB2 = "axxonsoft.bl.events.Events_pb2"

ARM_TIMEOUT_CAP_S = 300
ARM_STATES = {"disarm": "CS_Disarm", "arm": "CS_Arm", "arm_private": "CS_ArmPrivate"}

CONFIG_FIELDS = ("user_alert_ttl", "rule_alert_ttl", "conditional_ttl", "max_event_age", "event_cleanup_period")
COUNTER_OPERATIONS = {"start": "START", "stop": "STOP", "cleanup": "CLEANUP", "start_with_cleanup": "START_WITH_CLEANUP"}

LOGIC_CONTROL_TOOL_NAMES = (
    "logic_control_connect_axxon_profile",
    "list_launchable_macros",
    "launch_macro",
    "change_arm_state",
    "change_config",
    "change_counters",
    "counter_action",
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

    def change_config(self, overrides: dict[str, int] | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        unknown = [k for k in (overrides or {}) if k not in CONFIG_FIELDS]
        if not overrides or unknown:
            return {"status": "error", "message": f"overrides must set one or more of {list(CONFIG_FIELDS)}", "unknown": unknown}
        stub, pb2 = self._stub_and_pb2()
        timeout = self.ensure_client().config.timeout
        current = stub.GetConfig(pb2.GetConfigRequest(), timeout=timeout)
        applied = {f: int(overrides.get(f, getattr(current, f).seconds)) for f in CONFIG_FIELDS}
        request = pb2.ChangeConfigRequest(**{f: pb2.Duration(seconds=applied[f]) for f in CONFIG_FIELDS})
        stub.ChangeConfig(request, timeout=timeout)
        previous = {f: getattr(current, f).seconds for f in overrides}
        return {"status": "applied", "applied": applied, "previous": previous, "reversible": True}

    def change_counters(self, add: dict[str, str] | None = None, remove_guid: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        add = add or {}
        if bool(add) == bool(str(remove_guid or "").strip()):
            return {"status": "error", "message": "provide exactly one of add (guid+name) or remove_guid"}
        if add and not (str(add.get("guid", "")).strip() and str(add.get("name", "")).strip()):
            return {"status": "error", "message": "add requires both guid and name"}
        stub, pb2 = self._stub_and_pb2()
        if add:
            counter = pb2.CounterConfig(guid=add["guid"], name=add["name"], host_id=add.get("host_id", ""), autostart=bool(add.get("autostart", False)))
            stub.ChangeCounters(pb2.ChangeCountersRequest(modified_counters=[counter]), timeout=self.ensure_client().config.timeout)
            return {"status": "added", "guid": add["guid"], "name": add["name"]}
        stub.ChangeCounters(pb2.ChangeCountersRequest(removed_counters=[remove_guid]), timeout=self.ensure_client().config.timeout)
        return {"status": "removed", "guid": remove_guid}

    def counter_action(self, counter: str = "", operation: str = "start", confirmation: str = "") -> dict[str, Any]:
        gated = self._gate(confirmation)
        if gated is not None:
            return gated
        if not str(counter or "").strip():
            return {"status": "error", "message": "counter (guid) is required"}
        enum_name = COUNTER_OPERATIONS.get(str(operation).lower())
        if enum_name is None:
            return {"status": "error", "message": f"operation must be one of {list(COUNTER_OPERATIONS)}, got {operation!r}"}
        stub, pb2 = self._stub_and_pb2()
        macro = self.ensure_client().import_module(MACRO_PB2)
        action = macro.CounterAction(counter=counter, operation=getattr(macro.CounterAction, enum_name))
        stub.CounterAction(pb2.CounterActionRequest(action=action), timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "counter": counter, "operation": operation}
