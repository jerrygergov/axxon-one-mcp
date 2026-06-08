from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class MediaStreamSmokeTests(unittest.TestCase):
    def test_checks_are_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = module.media_checks()
        self.assertTrue(all("max_bytes" in item for item in checks))
        self.assertTrue(all(item["max_bytes"] <= 1048576 for item in checks))

    def test_archive_media_uses_resolved_archive_timestamp(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        archive_checks = [item for item in module.media_checks() if item["name"].startswith("archive_")]
        self.assertTrue(archive_checks)
        self.assertTrue(all("{archive_media_time}" in item["path"] for item in archive_checks))

    def test_rtsp_descriptor_checks_are_http_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = {item["name"]: item for item in module.media_checks()}
        self.assertIn("camera_live_rtsp_descriptor", checks)
        self.assertIn("rtsp_statistics", checks)
        self.assertIn("format=rtsp", checks["camera_live_rtsp_descriptor"]["path"])
        self.assertLessEqual(checks["camera_live_rtsp_descriptor"]["max_bytes"], 1048576)

    def test_rtsp_playback_check_is_external_and_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = {item["name"]: item for item in module.media_checks()}
        self.assertIn("rtsp_playback_ffprobe", checks)
        self.assertTrue(checks["rtsp_playback_ffprobe"]["path"].startswith("rtsp://"))
        self.assertEqual(checks["rtsp_playback_ffprobe"]["max_bytes"], 0)

    def test_composite_rtsp_check_is_external_and_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = {item["name"]: item for item in module.media_checks()}
        self.assertIn("composite_rtsp_playback_ffprobe", checks)
        self.assertIn("/composite/{composite_sources}", checks["composite_rtsp_playback_ffprobe"]["path"])
        self.assertEqual(checks["composite_rtsp_playback_ffprobe"]["max_bytes"], 0)

    def test_onvif_rtp_timestamp_check_is_external_and_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = {item["name"]: item for item in module.media_checks()}
        self.assertIn("onvif_rtp_timestamp_probe", checks)
        self.assertTrue(checks["onvif_rtp_timestamp_probe"]["path"].startswith("rtsp://"))
        self.assertEqual(checks["onvif_rtp_timestamp_probe"]["max_bytes"], 0)

    def test_parse_rtp_onvif_timestamp_extension(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        header = bytes.fromhex("906049390000000000000001abac0003")
        extension = bytes.fromhex("eda637e5d1eb851e00000000")
        parsed = module.parse_rtp_onvif_timestamp(header + extension + b"\x65")
        self.assertTrue(parsed["has_extension"])
        self.assertEqual(parsed["extension_profile"], "0xabac")
        self.assertEqual(parsed["onvif_timestamp"], "2026-05-06T21:57:57.820000+00:00")

    def test_composite_sources_uses_display_ids_and_stream_parts(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        smoke = module.MediaStreamSmoke.__new__(module.MediaStreamSmoke)
        cameras = [
            {
                "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "display_id": "10",
            },
            {
                "access_point": "hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:1",
                "display_id": "11",
            },
        ]
        self.assertEqual(smoke.composite_sources(cameras), "Server/10/0/0+Server/11/0/1")

    def test_parser_accepts_bearer_auth_mode(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        original_argv = sys.argv
        try:
            sys.argv = ["axxon_media_stream_smoke.py", "--password", "x", "--auth-mode", "bearer"]
            args = module.parse_args()
        finally:
            sys.argv = original_argv
        self.assertEqual(args.auth_mode, "bearer")
