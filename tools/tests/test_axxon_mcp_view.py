from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "demo.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://demo.local"
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
                },
                {
                    "access_point": "hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0",
                    "display_name": "Camera 2",
                    "enabled": True,
                },
            ],
            "archives": [
                {"access_point": "hosts/Server/MultimediaStorage.Main/MultimediaStorage", "enabled": True},
            ],
        }

    def load_inventory(self):
        return self.inventory

    def sanitize(self, value):
        if isinstance(value, dict):
            return {k: ("<redacted>" if k == "serial_number" else self.sanitize(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.sanitize(v) for v in value]
        return value


class AxxonMcpViewTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = view.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))


if __name__ == "__main__":
    unittest.main()
