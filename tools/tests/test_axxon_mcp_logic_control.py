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


class _Duration:
    def __init__(self, seconds=0):
        self.seconds = seconds


class _ConfigResp:
    def __init__(self, **fields):
        for f in module.CONFIG_FIELDS:
            setattr(self, f, _Duration(fields.get(f, 0)))


class _CounterConfig:
    def __init__(self, **kw):
        self.guid = kw.get("guid", "")
        self.name = kw.get("name", "")


class _ListCountersResp:
    def __init__(self, counters):
        self.counters = counters


class _GenericReq:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakePb2:
    # ECameraArmState lives on events pb2 in reality; the module resolves it via
    # an events import, so the fake provides both pb2s through import_module.
    def __init__(self):
        self.ChangeArmStateRequest = _ArmReq
        self.LaunchMacroRequest = _MacroReq
        self.ListMacrosRequest = _ListReq
        self.GetConfigRequest = _GenericReq
        self.ChangeConfigRequest = _GenericReq
        self.Duration = _Duration
        self.CounterConfig = _CounterConfig
        self.ChangeCountersRequest = _GenericReq
        self.CounterActionRequest = _GenericReq


class _FakeMacroPb2:
    class CounterAction:
        START, STOP, CLEANUP, START_WITH_CLEANUP = 0, 1, 3, 4

        def __init__(self, **kw):
            self.counter = kw.get("counter", "")
            self.operation = kw.get("operation", 0)


class _FakeEventsPb2:
    class CameraArmStateEvent:
        CS_Disarm, CS_Arm, CS_ArmPrivate = 0, 1, 2


class _FakeStub:
    def __init__(self, recorder, macros, config_seconds=300, counters=None):
        self._rec = recorder
        self._macros = macros
        self._config_seconds = config_seconds
        self._counters = counters if counters is not None else []

    def LaunchMacro(self, request, timeout=None):
        self._rec.append(("LaunchMacro", request, timeout))
        return object()

    def ChangeArmState(self, request, timeout=None):
        self._rec.append(("ChangeArmState", request, timeout))
        return object()

    def ListMacros(self, request, timeout=None):
        self._rec.append(("ListMacros", request, timeout))
        return self._macros

    def GetConfig(self, request, timeout=None):
        self._rec.append(("GetConfig", request, timeout))
        return _ConfigResp(**{f: self._config_seconds for f in module.CONFIG_FIELDS})

    def ChangeConfig(self, request, timeout=None):
        self._rec.append(("ChangeConfig", request, timeout))
        return object()

    def ChangeCounters(self, request, timeout=None):
        self._rec.append(("ChangeCounters", request, timeout))
        return object()

    def ListCounters(self, request, timeout=None):
        self._rec.append(("ListCounters", request, timeout))
        return _ListCountersResp(self._counters)

    def CounterAction(self, request, timeout=None):
        self._rec.append(("CounterAction", request, timeout))
        return object()


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
        if name.endswith("Events_pb2"):
            return _FakeEventsPb2()
        if name.endswith("Macro_pb2"):
            return _FakeMacroPb2()
        return _FakePb2()

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


class ChangeConfigTests(unittest.TestCase):
    def test_disabled_without_approval(self) -> None:
        inst = _ctl(enabled=False)
        out = inst.change_config({"user_alert_ttl": 200}, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_empty_overrides_no_wire(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_config({}, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_unknown_field_no_wire(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_config({"nope": 1}, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_reads_then_overrides_only_passed_field(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_config({"user_alert_ttl": 301}, module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["previous"], {"user_alert_ttl": 300})
        self.assertEqual(out["applied"]["user_alert_ttl"], 301)
        # untouched field retains the value read from GetConfig
        self.assertEqual(out["applied"]["rule_alert_ttl"], 300)
        names = [c[0] for c in inst.client.calls]
        self.assertEqual(names, ["GetConfig", "ChangeConfig"])


class ChangeCountersTests(unittest.TestCase):
    def test_requires_exactly_one_of_add_or_remove(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_counters(confirmation=module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_add_missing_name_no_wire(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_counters(add={"guid": "g"}, confirmation=module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_add_wire_shape(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_counters(add={"guid": "g1", "name": "c1"}, confirmation=module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "added")
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "ChangeCounters")
        self.assertEqual(req.modified_counters[0].guid, "g1")

    def test_remove_wire_shape(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.change_counters(remove_guid="g1", confirmation=module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "removed")
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "ChangeCounters")
        self.assertEqual(req.removed_counters, ["g1"])


class CounterActionTests(unittest.TestCase):
    def test_empty_counter_no_wire(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.counter_action("", "start", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_bad_operation_no_wire(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.counter_action("g1", "explode", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_start_wire_shape(self) -> None:
        inst = _ctl(enabled=True)
        out = inst.counter_action("g1", "start", module.LOGIC_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "CounterAction")
        self.assertEqual(req.action.counter, "g1")
        self.assertEqual(req.action.operation, _FakeMacroPb2.CounterAction.START)


class NoSecretLeakTests(unittest.TestCase):
    def test_no_config_password_in_outputs(self) -> None:
        inst = _ctl(enabled=True)
        outs = [
            inst.change_config({"user_alert_ttl": 301}, module.LOGIC_CONTROL_CONFIRMATION),
            inst.change_counters(add={"guid": "g1", "name": "c1"}, confirmation=module.LOGIC_CONTROL_CONFIRMATION),
            inst.counter_action("g1", "start", module.LOGIC_CONTROL_CONFIRMATION),
        ]
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", repr(outs))


if __name__ == "__main__":
    unittest.main()
