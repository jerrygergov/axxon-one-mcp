from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_videowall as module


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


class _VData:
    def __init__(self, data=b""):
        self.data = data


class _Wall:
    def __init__(self, wall_id, name="", display_name="", seq_number=0, host_name=""):
        self.wall_id, self.name, self.display_name, self.seq_number, self.host_name = wall_id, name, display_name, seq_number, host_name


class _ListResp:
    def __init__(self, walls):
        self.walls = walls
        self.unreachable_objects = []


class _RegReq:
    def __init__(self, **kw): self.__dict__.update(kw)


class _RegResp:
    def __init__(self, cookie="cookie-secret", wall_id="W1", seq_number=0):
        self.cookie, self.wall_id, self.seq_number = cookie, wall_id, seq_number


class _ChangeResp:
    def __init__(self, new_seq_number=1): self.new_seq_number = new_seq_number


class _FakePb2:
    ListWallsRequest = staticmethod(lambda **k: object())
    VideowallData = _VData
    ControlData = _VData
    RegisterWallRequest = _RegReq

    class ChangeWallRequest:
        def __init__(self, **kw): self.__dict__.update(kw)

    class SetControlDataRequest:
        def __init__(self, **kw): self.__dict__.update(kw)

    class UnregisterWallRequest:
        def __init__(self, **kw): self.__dict__.update(kw)


class _FakeStub:
    def __init__(self, recorder, walls):
        self._rec = recorder
        self._walls = walls

    def ListWalls(self, request, timeout=None):
        self._rec.append(("ListWalls", request, timeout))
        return iter([_ListResp(self._walls)])

    def RegisterWall(self, request, timeout=None):
        self._rec.append(("RegisterWall", request, timeout))
        return _RegResp()

    def ChangeWall(self, request, timeout=None):
        self._rec.append(("ChangeWall", request, timeout))
        return _ChangeResp(1)

    def SetControlData(self, request, timeout=None):
        self._rec.append(("SetControlData", request, timeout))
        return _ChangeResp(2)

    def UnregisterWall(self, request, timeout=None):
        self._rec.append(("UnregisterWall", request, timeout))
        return object()


class FakeClient:
    def __init__(self, config, walls=None):
        self.config = config
        self.calls: list = []
        self._walls = walls if walls is not None else [_Wall("W0", "existing", "Existing", 3)]

    def authenticate_grpc(self): return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "VideowallService"
        return _FakeStub(self.calls, self._walls)

    def import_module(self, name):
        return _FakePb2()


def _vw(walls=None, **overrides):
    inst = module.AxxonMcpVideowall(
        client_factory=lambda config: FakeClient(config, walls),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.videowall_connect_axxon_profile("env")
    return inst


class GatingTests(unittest.TestCase):
    def test_register_disabled_without_approval(self) -> None:
        inst = _vw(enabled=False)
        out = inst.register_wall("w", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_register_rejects_bad_confirmation(self) -> None:
        inst = _vw(enabled=True)
        out = inst.register_wall("w", confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])


class ListWallsTests(unittest.TestCase):
    def test_list_is_ungated(self) -> None:
        inst = _vw(enabled=False)
        out = inst.list_walls()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["walls"][0]["wall_id"], "W0")


class RegisterTests(unittest.TestCase):
    def test_empty_name_no_wire(self) -> None:
        inst = _vw(enabled=True)
        out = inst.register_wall("", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_register_returns_cookie_present_not_raw(self) -> None:
        inst = _vw(enabled=True)
        out = inst.register_wall("phase46", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(out["status"], "registered")
        self.assertTrue(out["cookie_present"])
        self.assertNotIn("cookie", out)
        self.assertEqual(out["wall_id"], "W1")
        # cookie tracked internally for later chaining
        self.assertEqual(inst._cookies["W1"], "cookie-secret")


class ChangeAndUnregisterTests(unittest.TestCase):
    def test_change_unknown_wall_no_wire(self) -> None:
        inst = _vw(enabled=True)
        out = inst.change_wall(wall_id="nope", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_set_control_unknown_wall_no_wire(self) -> None:
        inst = _vw(enabled=True)
        out = inst.set_control_data(wall_id="", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_full_reversible_lifecycle(self) -> None:
        inst = _vw(enabled=True)
        reg = inst.register_wall("phase46", confirmation=module.VIDEOWALL_CONFIRMATION)
        wid = reg["wall_id"]
        ch = inst.change_wall(wall_id=wid, seq_number=0, data=b"x", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(ch["new_seq_number"], 1)
        sc = inst.set_control_data(wall_id=wid, seq_number=1, data=b"c", confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(sc["new_seq_number"], 2)
        unr = inst.unregister_wall(wall_id=wid, confirmation=module.VIDEOWALL_CONFIRMATION)
        self.assertEqual(unr["status"], "unregistered")
        self.assertNotIn(wid, inst._cookies)
        names = [c[0] for c in inst.client.calls]
        self.assertEqual(names, ["RegisterWall", "ChangeWall", "SetControlData", "UnregisterWall"])


class NoSecretLeakTests(unittest.TestCase):
    def test_no_config_password_in_outputs(self) -> None:
        inst = _vw(enabled=True)
        outs = [
            inst.videowall_connect_axxon_profile("env"),
            inst.list_walls(),
            inst.register_wall("w", confirmation=module.VIDEOWALL_CONFIRMATION),
        ]
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", repr(outs))


if __name__ == "__main__":
    unittest.main()
