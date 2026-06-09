from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_statistics as module

_SECRET = "STATS-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _StatPointType:
    """Stand-in for the StatPointType enum with .Name() and .Value()."""

    _by_name = {"SPT_LiveFPS": 0, "SPT_CpuTotalUsage": 18, "SPT_Unknown": 1000}
    _by_num = {v: k for k, v in _by_name.items()}

    @classmethod
    def Name(cls, number):
        return cls._by_num[number]

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _StatPointKey:
    def __init__(self, type=0, name=""):
        self.type = type
        self.name = name


class _StatPoint:
    """Canned StatPoint: a CPU usage reading with a double value via the oneof."""

    def __init__(self, type=18, name="node-1", which="value_double", value=42.5):
        self.key = _StatPointKey(type=type, name=name)
        self._which = which
        self.value_double = value if which == "value_double" else 0.0
        self.value_uint64 = int(value) if which == "value_uint64" else 0
        self.value_int32 = 0
        self.value_uint32 = 0
        self.value_int64 = 0

    def WhichOneof(self, field):
        return self._which


class _StatsResponse:
    def __init__(self, stats=None, fails=None):
        self.stats = stats if stats is not None else [_StatPoint()]
        self.fails = fails if fails is not None else []


class _RepeatedKeys(list):
    """Mimic a protobuf repeated message field: .add(**kwargs) appends a key."""

    def add(self, **kwargs):
        key = _StatPointKey(**kwargs)
        self.append(key)
        return key


class _StatsRequest:
    def __init__(self):
        self.keys = _RepeatedKeys()


class _Pb2:
    StatPointType = _StatPointType
    StatPointKey = _StatPointKey
    StatsRequest = _StatsRequest


class _Stub:
    def __init__(self, rec, response=None):
        self._rec = rec
        self._response = response

    def GetStatistics(self, request, timeout=None):
        self._rec.append(("GetStatistics", list(getattr(request, "keys", []))))
        return self._response if self._response is not None else _StatsResponse()


class FakeClient:
    def __init__(self, config, response=None):
        self.config = config
        self.calls: list = []
        self._response = response

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._response)

    def import_module(self, name):
        return _Pb2()


def _inst(response=None, **overrides):
    inst = module.AxxonMcpStatistics(
        client_factory=lambda config: FakeClient(config, response),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.statistics_connect_axxon_profile("env")
    return inst


class StatisticsTests(unittest.TestCase):
    def test_connect_reports_read_mode(self) -> None:
        out = _inst().statistics_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_get_statistics_ok_summarizes_points(self) -> None:
        out = _inst().get_statistics()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "get_statistics")
        self.assertEqual(out["count"], 1)
        point = out["stats"][0]
        self.assertEqual(point["type"], "SPT_CpuTotalUsage")
        self.assertEqual(point["name"], "node-1")
        self.assertEqual(point["value"], 42.5)

    def test_get_statistics_defaults_to_all_points(self) -> None:
        inst = _inst()
        inst.get_statistics()
        # No keys supplied -> request.keys stays empty (server returns all points).
        method, keys = inst.client.calls[0]
        self.assertEqual(method, "GetStatistics")
        self.assertEqual(keys, [])

    def test_get_statistics_filters_by_named_keys(self) -> None:
        inst = _inst()
        inst.get_statistics(keys=[{"type": "SPT_CpuTotalUsage", "name": "node-1"}])
        _, keys = inst.client.calls[0]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].type, 18)
        self.assertEqual(keys[0].name, "node-1")

    def test_invalid_stat_type_returns_gap_not_exception(self) -> None:
        out = _inst().get_statistics(keys=[{"type": "NOPE_NOT_A_TYPE"}])
        self.assertEqual(out["status"], "gap")
        self.assertIn("NOPE_NOT_A_TYPE", out["message"])

    def test_fails_are_summarized(self) -> None:
        resp = _StatsResponse(stats=[], fails=[_StatPointKey(type=0, name="boom")])
        out = _inst(response=resp).get_statistics()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["fails"][0]["type"], "SPT_LiveFPS")
        self.assertEqual(out["fails"][0]["name"], "boom")

    def test_no_config_secret_leak(self) -> None:
        out = _inst().get_statistics()
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("get_statistics", module.STATISTICS_TOOL_NAMES)
        self.assertIn("statistics_connect_axxon_profile", module.STATISTICS_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
