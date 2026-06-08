from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_server_settings as module


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


_LEVELS = {
    "LOG_LEVEL_OFF": 0,
    "LOG_LEVEL_ERR": 10,
    "LOG_LEVEL_WARNING": 20,
    "LOG_LEVEL_INFO": 40,
    "LOG_LEVEL_DEBUG": 50,
    "LOG_LEVEL_TRACE": 60,
    "LOG_LEVEL_MAX": 100,
}
_NAMES = {v: k for k, v in _LEVELS.items()}


class _LogLevelEnum:
    @staticmethod
    def keys():
        return list(_LEVELS.keys())

    @staticmethod
    def Value(name):
        return _LEVELS[name]

    @staticmethod
    def Name(value):
        return _NAMES[value]


class _GetResp:
    def __init__(self, node_log_level=None, failed_nodes=None):
        self.node_log_level = node_log_level if node_log_level is not None else {"Server": 40}
        self.failed_nodes = failed_nodes or []


class _SetResp:
    def __init__(self, failed_nodes=None):
        self.failed_nodes = failed_nodes or []


class _DropResp:
    def __init__(self, failed_nodes=None):
        self.failed_nodes = failed_nodes or []


class _GetReq:
    def __init__(self, nodes=None):
        self.nodes = list(nodes or [])


class _SetReq:
    def __init__(self, nodes=None, log_level=0):
        self.nodes = list(nodes or [])
        self.log_level = log_level


class _DropReq:
    def __init__(self, nodes=None):
        self.nodes = list(nodes or [])


class _SrvPb2:
    LogLevel = _LogLevelEnum
    GetLogLevelRequest = _GetReq
    SetLogLevelRequest = _SetReq
    DropLogsRequest = _DropReq

    LOG_LEVEL_OFF = 0
    LOG_LEVEL_ERR = 10
    LOG_LEVEL_WARNING = 20
    LOG_LEVEL_INFO = 40
    LOG_LEVEL_DEBUG = 50
    LOG_LEVEL_TRACE = 60
    LOG_LEVEL_MAX = 100


class _FakeStub:
    def __init__(self, recorder, get_resp=None):
        self._rec = recorder
        self._get = get_resp or _GetResp()

    def GetLogLevel(self, request, timeout=None):
        self._rec.append(("GetLogLevel", request, timeout))
        return self._get

    def SetLogLevel(self, request, timeout=None):
        self._rec.append(("SetLogLevel", request, timeout))
        # reflect the set into the readback map for the current node
        self._get = _GetResp(node_log_level={"Server": request.log_level})
        return _SetResp()

    def DropLogs(self, request, timeout=None):
        self._rec.append(("DropLogs", request, timeout))
        return _DropResp()


class FakeSrvClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "ServerSettings"
        return _FakeStub(self.calls)

    def import_module(self, name):
        return _SrvPb2()


def _srv(**overrides):
    inst = module.AxxonMcpServerSettings(
        client_factory=lambda config: FakeSrvClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.server_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_get_log_level_shape(self) -> None:
        out = _srv().get_log_level()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["node_log_level"], {"Server": "LOG_LEVEL_INFO"})
        self.assertEqual(out["failed_nodes"], [])


class GatingTests(unittest.TestCase):
    def test_set_log_level_disabled(self) -> None:
        inst = _srv(enabled=False)
        out = inst.set_log_level("LOG_LEVEL_DEBUG", confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_set_log_level_bad_token(self) -> None:
        inst = _srv(enabled=True)
        out = inst.set_log_level("LOG_LEVEL_DEBUG", confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_drop_logs_disabled(self) -> None:
        inst = _srv(enabled=False)
        out = inst.drop_logs(confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_drop_logs_bad_token(self) -> None:
        inst = _srv(enabled=True)
        out = inst.drop_logs(confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])


class InputTests(unittest.TestCase):
    def test_set_log_level_requires_level(self) -> None:
        inst = _srv(enabled=True)
        out = inst.set_log_level("", confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_set_log_level_invalid_name(self) -> None:
        inst = _srv(enabled=True)
        out = inst.set_log_level("LOG_LEVEL_BOGUS", confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertIn("LOG_LEVEL_INFO", out["valid_levels"])
        self.assertEqual(inst.client.calls, [])


class SetLogLevelTests(unittest.TestCase):
    def test_set_then_readback_order(self) -> None:
        inst = _srv(enabled=True)
        out = inst.set_log_level("LOG_LEVEL_DEBUG", confirmation=module.SERVER_CONFIRMATION)
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["SetLogLevel", "GetLogLevel"])  # set then readback
        req = inst.client.calls[0][1]
        self.assertEqual(req.log_level, 50)
        self.assertEqual(list(req.nodes), [])  # current node when not given
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["node_log_level"], {"Server": "LOG_LEVEL_DEBUG"})

    def test_nodes_passed_through(self) -> None:
        inst = _srv(enabled=True)
        inst.set_log_level("LOG_LEVEL_ERR", nodes=["Server"], confirmation=module.SERVER_CONFIRMATION)
        req = inst.client.calls[0][1]
        self.assertEqual(list(req.nodes), ["Server"])
        self.assertEqual(req.log_level, 10)


class DropLogsTests(unittest.TestCase):
    def test_drop_logs_shape(self) -> None:
        inst = _srv(enabled=True)
        out = inst.drop_logs(confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed_nodes"], [])
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["DropLogs"])
        self.assertEqual(list(inst.client.calls[0][1].nodes), [])

    def test_drop_logs_nodes(self) -> None:
        inst = _srv(enabled=True)
        inst.drop_logs(nodes=["Server"], confirmation=module.SERVER_CONFIRMATION)
        self.assertEqual(list(inst.client.calls[0][1].nodes), ["Server"])


if __name__ == "__main__":
    unittest.main()
