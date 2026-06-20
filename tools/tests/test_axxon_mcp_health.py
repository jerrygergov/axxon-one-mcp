from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_health as module

_SECRET = "HEALTH-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _HealthResponse:
    def __init__(self, status):
        self.status = status


class _HealthStub:
    def __init__(self, rec, statuses=None):
        self._rec = rec
        self._statuses = statuses or [1]

    def Check(self, request, timeout=None):
        self._rec.append(("Check", request.service, timeout))
        return _HealthResponse(self._statuses[0])

    def Watch(self, request, timeout=None):
        self._rec.append(("Watch", request.service, timeout))
        for status in self._statuses:
            yield _HealthResponse(status)


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []
        self.grpc_channel = object()

    def authenticate_grpc(self):
        self.calls.append(("authenticate_grpc",))
        return None


def _inst(statuses=None):
    rec: list = []
    inst = module.AxxonMcpHealth(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
        health_stub_factory=lambda channel: _HealthStub(rec, statuses),
    )
    inst.health_connect_axxon_profile("env")
    inst.stub_calls = rec
    return inst


class HealthTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().health_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")
        self.assertNotIn(_SECRET, str(out))

    def test_check_ok(self) -> None:
        inst = _inst([1])
        out = inst.grpc_health_check("")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "grpc_health_check")
        self.assertEqual(out["serving_status"], "SERVING")
        self.assertEqual(inst.stub_calls[0][0], "Check")

    def test_watch_is_bounded(self) -> None:
        inst = _inst([1, 2, 3])
        out = inst.grpc_health_watch("axxon", max_items=2, timeout_s=4.0)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "grpc_health_watch")
        self.assertEqual(out["items"], ["SERVING", "NOT_SERVING"])
        self.assertEqual(out["items_seen"], 2)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["stop_reason"], "item_cap")
        self.assertEqual(inst.stub_calls[0], ("Watch", "axxon", 4.0))

    def test_tool_names_exported(self) -> None:
        self.assertIn("grpc_health_check", module.HEALTH_TOOL_NAMES)
        self.assertIn("grpc_health_watch", module.HEALTH_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
