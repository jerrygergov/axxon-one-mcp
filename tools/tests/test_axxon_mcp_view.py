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
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))
        self.assertNotIn("SHOULD_NOT_LEAK", str(profile))

        rejected = view.connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["profile_name"], "other")
        self.assertEqual(rejected["status"], "gap")


    def test_live_view_returns_url_with_caps_for_known_camera(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            duration_s=999,
            fps=999,
            format="mjpeg",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "live_view")
        self.assertIn("/live/media/", result["url"])
        self.assertIn("Server/DeviceIpint.1/SourceEndpoint.video:0:0", result["url"])
        self.assertEqual(result["caps"]["time_s"], module.DEFAULT_DURATION_S)
        self.assertEqual(result["caps"]["fps"], module.DEFAULT_FPS)
        self.assertEqual(result["auth"], {"header": "Authorization", "scheme": "Bearer"})
        self.assertNotIn("secret", str(result))

    def test_live_view_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view("hosts/Server/NotACamera", format="mjpeg")
        self.assertEqual(result["status"], "gap")
        self.assertIn("NotACamera", result["message"])

    def test_live_view_rejects_unknown_format(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            format="webp",
        )
        self.assertEqual(result["status"], "gap")
        self.assertIn("format", result["message"])


    def test_live_view_hls_omits_fps_and_width_from_caps_and_url(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            fps=999,
            width=320,
            format="hls",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["format"], "hls")
        self.assertIn("?format=hls", result["url"])
        self.assertNotIn("fps=", result["url"])
        self.assertNotIn("w=", result["url"])
        self.assertNotIn("fps", result["caps"])
        self.assertNotIn("width", result["caps"])

    def test_live_view_below_default_duration_is_not_floored(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            duration_s=3,
            format="mjpeg",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["caps"]["time_s"], 3)


if __name__ == "__main__":
    unittest.main()
