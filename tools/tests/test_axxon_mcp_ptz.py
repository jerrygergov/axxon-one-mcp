"""Phase 8 tests: AxxonMcpPtz (TelemetryService PTZ control)."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    tls_cn = "Server"
    timeout = 7.0


class FakeMsg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _telemetry_pb():
    mod = types.SimpleNamespace()
    for name in (
        "AcquireSessionRequest", "SessionRequest", "IsSessionAvailableRequest",
        "GetPositionInformationRequest", "MoveRequest", "CommonRequest",
        "AbsolutePosition", "AbsoluteMoveRequest", "GetPresetsInfoRequest",
        "SetPresetRequest", "GoPresetRequest", "RemovePresetRequest",
        "GetAuxiliaryOperationsRequest",
        "AbsolutePositionNormalized", "AbsoluteMoveNormalizedRequest",
        "ConfigurePresetRequest", "Preset", "GetToursRequest", "GetTourPointsRequest",
    ):
        setattr(mod, name, (lambda **kw: FakeMsg(**kw)))
    return mod


def _helper_pb():
    return types.SimpleNamespace(Capabilities=lambda **kw: FakeMsg(**kw))


def _domain_pb():
    return types.SimpleNamespace(ListComponentsRequest=lambda **kw: FakeMsg(**kw))


class FakeTelemetryStub:
    def __init__(self):
        self.calls = []

    def AcquireSessionId(self, request, timeout=None):
        self.calls.append(("AcquireSessionId", request))
        return FakeMsg(session_id=1, expiration_time="2026-06-05T08:55:14Z", error_code="NotError")

    def IsSessionAvailable(self, request, timeout=None):
        return FakeMsg(is_available=True)

    def KeepAlive(self, request, timeout=None):
        return FakeMsg(result=True, expiration_time="2026-06-05T09:00:00Z")

    def ReleaseSessionId(self, request, timeout=None):
        self.calls.append(("ReleaseSessionId", request))
        return FakeMsg()

    def GetPositionInformation(self, request, timeout=None):
        return FakeMsg(absolute_position={"pan": 675, "tilt": 279, "zoom": 10, "mask": 7}, error_code="NotError")

    def Move(self, request, timeout=None):
        self.calls.append(("Move", request))
        return FakeMsg()

    def Zoom(self, request, timeout=None):
        self.calls.append(("Zoom", request))
        return FakeMsg()

    def Focus(self, request, timeout=None):
        self.calls.append(("Focus", request))
        return FakeMsg()

    def Iris(self, request, timeout=None):
        self.calls.append(("Iris", request))
        return FakeMsg()

    def AbsoluteMove(self, request, timeout=None):
        self.calls.append(("AbsoluteMove", request))
        return FakeMsg()

    def GetPositionInformationNormalized(self, request, timeout=None):
        return FakeMsg(absolute_position={"pan": 0.5, "tilt": 0.5, "zoom": 0.1, "mask": 7}, error_code="NotError")

    def AbsoluteMoveNormalized(self, request, timeout=None):
        self.calls.append(("AbsoluteMoveNormalized", request))
        return FakeMsg()

    def SetPreset(self, request, timeout=None):
        self.calls.append(("SetPreset", request))
        return FakeMsg()

    def ConfigurePreset(self, request, timeout=None):
        self.calls.append(("ConfigurePreset", request))
        return FakeMsg()

    def GetTours(self, request, timeout=None):
        return FakeMsg(tours=[{"name": "Lobby", "state": "EIdle"}], error_code="NotError")

    def GetTourPoints(self, request, timeout=None):
        return FakeMsg(preset_collection={"presets": []}, error_code="NotError")

    def GetPresetsInfo(self, request, timeout=None):
        return FakeMsg(preset_info=[{"position": 0, "label": "Home"}], error_code="NotError")

    def SetPreset2(self, request, timeout=None):
        self.calls.append(("SetPreset2", request))
        return FakeMsg(error_code="NotError")

    def GoPreset(self, request, timeout=None):
        self.calls.append(("GoPreset", request))
        return FakeMsg()

    def RemovePreset(self, request, timeout=None):
        self.calls.append(("RemovePreset", request))
        return FakeMsg()

    def GetAuxiliaryOperations(self, request, timeout=None):
        return FakeMsg(operations=["wiper", "light"])


class FakeDomainStub:
    def __init__(self, access_points):
        self.access_points = access_points

    def ListComponents(self, request, timeout=None):
        yield FakeMsg()  # placeholder; message_to_dict provides items

    # message_to_dict is patched to return items for the placeholder page


class FakeClient:
    config = FakeConfig()

    def __init__(self, telemetry_endpoints):
        self.telemetry_endpoints = telemetry_endpoints
        self.telemetry_stub = FakeTelemetryStub()
        self.domain_stub = FakeDomainStub(telemetry_endpoints)

    def authenticate_grpc(self):
        pass

    def import_module(self, name):
        if name.endswith("Telemetry_pb2"):
            return _telemetry_pb()
        if name.endswith("TelemetryHelper_pb2"):
            return _helper_pb()
        if name.endswith("Domain_pb2"):
            return _domain_pb()
        raise AssertionError(f"unexpected import {name}")

    def stub_from_proto(self, proto, service):
        if service == "TelemetryService":
            return self.telemetry_stub
        if service == "DomainService":
            return self.domain_stub
        raise AssertionError(service)

    def message_to_dict(self, message):
        # ListComponents page -> the configured telemetry endpoints; everything else -> its __dict__
        if isinstance(message, FakeMsg) and not message.__dict__:
            return {"items": [{"access_point": ap} for ap in self.telemetry_endpoints]}
        return dict(getattr(message, "__dict__", {}))


def _ptz(endpoints):
    module = importlib.import_module("axxon_mcp_ptz")
    ptz = module.AxxonMcpPtz(client_factory=lambda _c: FakeClient(endpoints), config_factory=lambda: FakeConfig())
    ptz.connect_axxon_profile("env")
    return ptz


PTZ_AP = "hosts/Server/DeviceIpint.53/TelemetryControl.0"


class AxxonMcpPtzTests(unittest.TestCase):
    def test_list_telemetry_sources_found(self) -> None:
        result = _ptz([PTZ_AP, "hosts/Server/DeviceIpint.53/TelemetryControl.1"]).list_telemetry_sources()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 2)
        self.assertIn(PTZ_AP, result["sources"])

    def test_list_telemetry_sources_gap_when_none(self) -> None:
        result = _ptz([]).list_telemetry_sources()
        self.assertEqual(result["status"], "gap")
        self.assertEqual(result["count"], 0)
        self.assertIn("PTZ", result["message"])

    def test_session_lifecycle_and_position(self) -> None:
        ptz = _ptz([PTZ_AP])
        acq = ptz.acquire_session(PTZ_AP)
        self.assertEqual(acq["status"], "ok")
        self.assertEqual(acq["session_id"], 1)
        avail = ptz.session_available(PTZ_AP)
        self.assertTrue(avail["is_available"])
        ka = ptz.keepalive_session(PTZ_AP, 1)
        self.assertTrue(ka["result"])
        pos = ptz.get_position(PTZ_AP)
        self.assertEqual(pos["absolute_position"]["pan"], 675)
        rel = ptz.release_session(PTZ_AP, 1)
        self.assertEqual(rel["status"], "ok")

    def test_acquire_refuses_non_telemetry_endpoint(self) -> None:
        result = _ptz([PTZ_AP]).acquire_session("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(result["status"], "gap")
        self.assertIn("TelemetryControl", result["message"])

    def test_move_zoom_focus_iris_and_absolute(self) -> None:
        ptz = _ptz([PTZ_AP])
        self.assertEqual(ptz.move(PTZ_AP, 1, 0.5, -0.5)["status"], "ok")
        self.assertEqual(ptz.zoom(PTZ_AP, 1, 0.3)["status"], "ok")
        self.assertEqual(ptz.focus(PTZ_AP, 1, 0.1)["status"], "ok")
        self.assertEqual(ptz.iris(PTZ_AP, 1, 0.2)["status"], "ok")
        absmove = ptz.absolute_move(PTZ_AP, 1, 100, 50, 5)
        self.assertEqual(absmove["absolute_position"]["pan"], 100)

    def test_move_bad_mode_refused(self) -> None:
        result = _ptz([PTZ_AP]).move(PTZ_AP, 1, 0.5, 0.5, mode="warp")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "bad-mode")

    def test_preset_round_trip(self) -> None:
        ptz = _ptz([PTZ_AP])
        self.assertEqual(ptz.set_preset(PTZ_AP, 1, 3, "Gate")["status"], "ok")
        listed = ptz.list_presets(PTZ_AP)
        self.assertEqual(listed["presets"][0]["label"], "Home")
        self.assertEqual(ptz.go_preset(PTZ_AP, 1, 3)["status"], "ok")
        self.assertEqual(ptz.remove_preset(PTZ_AP, 1, 3)["status"], "ok")

    def test_auxiliary_operations(self) -> None:
        result = _ptz([PTZ_AP]).auxiliary_operations(PTZ_AP)
        self.assertEqual(result["operations"], ["wiper", "light"])

    def test_zoom_absolute_mode_emits_single_zoom_with_absolute_flag(self) -> None:
        ptz = _ptz([PTZ_AP])
        result = ptz.zoom(PTZ_AP, 9, 0.4, mode="absolute")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "absolute")
        stub = ptz.client.telemetry_stub
        zoom_calls = [req for name, req in stub.calls if name == "Zoom"]
        self.assertEqual(len(zoom_calls), 1)
        request = zoom_calls[0]
        self.assertEqual(request.access_point, PTZ_AP)
        self.assertEqual(request.session_id, 9)
        self.assertEqual(request.value, 0.4)
        self.assertTrue(request.mode.is_absolute)
        self.assertFalse(request.mode.is_continuous)

    def test_zoom_reversible_capture_restore_sequence(self) -> None:
        ptz = _ptz([PTZ_AP])
        captured = ptz.get_position(PTZ_AP)["absolute_position"]
        self.assertEqual(ptz.zoom(PTZ_AP, 9, 0.4, mode="absolute")["status"], "ok")
        restore = ptz.absolute_move(
            PTZ_AP, 9, captured["pan"], captured["tilt"], captured["zoom"], captured["mask"]
        )
        self.assertEqual(restore["status"], "ok")
        self.assertEqual(restore["absolute_position"]["pan"], captured["pan"])
        self.assertEqual(restore["absolute_position"]["zoom"], captured["zoom"])
        names = [name for name, _ in ptz.client.telemetry_stub.calls]
        self.assertLess(names.index("Zoom"), names.index("AbsoluteMove"))


class PtzNormalizedAndToursTests(unittest.TestCase):
    def test_get_position_normalized(self) -> None:
        out = _ptz([PTZ_AP]).get_position_normalized(PTZ_AP)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "get_position_normalized")
        self.assertEqual(out["absolute_position"]["pan"], 0.5)

    def test_absolute_move_normalized_emits_rpc(self) -> None:
        ptz = _ptz([PTZ_AP])
        out = ptz.absolute_move_normalized(PTZ_AP, 9, 0.25, 0.5, 0.75, 7)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["absolute_position"]["zoom"], 0.75)
        self.assertIn("AbsoluteMoveNormalized", [name for name, _ in ptz.client.telemetry_stub.calls])

    def test_save_preset_uses_bare_setpreset(self) -> None:
        ptz = _ptz([PTZ_AP])
        out = ptz.save_preset(PTZ_AP, 9, 5, "Door")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "save_preset")
        self.assertIn("SetPreset", [name for name, _ in ptz.client.telemetry_stub.calls])

    def test_configure_preset_emits_rpc(self) -> None:
        ptz = _ptz([PTZ_AP])
        out = ptz.configure_preset(PTZ_AP, 3, "Gate", 100, 50, 5)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["position"], 3)
        self.assertIn("ConfigurePreset", [name for name, _ in ptz.client.telemetry_stub.calls])

    def test_get_tours_shape(self) -> None:
        out = _ptz([PTZ_AP]).get_tours(PTZ_AP)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tours"][0]["name"], "Lobby")

    def test_get_tour_points_shape(self) -> None:
        out = _ptz([PTZ_AP]).get_tour_points(PTZ_AP, "Lobby")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tour_name"], "Lobby")
        self.assertIn("preset_collection", out)


if __name__ == "__main__":
    unittest.main()
