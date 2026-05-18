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
        self.inventory: dict[str, Any] = {"cameras": [], "archives": []}
        self.calls: list[tuple[str, tuple, dict]] = []

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):
        return value


class AxxonMcpViewObjectsTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = vo.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))

        rejected = vo.connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(rejected["profile_name"], "other")

    def test_normalize_layout_meta_only(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {
                "layout_id": "lid-1",
                "owned_by_user": True,
                "etag": "etag-1",
                "has_write_access": True,
                "shared_with": [],
                "sharing_properties": {},
            },
        }
        out = module.normalize_layout(raw)
        self.assertEqual(out["layout_id"], "lid-1")
        self.assertTrue(out["owned_by_user"])
        self.assertEqual(out["etag"], "etag-1")
        self.assertIsNone(out["display_name"])
        self.assertIsNone(out["cells_count"])

    def test_normalize_layout_full(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {"layout_id": "lid-2", "owned_by_user": True, "etag": "e2", "has_write_access": True},
            "body": {
                "id": "lid-2",
                "display_name": "Main",
                "is_user_defined": True,
                "is_for_alarm": False,
                "cells": {"1": {}, "2": {}, "3": {}},
                "map_id": "map-9",
            },
        }
        out = module.normalize_layout(raw)
        self.assertEqual(out["display_name"], "Main")
        self.assertTrue(out["is_user_defined"])
        self.assertFalse(out["is_for_alarm"])
        self.assertEqual(out["cells_count"], 3)
        self.assertEqual(out["map_id"], "map-9")

    def test_normalize_map_strips_password_keys(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {
                "id": "m-1",
                "access": "MAP_ACCESS_FULL",
                "sharing": {"owner": "u-1", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                "name": "Plan",
                "type": "MAP_TYPE_RASTER",
                "etag": "e",
                "image_etag": "ie",
            },
        }
        out = module.normalize_map(raw)
        self.assertEqual(out["map_id"], "m-1")
        self.assertEqual(out["type"], "MAP_TYPE_RASTER")
        self.assertEqual(out["access"], "MAP_ACCESS_FULL")
        self.assertEqual(out["owner"], "u-1")
        self.assertEqual(out["sharing_kind"], "SHARING_KIND_ANY")
        self.assertEqual(out["etag"], "e")
        self.assertEqual(out["image_etag"], "ie")
        self.assertNotIn("password", str(out))

    def test_normalize_wall_redacts_data_bytes(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "wall_id": "w-1",
            "host_name": "h",
            "pid": 1234,
            "ppid": 5,
            "name": "wall-name",
            "display_name": "Main Wall",
            "seq_number": 7,
            "data": {"data": "VGVzdEJ5dGVz"},  # base64 of "TestBytes"
        }
        out = module.normalize_wall(raw)
        self.assertEqual(out["wall_id"], "w-1")
        self.assertEqual(out["data_size"], 9)
        self.assertNotIn("VGVzdEJ5dGVz", str(out))
        self.assertNotIn("TestBytes", str(out))

    def test_normalize_marker_keeps_position_and_access_point(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "id": "mk-1",
            "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "position": {"x": 0.5, "y": 0.2},
            "marker_type": "MARKER_TYPE_CAMERA",
        }
        out = module.normalize_marker(raw)
        self.assertEqual(out["marker_id"], "mk-1")
        self.assertEqual(out["access_point"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(out["position"], {"x": 0.5, "y": 0.2})
        self.assertEqual(out["marker_type"], "MARKER_TYPE_CAMERA")


if __name__ == "__main__":
    unittest.main()
