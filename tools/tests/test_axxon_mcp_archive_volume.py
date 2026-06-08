from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_archive_volume as module


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_PASSWORD_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _VolState:
    def __init__(self, state=1, used=10, cap=100):
        self.state = state
        self.used_bytes = used
        self.capacity_bytes = cap


class _VolStatesResp:
    def __init__(self):
        self.volumes_state = {"vol-1": _VolState()}


class _EStatusCode:
    @staticmethod
    def Name(code):
        return {0: "DONE", 1: "OPERATION_IN_PROGRESS"}.get(code, str(code))


class _ResizeResp:
    EStatusCode = _EStatusCode

    def __init__(self, code=0):
        self.status_code = code


class _GetVolReq:
    def __init__(self, access_point=""):
        self.access_point = access_point


class _ResizeReq:
    def __init__(self, access_point="", volume_id="", new_size=0):
        self.access_point = access_point
        self.volume_id = volume_id
        self.new_size = new_size


class _Pb2:
    GetVolumesStateRequest = _GetVolReq
    ResizeRequest = _ResizeReq
    ResizeResponse = _ResizeResp


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def GetVolumesState(self, request, timeout=None):
        self._rec.append(("GetVolumesState", request.access_point))
        return _VolStatesResp()

    def Resize(self, request, timeout=None):
        self._rec.append(("Resize", request.volume_id, request.new_size))
        return _ResizeResp(0)


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpArchiveVolume(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.archive_volume_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_list_volume_states_ok(self) -> None:
        out = _inst().list_volume_states(access_point="hosts/Server/MultimediaStorage.X/MultimediaStorage")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["volume_count"], 1)
        self.assertEqual(out["volumes"][0]["volume_id"], "vol-1")
        self.assertEqual(out["volumes"][0]["capacity_bytes"], 100)

    def test_list_volume_states_empty_ap_no_wire(self) -> None:
        inst = _inst()
        out = inst.list_volume_states(access_point="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.resize_volume(access_point="ap", volume_id="vol-1", new_size=100, confirmation=module.ARCHIVE_VOLUME_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.resize_volume(access_point="ap", volume_id="vol-1", new_size=100, confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_missing_fields_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.resize_volume(access_point="ap", volume_id="", new_size=100, confirmation=module.ARCHIVE_VOLUME_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_zero_size_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.resize_volume(access_point="ap", volume_id="vol-1", new_size=0, confirmation=module.ARCHIVE_VOLUME_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_resize_applied_done(self) -> None:
        inst = _inst(enabled=True)
        out = inst.resize_volume(access_point="ap", volume_id="vol-1", new_size=100, confirmation=module.ARCHIVE_VOLUME_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["status_code"], 0)
        self.assertEqual(out["status_name"], "DONE")
        self.assertEqual(inst.client.calls[0][0], "Resize")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.resize_volume(access_point="ap", volume_id="vol-1", new_size=100, confirmation=module.ARCHIVE_VOLUME_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
