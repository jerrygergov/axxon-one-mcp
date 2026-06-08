from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class LegacyHttpSweepTests(unittest.TestCase):
    def test_sweep_has_safe_endpoint_groups(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        groups = module.safe_endpoint_groups()
        names = {group["name"] for group in groups}
        self.assertIn("server", names)
        self.assertIn("camera_inventory", names)
        self.assertIn("archive_read", names)
        self.assertIn("events_read", names)
        self.assertNotIn("delete_video", names)

    def test_events_group_uses_pdf_alerts_endpoint(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        events_group = next(group for group in module.safe_endpoint_groups() if group["name"] == "events_read")
        paths = {check["path"] for check in events_group["checks"]}
        self.assertIn("/archive/events/alerts/{end}/{begin}?limit=50&offset=0", paths)
        self.assertIn("/audit/{host_name}/{end}/{begin}?filter=17-20,6,1:4", paths)
        self.assertFalse(any("/archive/events/alarms/" in path for path in paths))

    def test_sweep_uses_reusable_client(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        self.assertTrue(hasattr(module, "LegacyHttpSweep"))

    def test_macros_group_uses_pdf_list_endpoints(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        macros_group = next(group for group in module.safe_endpoint_groups() if group["name"] == "macros_read")
        paths = {check["path"] for check in macros_group["checks"]}
        self.assertIn("/macro/list/", paths)
        self.assertIn("/macro/list/?exclude_auto", paths)
        self.assertNotIn("/macros", paths)

    def test_archive_group_uses_pdf_frame_registration_endpoint(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        archive_group = next(group for group in module.safe_endpoint_groups() if group["name"] == "archive_read")
        paths = {check["path"] for check in archive_group["checks"]}
        self.assertIn("/archive/contents/frames/{camera_legacy_ap}/{end}/{begin}?limit=3", paths)

    def test_parser_accepts_bearer_auth_mode(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        original_argv = __import__("sys").argv
        try:
            __import__("sys").argv = ["axxon_legacy_http_sweep.py", "--password", "x", "--auth-mode", "bearer"]
            args = module.parse_args()
        finally:
            __import__("sys").argv = original_argv
        self.assertEqual(args.auth_mode, "bearer")
