#!/usr/bin/env python3
"""Cross-service read + reversible-settings tools for Axxon One MCP (Phase 43).

Bundles serviceable methods from four small services:
- DynamicParametersService: acquire_dynamic_parameters, acquire_device_additional_data (reads)
- ArchiveVolumeService: probe_volume (read/probe)
- NodeNotifier: ping_node (read)
- GenericSettingsService: get_generic_settings (read) + gated save_generic_settings /
  remove_generic_settings (reversible)

The two settings writes are approval-gated (`AXXON_MISC_WRITE_APPROVE=1`) plus a per-call
confirmation token, mirroring the layout-manager idiom.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

MISC_WRITE_APPROVE_ENV = "AXXON_MISC_WRITE_APPROVE"
MISC_WRITE_CONFIRMATION = "CONFIRM-misc-write"

DYNPARAM_PROTO = "axxonsoft/bl/config/DynamicParametersService.proto"
DYNPARAM_PB2 = "axxonsoft.bl.config.DynamicParametersService_pb2"
VOLUME_PROTO = "axxonsoft/bl/archive/ArchiveVolumeService.proto"
VOLUME_PB2 = "axxonsoft.bl.archive.ArchiveVolumeService_pb2"
NOTIFY_PROTO = "axxonsoft/bl/events/Notification.proto"
NOTIFY_PB2 = "axxonsoft.bl.events.Notification_pb2"
SETTINGS_PROTO = "axxonsoft/bl/settings/generic/GenericSettings.proto"
SETTINGS_PB2 = "axxonsoft.bl.settings.generic.GenericSettings_pb2"
SETTINGS_INFO_PB2 = "axxonsoft.bl.settings.generic.SettingsInfo_pb2"
SETTINGS_MSG_PB2 = "axxonsoft.bl.settings.generic.Settings_pb2"

MISC_READS_TOOL_NAMES = (
    "misc_reads_connect_axxon_profile",
    "acquire_dynamic_parameters",
    "acquire_device_additional_data",
    "probe_volume",
    "ping_node",
    "get_generic_settings",
    "save_generic_settings",
    "remove_generic_settings",
)

SETTINGS_SCOPE_GLOBAL = 1


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(MISC_WRITE_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpMiscReads:
    """Phase 43 cross-service read tools + gated reversible generic-settings writes."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def misc_reads_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": MISC_WRITE_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.misc_reads_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.misc_reads_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self, proto: str, service: str, pb2_name: str) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(proto, service), client.import_module(pb2_name)

    def _timeout(self) -> Any:
        return self.ensure_client().config.timeout

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {MISC_WRITE_APPROVE_ENV}=1 to enable generic-settings writes.", "approval_env": MISC_WRITE_APPROVE_ENV}
        if confirmation != MISC_WRITE_CONFIRMATION:
            return {"status": "gap", "message": f"generic-settings writes require confirmation={MISC_WRITE_CONFIRMATION}"}
        return None

    def _acquire(self, tool: str, rpc: str, request_name: str, uid: str) -> dict[str, Any]:
        if not uid:
            return {"status": "error", "tool": tool, "message": "provide a unit uid"}
        stub, pb2 = self._stub_and_pb2(DYNPARAM_PROTO, "DynamicParametersService", DYNPARAM_PB2)
        response = getattr(stub, rpc)(getattr(pb2, request_name)(uid=uid), timeout=self._timeout())
        return {"status": "ok", "tool": tool, "result": int(response.status), "property_count": len(response.properties)}

    def acquire_dynamic_parameters(self, uid: str = "") -> dict[str, Any]:
        return self._acquire("acquire_dynamic_parameters", "AcquireDynamicParameters", "AcquireDynamicParametersRequest", uid)

    def acquire_device_additional_data(self, uid: str = "") -> dict[str, Any]:
        return self._acquire("acquire_device_additional_data", "AcquireDeviceAdditionalData", "AcquireDeviceAdditionalDataRequest", uid)

    def probe_volume(self, volume_type: str = "", node_name: str = "Server", connection_params: dict[str, str] | None = None) -> dict[str, Any]:
        if not volume_type:
            return {"status": "error", "tool": "probe_volume", "message": "provide a volume_type"}
        stub, pb2 = self._stub_and_pb2(VOLUME_PROTO, "ArchiveVolumeService", VOLUME_PB2)
        request = pb2.ProbeVolumeRequest(volume_type=volume_type, node_name=node_name)
        for key, value in (connection_params or {}).items():
            request.connection_params[key] = value
        response = stub.ProbeVolume(request, timeout=self._timeout())
        code = int(response.status_code)
        return {"status": "ok", "tool": "probe_volume", "status_code": code, "status_name": pb2.ProbeVolumeResponse.EProbeResultCode.Name(code), "error_details": response.error_details}

    def ping_node(self, timeout_ms: int = 1000) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2(NOTIFY_PROTO, "NodeNotifier", NOTIFY_PB2)
        responses = 0
        for _ in stub.Ping(pb2.PingRequest(timeoutMs=int(timeout_ms)), timeout=self._timeout()):
            responses += 1
            break
        return {"status": "ok", "tool": "ping_node", "responses": responses}

    def get_generic_settings(self, context: str = "") -> dict[str, Any]:
        if not context:
            return {"status": "error", "tool": "get_generic_settings", "message": "provide a settings context (GUID)"}
        stub, pb2 = self._stub_and_pb2(SETTINGS_PROTO, "GenericSettingsService", SETTINGS_PB2)
        response = stub.GetSettings(pb2.GetSettingsRequest(context=context, scope=SETTINGS_SCOPE_GLOBAL), timeout=self._timeout())
        return {"status": "ok", "tool": "get_generic_settings", "context": context, "value_count": len(response.settings.values), "revision": response.settings.info.revision}

    def save_generic_settings(self, context: str = "", values: dict[str, str] | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "save_generic_settings", **gated}
        if not context:
            return {"status": "error", "tool": "save_generic_settings", "message": "provide a settings context (GUID)"}
        stub, pb2 = self._stub_and_pb2(SETTINGS_PROTO, "GenericSettingsService", SETTINGS_PB2)
        settings_pb2 = self.ensure_client().import_module(SETTINGS_MSG_PB2)
        settings = settings_pb2.Settings()
        settings.info.context = context
        settings.values.update(values or {})
        response = stub.SaveSettings(pb2.SaveSettingsRequest(settings=settings, scope=SETTINGS_SCOPE_GLOBAL), timeout=self._timeout())
        code = int(response.result)
        return {"status": "applied", "tool": "save_generic_settings", "result": code, "result_name": pb2.EModificationResult.Name(code), "revision": response.updated.revision}

    def remove_generic_settings(self, context: str = "", revision: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "remove_generic_settings", **gated}
        if not context or not revision:
            return {"status": "error", "tool": "remove_generic_settings", "message": "provide a context and its current revision"}
        stub, pb2 = self._stub_and_pb2(SETTINGS_PROTO, "GenericSettingsService", SETTINGS_PB2)
        info_pb2 = self.ensure_client().import_module(SETTINGS_INFO_PB2)
        to_remove = info_pb2.SettingsInfo(context=context, revision=revision)
        stub.RemoveSettings(pb2.RemoveSettingsRequest(to_remove=to_remove, scope=SETTINGS_SCOPE_GLOBAL), timeout=self._timeout())
        return {"status": "applied", "tool": "remove_generic_settings", "context": context}
