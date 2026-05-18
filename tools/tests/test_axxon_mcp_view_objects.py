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
        self.map_pages: list[dict[str, Any]] = [
            {
                "meta": {
                    "id": "m-1",
                    "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-1", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Office plan",
                    "type": "MAP_TYPE_RASTER",
                    "etag": "e1",
                    "image_etag": "ie1",
                }
            },
            {
                "meta": {
                    "id": "m-2",
                    "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-2", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Floor 1",
                    "type": "MAP_TYPE_RASTER",
                    "etag": "e2",
                    "image_etag": "ie2",
                }
            },
        ]
        self.map_image_bytes: dict[str, bytes] = {"m-1": b"X" * 10, "m-big": b"Y" * 5_000_000}
        self.map_markers: dict[str, list[dict[str, Any]]] = {
            "m-1": [
                {
                    "id": "mk-1",
                    "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                    "position": {"x": 0.5, "y": 0.2},
                    "marker_type": "MARKER_TYPE_CAMERA",
                }
            ],
        }
        self.providers: list[dict[str, Any]] = [
            {"id": "bitmap-id", "name": "Bitmap or vector image", "etag": "bp1"},
            {"id": "google-id", "name": "Google Map", "etag": "gp1"},
        ]

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):
        return value

    def list_layouts(self, view: str) -> dict[str, Any]:
        self.calls.append(("list_layouts", (view,), {}))
        return {
            "status": 200,
            "body": {
                "current": "lid-1",
                "items": [
                    {
                        "meta": {
                            "layout_id": "lid-1",
                            "owned_by_user": True,
                            "etag": "e1",
                            "has_write_access": True,
                        },
                        "body": {
                            "id": "lid-1",
                            "display_name": "First",
                            "is_user_defined": True,
                            "is_for_alarm": False,
                            "cells": {"1": {}, "2": {}},
                            "map_id": "",
                        },
                    },
                    {
                        "meta": {
                            "layout_id": "lid-2",
                            "owned_by_user": False,
                            "etag": "e2",
                            "has_write_access": False,
                        },
                        "body": {
                            "id": "lid-2",
                            "display_name": "Second",
                            "is_user_defined": False,
                            "is_for_alarm": True,
                            "cells": {"1": {}},
                            "map_id": "m-1",
                        },
                    },
                ],
            },
        }

    def batch_get_layouts(self, items: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(("batch_get_layouts", (tuple(items[0].items()) if items else (),), {}))
        ids = [it["layout_id"] for it in items]
        out_items = []
        not_found = []
        for layout_id in ids:
            if layout_id == "lid-1":
                out_items.append(
                    {
                        "meta": {
                            "layout_id": "lid-1",
                            "owned_by_user": True,
                            "etag": "e1",
                            "has_write_access": True,
                        },
                        "body": {
                            "id": "lid-1",
                            "display_name": "First",
                            "is_user_defined": True,
                            "is_for_alarm": False,
                            "cells": {"1": {}, "2": {}},
                            "map_id": "",
                        },
                    }
                )
            else:
                not_found.append(layout_id)
        return {"status": 200, "body": {"items": out_items, "not_found_items": not_found}}

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(("layouts_on_view", (), {"layouts": list(layouts)}))
        return {"status": 200, "body": {}}

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        self.calls.append(("list_layout_images", (layout_id,), {}))
        if layout_id == "lid-unknown":
            return {"status": 500, "body": {}}
        return {"status": 200, "body": {"images": [{"id": "img-1", "etag": "ie-1"}]}}

    def list_maps(self) -> dict[str, Any]:
        self.calls.append(("list_maps", (), {}))
        return {"status": 200, "body": {"items": list(self.map_pages)}}

    def batch_get_maps(self, map_ids: list[str]) -> dict[str, Any]:
        self.calls.append(("batch_get_maps", (tuple(map_ids),), {}))
        items = [m for m in self.map_pages if m["meta"]["id"] in map_ids]
        not_found = [mid for mid in map_ids if mid not in {m["meta"]["id"] for m in self.map_pages}]
        return {"status": 200, "body": {"items": items, "not_found": not_found}}

    def get_map_image(self, map_id: str) -> dict[str, Any]:
        self.calls.append(("get_map_image", (map_id,), {}))
        if map_id not in self.map_image_bytes:
            return {"status": 500, "body": {}}
        import base64

        raw = self.map_image_bytes[map_id]
        return {
            "status": 200,
            "body": {
                "etag": f"img-etag-{map_id}",
                "total_size_bytes": len(raw),
                "content_type": "image/png",
                "data": base64.b64encode(raw).decode("ascii"),
            },
        }

    def get_markers(self, map_id: str) -> dict[str, Any]:
        self.calls.append(("get_markers", (map_id,), {}))
        return {"status": 200, "body": {"markers": list(self.map_markers.get(map_id, []))}}

    def list_map_providers(self) -> dict[str, Any]:
        self.calls.append(("list_map_providers", (), {}))
        return {"status": 200, "body": {"map_providers": list(self.providers)}}

    def list_walls(self) -> dict[str, Any]:
        self.calls.append(("list_walls", (), {}))
        return {
            "status": 200,
            "body": {
                "event_stream_items": [
                    {"walls": [], "unreachable_objects": ["transient"]},
                    {
                        "walls": [
                            {
                                "wall_id": "w-1",
                                "host_name": "h",
                                "pid": 100,
                                "ppid": 1,
                                "name": "wall-name",
                                "display_name": "Main Wall",
                                "seq_number": 5,
                                "data": {"data": "VGVzdEJ5dGVz"},
                            }
                        ],
                        "unreachable_objects": [],
                    },
                ],
                "event_stream_count": 2,
            },
        }


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

    def test_list_layouts_meta_returns_normalized_items(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layouts(view="meta", limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["applied_view"], "VIEW_MODE_ONLY_META")
        self.assertEqual(r["applied_limit"], module.LIST_LIMIT_CAP)
        self.assertEqual(r["items"][0]["layout_id"], "lid-1")

    def test_list_layouts_unknown_view_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.list_layouts(view="banana", limit=10)
        self.assertEqual(r["status"], "gap")
        self.assertIn("view", r["message"])

    def test_get_layout_returns_normalized_item(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_layout("lid-1", etag=None)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["item"]["layout_id"], "lid-1")
        self.assertEqual(r["item"]["display_name"], "First")

    def test_get_layout_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_layout("lid-missing")
        self.assertEqual(r["status"], "gap")
        self.assertIn("lid-missing", r["message"])

    def test_layouts_on_view_returns_pushed_count(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.layouts_on_view([{"layout_id": "lid-1", "layout_display_name": "First"}])
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["pushed"], 1)

    def test_list_layout_images_returns_meta(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layout_images("lid-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["id"], "img-1")

    def test_list_layout_images_unknown_layout_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layout_images("lid-unknown")
        self.assertEqual(r["status"], "gap")

    def test_list_maps_returns_normalized_items(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_maps(limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["applied_limit"], module.LIST_LIMIT_CAP)
        self.assertEqual(r["items"][0]["map_id"], "m-1")
        self.assertEqual(r["items"][0]["type"], "MAP_TYPE_RASTER")

    def test_get_map_returns_normalized_item(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["item"]["map_id"], "m-1")

    def test_get_map_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_map("m-missing")
        self.assertEqual(r["status"], "gap")

    def test_get_map_image_small_returns_metadata_no_raw_bytes(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["bytes_returned"], 10)
        self.assertFalse(r["truncated"])
        self.assertEqual(r["content_type"], "image/png")
        self.assertNotIn("data", r)

    def test_get_map_image_truncates_at_cap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-big", max_bytes=1000)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["bytes_returned"], 1000)
        self.assertTrue(r["truncated"])

    def test_get_map_image_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-missing")
        self.assertEqual(r["status"], "gap")

    def test_get_markers_returns_normalized_list(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_markers("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["marker_id"], "mk-1")

    def test_list_map_providers_returns_provider_list(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_map_providers()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertIn("Google", r["items"][1]["name"])

    def test_list_walls_flattens_pages_and_drops_transient_unreachable(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_walls(limit=10)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["wall_id"], "w-1")
        self.assertEqual(r["items"][0]["data_size"], 9)
        self.assertEqual(r.get("unreachable_objects", []), [])

    def test_list_walls_returns_empty_list_not_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        fake.list_walls = lambda: {
            "status": 200,
            "body": {
                "event_stream_items": [{"walls": [], "unreachable_objects": []}],
                "event_stream_count": 1,
            },
        }
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_walls()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 0)


if __name__ == "__main__":
    unittest.main()
