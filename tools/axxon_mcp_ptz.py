#!/usr/bin/env python3
"""PTZ / telemetry control tools for the Axxon One MCP server.

Wraps `axxonsoft.bl.ptz.TelemetryService` as bounded operator tools: discover telemetry
sources from the full config graph, acquire/keepalive/release a control session, read the
absolute position, drive move/zoom/focus/iris (continuous, relative, or absolute), and manage
presets. Telemetry sources are `*/DeviceIpint.N/TelemetryControl.M` components; cameras without a
telemetry endpoint return a structured gap rather than crashing.

Credentials are read only from the environment. Motion calls require an acquired session id.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig

MAX_SOURCES = 256
MAX_LIST_PAGE = 1000
DEFAULT_TIMEOUT = 20.0

# Telemetry move/zoom/focus/iris modes (TelemetryHelper.Capabilities flags). The server reads one
# mode per command; "continuous" is the safe default for joystick-style nudges.
MOVE_MODES = {"continuous", "relative", "absolute", "auto"}


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def public_config_summary(config: Any) -> dict[str, Any]:
    return {"host": "<redacted>", "tls_cn": getattr(config, "tls_cn", ""), "mode": "ptz-control"}


def _redact(value: Any, limit: int = 240) -> str:
    text = str(value)
    return text[:limit]


def _capabilities(client: Any, mode: str):
    """Build a TelemetryHelper.Capabilities with exactly the requested mode flag set."""
    helper = client.import_module("axxonsoft.bl.ptz.TelemetryHelper_pb2")
    return helper.Capabilities(
        is_continuous=(mode == "continuous"),
        is_relative=(mode == "relative"),
        is_absolute=(mode == "absolute"),
        is_auto=(mode == "auto"),
    )


@dataclass
class AxxonMcpPtz:
    """TelemetryService PTZ control tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def ptz_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "ptz-control"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.ptz_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.ptz_connect_axxon_profile("env")
        return self.client

    def _domain_stub(self, client: Any):
        return client.stub_from_proto("axxonsoft/bl/domain/Domain.proto", "DomainService")

    def _telemetry_stub(self, client: Any):
        return client.stub_from_proto("axxonsoft/bl/ptz/Telemetry.proto", "TelemetryService")

    def list_telemetry_sources(self, limit: int = 64) -> dict[str, Any]:
        """List PTZ telemetry endpoints (*/TelemetryControl.M) from the full config graph.

        Uses DomainService.ListComponents (not the filtered inventory), which is the only place
        TelemetryControl endpoints appear.
        """
        client = self.ensure_client()
        client.authenticate_grpc()
        domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
        domain = self._domain_stub(client)
        sources: list[str] = []
        request = domain_pb2.ListComponentsRequest(page_size=MAX_LIST_PAGE)
        for page in domain.ListComponents(request, timeout=client.config.timeout):
            for component in client.message_to_dict(page).get("items", []):
                ap = component.get("access_point", "")
                if "/TelemetryControl." in ap and ap not in sources:
                    sources.append(ap)
        sources.sort()
        if not sources:
            return {"status": "gap", "tool": "list_telemetry_sources", "count": 0, "sources": [],
                    "message": "No TelemetryControl endpoint on this stand; add a PTZ-capable device to control telemetry."}
        return {"status": "ok", "tool": "list_telemetry_sources", "count": len(sources), "sources": sources[: max(1, min(limit, MAX_SOURCES))]}

    def _resolve_source(self, client: Any, access_point: str) -> str | None:
        if "/TelemetryControl." in access_point:
            return access_point
        return None

    def acquire_session(self, access_point: str, host_name: str = "axxon-mcp") -> dict[str, Any]:
        """Acquire a telemetry control session for a PTZ source."""
        client = self.ensure_client()
        client.authenticate_grpc()
        if self._resolve_source(client, access_point) is None:
            return {"status": "gap", "tool": "acquire_session", "access_point": access_point,
                    "message": "access_point is not a TelemetryControl endpoint."}
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        response = stub.AcquireSessionId(tel.AcquireSessionRequest(access_point=access_point, host_name=host_name), timeout=client.config.timeout)
        body = client.message_to_dict(response)
        return {"status": "ok", "tool": "acquire_session", "access_point": access_point,
                "session_id": body.get("session_id"), "expiration_time": body.get("expiration_time"),
                "error_code": body.get("error_code", "NotError")}

    def session_available(self, access_point: str) -> dict[str, Any]:
        """Report whether a PTZ source currently has a free control session."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.IsSessionAvailable(tel.IsSessionAvailableRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "session_available", "access_point": access_point,
                "is_available": bool(body.get("is_available", False))}

    def keepalive_session(self, access_point: str, session_id: int) -> dict[str, Any]:
        """Extend a telemetry control session."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.KeepAlive(tel.SessionRequest(access_point=access_point, session_id=int(session_id)), timeout=client.config.timeout))
        return {"status": "ok", "tool": "keepalive_session", "access_point": access_point,
                "result": bool(body.get("result", False)), "expiration_time": body.get("expiration_time")}

    def release_session(self, access_point: str, session_id: int) -> dict[str, Any]:
        """Release a telemetry control session."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        stub.ReleaseSessionId(tel.SessionRequest(access_point=access_point, session_id=int(session_id)), timeout=client.config.timeout)
        return {"status": "ok", "tool": "release_session", "access_point": access_point, "session_id": int(session_id)}

    def get_position(self, access_point: str) -> dict[str, Any]:
        """Read the absolute pan/tilt/zoom position of a PTZ source."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetPositionInformation(tel.GetPositionInformationRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "get_position", "access_point": access_point,
                "absolute_position": body.get("absolute_position", {}), "error_code": body.get("error_code", "NotError")}

    def move(self, access_point: str, session_id: int, pan: float, tilt: float, mode: str = "continuous") -> dict[str, Any]:
        """Pan/tilt the camera. mode is continuous (speed), relative (step), or absolute."""
        if mode not in MOVE_MODES:
            return {"status": "refused", "tool": "move", "reason": "bad-mode", "message": f"mode must be one of {sorted(MOVE_MODES)}"}
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        stub.Move(tel.MoveRequest(access_point=access_point, session_id=int(session_id), mode=_capabilities(client, mode),
                                  val_pan=float(pan), val_tilt=float(tilt)), timeout=client.config.timeout)
        return {"status": "ok", "tool": "move", "access_point": access_point, "pan": float(pan), "tilt": float(tilt), "mode": mode}

    def _common(self, rpc_name: str, tool: str, access_point: str, session_id: int, value: float, mode: str) -> dict[str, Any]:
        if mode not in MOVE_MODES:
            return {"status": "refused", "tool": tool, "reason": "bad-mode", "message": f"mode must be one of {sorted(MOVE_MODES)}"}
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        request = tel.CommonRequest(access_point=access_point, session_id=int(session_id), mode=_capabilities(client, mode), value=float(value))
        getattr(stub, rpc_name)(request, timeout=client.config.timeout)
        return {"status": "ok", "tool": tool, "access_point": access_point, "value": float(value), "mode": mode}

    def zoom(self, access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Zoom the camera (continuous speed, relative step, or absolute)."""
        return self._common("Zoom", "zoom", access_point, session_id, value, mode)

    def focus(self, access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust focus (continuous speed, relative step, or absolute)."""
        return self._common("Focus", "focus", access_point, session_id, value, mode)

    def iris(self, access_point: str, session_id: int, value: float, mode: str = "continuous") -> dict[str, Any]:
        """Adjust iris (continuous speed, relative step, or absolute)."""
        return self._common("Iris", "iris", access_point, session_id, value, mode)

    def point_move(self, access_point: str, session_id: int, x: float, y: float) -> dict[str, Any]:
        """Center the camera on a normalized [0..1] image point (click-to-center). Needs a session."""
        if not access_point or "/TelemetryControl." not in access_point:
            return {"status": "refused", "tool": "point_move", "reason": "bad-access-point", "message": "access_point must be a TelemetryControl endpoint."}
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        prim = client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        stub = self._telemetry_stub(client)
        stub.PointMove(tel.PointMoveRequest(access_point=access_point, session_id=int(session_id), point=prim.Point(x=float(x), y=float(y))), timeout=client.config.timeout)
        return {"status": "ok", "tool": "point_move", "access_point": access_point, "x": float(x), "y": float(y)}

    def absolute_move(self, access_point: str, session_id: int, pan: int, tilt: int, zoom: int, mask: int = 7) -> dict[str, Any]:
        """Move to an absolute pan/tilt/zoom position. mask selects which axes apply (7 = all)."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        position = tel.AbsolutePosition(pan=int(pan), tilt=int(tilt), zoom=int(zoom), mask=int(mask))
        stub.AbsoluteMove(tel.AbsoluteMoveRequest(access_point=access_point, session_id=int(session_id), absolute_position=position), timeout=client.config.timeout)
        return {"status": "ok", "tool": "absolute_move", "access_point": access_point,
                "absolute_position": {"pan": int(pan), "tilt": int(tilt), "zoom": int(zoom), "mask": int(mask)}}

    def get_position_normalized(self, access_point: str) -> dict[str, Any]:
        """Read the normalized [0..1] pan/tilt/zoom position of a PTZ source."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetPositionInformationNormalized(tel.GetPositionInformationRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "get_position_normalized", "access_point": access_point,
                "absolute_position": body.get("absolute_position", {}), "error_code": body.get("error_code", "NotError")}

    def absolute_move_normalized(self, access_point: str, session_id: int, pan: float, tilt: float, zoom: float, mask: int = 7) -> dict[str, Any]:
        """Move to a normalized [0..1] absolute pan/tilt/zoom position. mask selects axes (7 = all)."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        position = tel.AbsolutePositionNormalized(pan=float(pan), tilt=float(tilt), zoom=float(zoom), mask=int(mask))
        stub.AbsoluteMoveNormalized(tel.AbsoluteMoveNormalizedRequest(access_point=access_point, session_id=int(session_id), absolute_position=position), timeout=client.config.timeout)
        return {"status": "ok", "tool": "absolute_move_normalized", "access_point": access_point,
                "absolute_position": {"pan": float(pan), "tilt": float(tilt), "zoom": float(zoom), "mask": int(mask)}}

    def save_preset(self, access_point: str, session_id: int, position: int, label: str = "") -> dict[str, Any]:
        """Save the current position as a preset via the bare SetPreset RPC (no response body)."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        stub.SetPreset(tel.SetPresetRequest(access_point=access_point, session_id=int(session_id), position=int(position), label=label), timeout=client.config.timeout)
        return {"status": "ok", "tool": "save_preset", "access_point": access_point, "position": int(position), "label": label}

    def configure_preset(self, access_point: str, position: int, label: str = "", pan: int = 0, tilt: int = 0, zoom: int = 0) -> dict[str, Any]:
        """Create or update a preset at a slot with an explicit absolute position (ConfigurePreset)."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        preset = tel.Preset(label=label, absolute_pan=int(pan), absolute_tilt=int(tilt), absolute_zoom=int(zoom))
        stub.ConfigurePreset(tel.ConfigurePresetRequest(access_point=access_point, position=int(position), preset=preset), timeout=client.config.timeout)
        return {"status": "ok", "tool": "configure_preset", "access_point": access_point, "position": int(position), "label": label}

    def get_tours(self, access_point: str) -> dict[str, Any]:
        """List the patrol tours configured on a PTZ source."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetTours(tel.GetToursRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "get_tours", "access_point": access_point,
                "tours": body.get("tours", []), "error_code": body.get("error_code", "NotError")}

    def get_tour_points(self, access_point: str, tour_name: str) -> dict[str, Any]:
        """List the preset points that make up a named patrol tour."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetTourPoints(tel.GetTourPointsRequest(access_point=access_point, tour_name=tour_name), timeout=client.config.timeout))
        return {"status": "ok", "tool": "get_tour_points", "access_point": access_point, "tour_name": tour_name,
                "preset_collection": body.get("preset_collection", {}), "error_code": body.get("error_code", "NotError")}

    def list_presets(self, access_point: str) -> dict[str, Any]:
        """List telemetry presets for a PTZ source."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetPresetsInfo(tel.GetPresetsInfoRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "list_presets", "access_point": access_point,
                "presets": body.get("preset_info", []), "error_code": body.get("error_code", "NotError")}

    def set_preset(self, access_point: str, session_id: int, position: int, label: str = "") -> dict[str, Any]:
        """Save the current position as a preset at the given slot."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.SetPreset2(tel.SetPresetRequest(access_point=access_point, session_id=int(session_id), position=int(position), label=label), timeout=client.config.timeout))
        return {"status": "ok", "tool": "set_preset", "access_point": access_point, "position": int(position), "label": label, "error_code": body.get("error_code", "NotError")}

    def go_preset(self, access_point: str, session_id: int, position: int, speed: float = 1.0) -> dict[str, Any]:
        """Move the camera to a saved preset."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        stub.GoPreset(tel.GoPresetRequest(access_point=access_point, session_id=int(session_id), position=int(position), speed=float(speed)), timeout=client.config.timeout)
        return {"status": "ok", "tool": "go_preset", "access_point": access_point, "position": int(position), "speed": float(speed)}

    def remove_preset(self, access_point: str, session_id: int, position: int) -> dict[str, Any]:
        """Delete a saved preset."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        stub.RemovePreset(tel.RemovePresetRequest(access_point=access_point, session_id=int(session_id), position=int(position)), timeout=client.config.timeout)
        return {"status": "ok", "tool": "remove_preset", "access_point": access_point, "position": int(position)}

    def auxiliary_operations(self, access_point: str) -> dict[str, Any]:
        """List auxiliary operations (wiper, light, etc.) a PTZ source supports."""
        client = self.ensure_client()
        client.authenticate_grpc()
        tel = client.import_module("axxonsoft.bl.ptz.Telemetry_pb2")
        stub = self._telemetry_stub(client)
        body = client.message_to_dict(stub.GetAuxiliaryOperations(tel.GetAuxiliaryOperationsRequest(access_point=access_point), timeout=client.config.timeout))
        return {"status": "ok", "tool": "auxiliary_operations", "access_point": access_point, "operations": body.get("operations", [])}
