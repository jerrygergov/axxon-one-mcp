from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_state_control as module

_SECRET = "STATE-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = _SECRET
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _StateResponse:
    def __init__(self, result=True):
        self.result = result


class _EStateDirective:
    STATE_DIRECTIVE_NEUTRAL = 0
    STATE_DIRECTIVE_OFF = 1
    STATE_DIRECTIVE_ON = 2
    _by_name = {"STATE_DIRECTIVE_NEUTRAL": 0, "STATE_DIRECTIVE_OFF": 1, "STATE_DIRECTIVE_ON": 2}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _EPriority:
    PRIORITY_DEFAULT_STATE = 0
    PRIORITY_DAEMON = 1
    PRIORITY_USER = 2
    _by_name = {"PRIORITY_DEFAULT_STATE": 0, "PRIORITY_DAEMON": 1, "PRIORITY_USER": 2}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _GetCurrentStateRequest:
    def __init__(self, access_point=""):
        self.access_point = access_point


class _GetDefaultStateRequest:
    def __init__(self, access_point=""):
        self.access_point = access_point


class _SetStateRequest:
    EPriority = _EPriority
    EStateDirective = _EStateDirective

    def __init__(self, access_point="", priority=0, directive=0):
        self.access_point = access_point
        self.priority = priority
        self.directive = directive


class _Pb2:
    EStateDirective = _EStateDirective
    EPriority = _EPriority
    GetCurrentStateRequest = _GetCurrentStateRequest
    GetDefaultStateRequest = _GetDefaultStateRequest
    SetStateRequest = _SetStateRequest


class _Stub:
    def __init__(self, rec, current=True):
        self._rec = rec
        self._current = current

    def GetCurrentState(self, request, timeout=None):
        self._rec.append(("GetCurrentState", request.access_point))
        return _StateResponse(self._current)

    def GetDefaultState(self, request, timeout=None):
        self._rec.append(("GetDefaultState", request.access_point))
        return _StateResponse(False)

    def SetState(self, request, timeout=None):
        self._rec.append(("SetState", request.access_point, request.priority, request.directive))
        return _StateResponse(True)


class FakeClient:
    def __init__(self, config, current=True):
        self.config = config
        self.calls: list = []
        self._current = current

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._current)

    def import_module(self, name):
        return _Pb2()


def _inst(enabled=True, current=True):
    inst = module.AxxonMcpStateControl(
        client_factory=lambda config: FakeClient(config, current),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.state_control_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_connect_read_write_mode(self):
        out = _inst().state_control_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read+write")
        self.assertEqual(out["approval_env"], module.STATE_CONTROL_APPROVE_ENV)

    def test_get_current_state(self):
        out = _inst(current=True).get_current_state("hosts/Server/DeviceIpint.54/StateControl.telemetry:0")
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["result"])

    def test_get_default_state(self):
        out = _inst().get_default_state("hosts/Server/DeviceIpint.54/StateControl.telemetry:0")
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["result"])

    def test_get_requires_access_point(self):
        out = _inst().get_current_state("")
        self.assertEqual(out["status"], "gap")


class SetStateGateTests(unittest.TestCase):
    AP = "hosts/Server/DeviceIpint.54/StateControl.telemetry:0"

    def test_disabled_without_approve(self):
        out = _inst(enabled=False).set_state(self.AP, directive="STATE_DIRECTIVE_ON", confirmation=module.STATE_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.STATE_CONTROL_APPROVE_ENV)

    def test_refuses_without_token(self):
        out = _inst().set_state(self.AP, directive="STATE_DIRECTIVE_ON", confirmation="")
        self.assertEqual(out["status"], "gap")
        self.assertIn(module.STATE_CONTROL_CONFIRMATION, out["message"])

    def test_invalid_directive_gap(self):
        out = _inst().set_state(self.AP, directive="BOGUS", confirmation=module.STATE_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "gap")
        self.assertIn("BOGUS", out["message"])

    def test_applies_with_token(self):
        inst = _inst()
        out = inst.set_state(self.AP, directive="STATE_DIRECTIVE_ON", priority="PRIORITY_USER", confirmation=module.STATE_CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        call = [c for c in inst.client.calls if c[0] == "SetState"][0]
        self.assertEqual(call[2], 2)  # PRIORITY_USER
        self.assertEqual(call[3], 2)  # STATE_DIRECTIVE_ON


class CommonTests(unittest.TestCase):
    def test_no_secret_leak(self):
        out = _inst().get_current_state("hosts/Server/x/StateControl.telemetry:0")
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self):
        for name in ("get_current_state", "get_default_state", "set_state"):
            self.assertIn(name, module.STATE_CONTROL_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
