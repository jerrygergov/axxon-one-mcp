from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local",
            grpc_port=20109,
            http_port=80,
            http_url="http://example.local",
            username="root",
            password="secret",
            tls_cn="Server",
            ca=Path("/tmp/ca.crt"),
            proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"),
            timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {
            "status": 200,
            "body": {"items": [], "walls": [], "cookie": "fake", "wall_id": "w-1", "seq_number": 1},
        }


class ViewObjectsWrappersTests(unittest.TestCase):
    def test_list_layouts_passes_view(self) -> None:
        c = _FakeClient()
        c.list_layouts(view="VIEW_MODE_ONLY_META")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.layout.LayoutManager.ListLayouts",
                {"view": "VIEW_MODE_ONLY_META"},
            ),
        )

    def test_batch_get_layouts_passes_items(self) -> None:
        c = _FakeClient()
        c.batch_get_layouts([{"layout_id": "lid", "etag": "e"}])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.layout.LayoutManager.BatchGetLayouts",
                {"items": [{"layout_id": "lid", "etag": "e"}]},
            ),
        )

    def test_layouts_on_view_passes_layouts(self) -> None:
        c = _FakeClient()
        c.layouts_on_view([{"layout_id": "lid", "layout_display_name": "n"}])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.layout.LayoutManager.LayoutsOnView",
                {"layouts": [{"layout_id": "lid", "layout_display_name": "n"}]},
            ),
        )

    def test_list_layout_images_passes_layout_id(self) -> None:
        c = _FakeClient()
        c.list_layout_images("lid")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages",
                {"layout_id": "lid"},
            ),
        )

    def test_batch_get_maps_passes_map_ids(self) -> None:
        c = _FakeClient()
        c.batch_get_maps(["m-1", "m-2"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.maps.MapService.BatchGetMaps",
                {"map_ids": ["m-1", "m-2"]},
            ),
        )

    def test_register_wall_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.register_wall(host_name="h", pid=1, ppid=2, name="n", display_name="d", data_bytes=b"abc")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.videowall.VideowallService.RegisterWall",
                {
                    "host_name": "h",
                    "pid": 1,
                    "ppid": 2,
                    "name": "n",
                    "display_name": "d",
                    "data": {"data": "YWJj"},
                },
            ),
        )

    def test_change_wall_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.change_wall(cookie="ck", data_bytes=b"d", seq_number=3)
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.videowall.VideowallService.ChangeWall",
                {"cookie": "ck", "data": {"data": "ZA=="}, "seq_number": 3},
            ),
        )

    def test_unregister_wall_passes_cookie(self) -> None:
        c = _FakeClient()
        c.unregister_wall("ck")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.videowall.VideowallService.UnregisterWall",
                {"cookie": "ck"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
