from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_logic_control as module


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


class _ArmReq:
    def __init__(self, **kw):
        self.camera_ap = kw.get("camera_ap", "")
        self.state = kw.get("state", 0)
        self.timeout = kw.get("timeout")


class _MacroReq:
    def __init__(self, **kw):
        self.macro_id = kw.get("macro_id", "")


class _ListReq:
    def __init__(self, **kw):
        pass


class _FakePb2:
    # ECameraArmState lives on events pb2 in reality; the module resolves it via
    # an events import, so the fake provides both pb2s through import_module.
    def __init__(self):
        self.ChangeArmStateRequest = _ArmReq
        self.LaunchMacroRequest = _MacroReq
        self.ListMacrosRequest = _ListReq


class _FakeEventsPb2:
    class CameraArmStateEvent:
        CS_Disarm, CS_Arm, CS_ArmPrivate = 0, 1, 2


class _FakeStub:
    def __init__(self, recorder, macros):
        self._rec = recorder
        self._macros = macros

    def LaunchMacro(self, request, timeout=None):
        self._rec.append(("LaunchMacro", request, timeout))
        return object()

    def ChangeArmState(self, request, timeout=None):
        self._rec.append(("ChangeArmState", request, timeout))
        return object()

    def ListMacros(self, request, timeout=None):
        self._rec.append(("ListMacros", request, timeout))
        return self._macros


class FakeLogicClient:
    def __init__(self, config, macros=None):
        self.config = config
        self.calls: list = []
        self._macros = macros if macros is not None else {
            "items": [
                {"guid": "m-manual", "name": "Fire", "mode": {"enabled": True, "common": {}}},
                {"guid": "m-auto", "name": "Cam Motion", "mode": {"enabled": True, "autorule": {"zone_ap": "z"}}},
            ]
        }

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "LogicService"
        return _FakeStub(self.calls, object())

    def import_module(self, name):
        return _FakeEventsPb2() if name.endswith("Events_pb2") else _FakePb2()

    def message_to_dict(self, msg):
        return self._macros


def _ctl(macros=None, **overrides):
    inst = module.AxxonMcpLogicControl(
        client_factory=lambda config: FakeLogicClient(config, macros),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.logic_control_connect_axxon_profile("env")
    return inst


class GatingTests(unittest.TestCase):
    def test_launch_disabled_without_approval(self) -> None:
        inst = _ctl(enabled=False)
        out = inst.launch_macro("m-manual", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_launch_rejects_bad_confirmation(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.launch_macro("m-manual", "WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_arm_disabled_without_approval(self) -> None:
        inst = _ctl(enabled=False)
        out = inst.change_arm_state("cam", "arm", 5, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")


class ListMacrosTests(unittest.TestCase):
    def test_classifies_launchable(self) -> None:
        inst = _ctl()
        out = inst.list_launchable_macros()
        self.assertEqual(out["status"], "ok")
        by_id = {m["id"]: m for m in out["macros"]}
        self.assertTrue(by_id["m-manual"]["launchable"])
        self.assertFalse(by_id["m-auto"]["launchable"])


class LaunchMacroTests(unittest.TestCase):
    def test_empty_id_errors(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.launch_macro("", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_success_wire_shape(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.launch_macro("m-manual", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "launched")
        self.assertEqual(out["macro_id"], "m-manual")
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "LaunchMacro")
        self.assertEqual(req.macro_id, "m-manual")


class ChangeArmStateTests(unittest.TestCase):
    def test_state_mapping(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_arm_state("cam", "arm", 5, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertTrue(out["auto_reverts"])
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "ChangeArmState")
        self.assertEqual(req.state, _FakeEventsPb2.CameraArmStateEvent.CS_Arm)
        self.assertEqual(req.timeout.seconds, 5)

    def test_disarm_and_private_map(self) -> None:
        inst = _ctl(enabled=True)
        inst.change_arm_state("cam", "disarm", 2, module.LOGIC_CONTROL_CONFIRMATION)
        inst.change_arm_state("cam", "arm_private", 2, module.LOGIC_CONTROL_CONFIRMATION)
        states = [c[1].state for c in inst.client.calls]
        self.assertEqual(states, [
            _FakeEventsPb2.CameraArmStateEvent.CS_Disarm,
            _FakeEventsPb2.CameraArmStateEvent.CS_ArmPrivate,
        ])

    def test_unknown_state_errors(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_arm_state("cam", "explode", 5, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_timeout_required_rejects_zero(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_arm_state("cam", "arm", 0, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_timeout_capped(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_arm_state("cam", "arm", 99999, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["timeout_s"], module.ARM_TIMEOUT_CAP_S)
        (_, req, _), = inst.client.calls
        self.assertEqual(req.timeout.seconds, module.ARM_TIMEOUT_CAP_S)

    def test_empty_camera_errors(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_arm_state("", "arm", 5, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


if __name__ == "__main__":
    unittest.main()
