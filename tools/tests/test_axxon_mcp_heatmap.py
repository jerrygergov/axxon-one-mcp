from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_heatmap as module


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


class _BuildResp:
    def __init__(self):
        self.result = True
        self.heatmap = [1, 2, 3]
        self.image_data = b"PNGDATA-not-returned"


class _QueryResp:
    def __init__(self, progress):
        self.progress = progress
        self.heatmap = [9, 9]


class _SizeInt:
    def __init__(self, width=0, height=0):
        self.width = width
        self.height = height


class _Polyline:
    def __init__(self, points=None):
        self.points = points or []


class _Point:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


class _HeatmapPb2:
    RESULT_TYPE_IMAGE = 1

    class BuildHeatmapRequest:
        def __init__(self, **kw):
            self.kw = kw

    class BuildEventsHeatmapRequest:
        def __init__(self, **kw):
            self.kw = kw

    class BuildFloorHeatmapRequest:
        def __init__(self, **kw):
            self.kw = kw

    class ExecuteHeatmapQueryRequest:
        def __init__(self, **kw):
            self.kw = kw

    class ExecuteHeatmapQueryTypedRequest:
        def __init__(self, **kw):
            self.kw = kw

    class DataSource:
        def __init__(self, **kw):
            self.kw = kw

    class DataSourceArray:
        def __init__(self, data_sources=None):
            self.data_sources = data_sources or []


class _PrimPb2:
    SizeInt = _SizeInt
    Polyline = _Polyline
    Point = _Point


class _EventsPb2:
    class SearchFilterArray:
        def __init__(self, **kw):
            self.kw = kw


class _VmdaPb2:
    class QueryDescription:
        def __init__(self, **kw):
            self.kw = kw

    class MotionInArea:
        def __init__(self, **kw):
            self.kw = kw


_PB2_BY_NAME = {
    module.HEATMAP_PB2: _HeatmapPb2,
    module.PRIMITIVE_PB2: _PrimPb2,
    module.EVENTS_PB2: _EventsPb2,
    module.VMDA_QUERY_PB2: _VmdaPb2,
}


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def BuildHeatmap(self, request, timeout=None):
        self._rec.append(("BuildHeatmap",))
        return _BuildResp()

    def BuildEventsHeatmap(self, request, timeout=None):
        self._rec.append(("BuildEventsHeatmap",))
        return _BuildResp()

    def BuildFloorHeatmap(self, request, timeout=None):
        self._rec.append(("BuildFloorHeatmap",))
        return _BuildResp()

    def ExecuteHeatmapQuery(self, request, timeout=None):
        self._rec.append(("ExecuteHeatmapQuery",))
        return iter([_QueryResp("p1"), _QueryResp("p2")])

    def ExecuteHeatmapQueryTyped(self, request, timeout=None):
        self._rec.append(("ExecuteHeatmapQueryTyped",))
        return iter([_QueryResp("t1"), _QueryResp("t2")])


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _PB2_BY_NAME[name]


def _inst():
    inst = module.AxxonMcpHeatmap(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    inst.heatmap_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_build_heatmap_metadata_only(self) -> None:
        out = _inst().build_heatmap(camera_id="cam", start_time="20260101T000000.0", end_time="20260101T010000.0")
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["result"])
        self.assertEqual(out["heatmap_cells"], 3)
        self.assertEqual(out["image_bytes"], len(b"PNGDATA-not-returned"))
        self.assertNotIn("PNGDATA", str(out))

    def test_build_heatmap_missing_args_no_wire(self) -> None:
        inst = _inst()
        out = inst.build_heatmap(camera_id="", start_time="", end_time="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_build_events_heatmap_ok(self) -> None:
        out = _inst().build_events_heatmap(start_time="20260101T000000.0", end_time="20260101T010000.0")
        self.assertEqual(out["tool"], "build_events_heatmap")
        self.assertTrue(out["result"])

    def test_build_floor_heatmap_ok(self) -> None:
        out = _inst().build_floor_heatmap(camera_id="cam", start_time="a", end_time="b", map_guid="g")
        self.assertEqual(out["map_guid"], "g")
        self.assertTrue(out["result"])

    def test_execute_heatmap_query_bounded(self) -> None:
        out = _inst().execute_heatmap_query(camera_id="cam", start_time="a", end_time="b", max_responses=1)
        self.assertEqual(out["responses"], 1)
        self.assertEqual(out["last_progress"], "p1")

    def test_execute_heatmap_query_typed_ok(self) -> None:
        out = _inst().execute_heatmap_query_typed(camera_id="cam", start_time="a", end_time="b")
        self.assertEqual(out["responses"], 2)
        self.assertEqual(out["last_progress"], "t2")

    def test_execute_query_missing_args_no_wire(self) -> None:
        inst = _inst()
        out = inst.execute_heatmap_query(camera_id="", start_time="", end_time="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


if __name__ == "__main__":
    unittest.main()
