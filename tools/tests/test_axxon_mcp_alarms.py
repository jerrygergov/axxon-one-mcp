from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "secret"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self) -> None:
        self.inventory = {
            "cameras": [
                {
                    "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                    "display_name": "Camera 1",
                    "enabled": True,
                    "serial_number": "SHOULD_NOT_LEAK",
                }
            ],
        }
        self.calls: list[tuple[str, tuple, dict]] = []

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):  # parity with AxxonApiClient.sanitize
        return value


class AxxonMcpAlarmsTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = alarms.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))

        rejected = alarms.connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["profile_name"], "other")
        self.assertEqual(rejected["status"], "gap")


if __name__ == "__main__":
    unittest.main()
