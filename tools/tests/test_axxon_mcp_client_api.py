from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_client_api as module


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


class FakeClient:
    def __init__(self, config):
        self.config = config

    def sanitize(self, value):
        return value


def _inst(reachable_ports=None):
    reachable = set(reachable_ports or [])
    probed: list[tuple[str, int]] = []

    def socket_probe(host, port, timeout):
        probed.append((host, port))
        return port in reachable

    inst = module.AxxonMcpClientApi(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
        socket_probe=socket_probe,
    )
    inst.client_api_connect_axxon_profile("env")
    inst._probed = probed  # type: ignore[attr-defined]
    return inst


class ConnectTests(unittest.TestCase):
    def test_connect_env_only_lazy_and_redacts_secrets(self) -> None:
        created = []
        inst = module.AxxonMcpClientApi(
            client_factory=lambda config: created.append(config) or FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )
        self.assertIsNone(inst.client)
        rejected = inst.client_api_connect_axxon_profile("prod")
        self.assertFalse(rejected["connected"])
        self.assertEqual(created, [])

        out = inst.client_api_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


class PreflightTests(unittest.TestCase):
    def test_preflight_unreachable_reports_gap_no_secret(self) -> None:
        inst = _inst(reachable_ports=[])
        out = inst.client_api_preflight(client_http_port=8888)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["reachable_count"], 0)
        self.assertTrue(out["fixture_gap"])
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))
        # probed both local and remote host on the requested port
        self.assertIn(("127.0.0.1", 8888), inst._probed)
        self.assertIn(("example.local", 8888), inst._probed)

    def test_preflight_reachable_clears_gap(self) -> None:
        inst = _inst(reachable_ports=[8888])
        out = inst.client_api_preflight(client_http_port=8888)
        self.assertGreaterEqual(out["reachable_count"], 1)
        self.assertEqual(out["fixture_gap"], "")

    def test_preflight_never_mutates(self) -> None:
        inst = _inst(reachable_ports=[8888])
        out = inst.client_api_preflight(client_http_port=8888)
        # every check is a read-only socket probe; nothing in the result performs a switch/mode op
        for check in out["checks"]:
            self.assertIn("reachable", check)
            self.assertNotIn("executed", check)


class OperationCatalogTests(unittest.TestCase):
    def test_operations_all_fixture_needed_no_wire(self) -> None:
        inst = _inst()
        out = inst.list_client_api_operations()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(inst._probed, [])
        ops = {op["operation"] for op in out["operations"]}
        self.assertIn("SwitchLayout", ops)
        self.assertIn("AddCameraToDisplay", ops)
        self.assertTrue(all(op["status"] == "fixture-needed" for op in out["operations"]))
        for op in out["operations"]:
            self.assertTrue(op["required_fixture"])


if __name__ == "__main__":
    unittest.main()
