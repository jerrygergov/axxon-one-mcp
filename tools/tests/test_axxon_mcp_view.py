from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any
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

    def archive_calendar(self, source_ap: str, archive_ap: str) -> dict[str, Any]:
        return {"days": ["2026-05-15", "2026-05-16"], "source": source_ap, "archive": archive_ap}

    def archive_intervals(self, camera_legacy_ap: str, begin: str, end: str, archive_ap: str | None = None) -> list[dict[str, str]]:
        return [{"begin": "2026-05-16T10:00:00.000000Z", "end": "2026-05-16T10:00:05.000000Z"}]

    def archive_time_range_legacy(self, hours: int = 1) -> tuple[str, str]:
        return ("2026-05-16T09:00:00.000000Z", "2026-05-16T10:00:00.000000Z")

    def http_get_json(self, path: str) -> dict[str, Any]:
        if path.startswith("/statistics/"):
            return {"bitrate": 1234, "fps": 10, "width": 640, "height": 360, "mediaType": "video", "streamType": "live"}
        if path == "/rtsp/stat":
            return {"sessions": []}
        return {}


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


    def test_snapshot_batch_returns_one_url_per_known_camera_and_caps_count(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        # Pass a 10-camera list; only 2 exist in fixture and SNAPSHOT_BATCH_LIMIT clamps to 8.
        aps = [f"hosts/Server/DeviceIpint.{i}/SourceEndpoint.video:0:0" for i in range(1, 11)]
        result = view.snapshot_batch(aps)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "snapshot_batch")
        self.assertLessEqual(len(result["items"]), module.SNAPSHOT_BATCH_LIMIT)
        ok_items = [item for item in result["items"] if item["status"] == "ok"]
        gap_items = [item for item in result["items"] if item["status"] == "gap"]
        self.assertEqual(len(ok_items), 2)
        self.assertGreaterEqual(len(gap_items), 1)
        for item in ok_items:
            self.assertIn("/live/media/snapshot/", item["url"])
            self.assertEqual(item["caps"]["bytes"], module.DEFAULT_MAX_BYTES)


    def test_archive_scrub_combines_calendar_intervals_and_frame_probe(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_scrub(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            hours=2,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "archive_scrub")
        self.assertIn("days", result["calendar"])
        self.assertEqual(len(result["intervals"]), 1)
        self.assertIn("/archive/media/", result["sample_frame_url"])
        self.assertEqual(result["caps"]["bytes"], module.DEFAULT_MAX_BYTES)

    def test_archive_scrub_picks_archive_with_intervals(self) -> None:
        class TwoArchiveClient(FakeClient):
            def __init__(self) -> None:
                super().__init__()
                self.inventory["archives"] = [
                    {"access_point": "hosts/Server/DeviceIpint.5/MultimediaStorage.0", "enabled": True},
                    {"access_point": "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage", "enabled": True},
                ]

            def archive_intervals(self, camera_legacy_ap, begin, end, archive_ap=None):
                if "AliceBlue" in (archive_ap or ""):
                    return [{"begin": "2026-05-29T07:56:53.451000", "end": "2026-05-29T08:56:56.550000"}]
                return []

        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: TwoArchiveClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_scrub("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", hours=1)
        self.assertEqual(result["status"], "ok")
        self.assertIn("AliceBlue", result["archive"])
        self.assertEqual(len(result["intervals"]), 1)

    def test_archive_scrub_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_scrub("hosts/Server/NotACamera")
        self.assertEqual(result["status"], "gap")

    def test_archive_frame_returns_url_with_threshold(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_frame(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            ts="2026-05-16T10:00:00.000000Z",
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("/archive/media/", result["url"])
        self.assertIn("threshold=", result["url"])
        self.assertEqual(result["caps"]["bytes"], module.DEFAULT_MAX_BYTES)

    def test_archive_mjpeg_bounded_returns_capped_url(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_mjpeg_bounded(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            begin_ts="2026-05-16T10:00:00.000000Z",
            speed=99,
            fps=99,
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("/archive/media/", result["url"])
        self.assertEqual(result["caps"]["bytes"], module.ARCHIVE_MJPEG_BYTE_CAP)
        self.assertLessEqual(result["caps"]["fps"], module.DEFAULT_FPS)
        self.assertLessEqual(result["caps"]["speed"], 8)

    def test_stream_health_returns_statistics_and_rtsp_summary(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.stream_health("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["statistics"]["bitrate"], 1234)
        self.assertEqual(result["rtsp"]["sessions"], [])
        self.assertNotIn("password", str(result))


if __name__ == "__main__":
    unittest.main()
