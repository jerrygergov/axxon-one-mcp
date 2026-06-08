"""Phase 5H tests: AxxonMcpMetadata (live track sample + VMDA archived query)."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    tls_cn = "Server"
    host = "<demo-host>"
    grpc_port = 20109
    http_url = "http://<demo-host>"
    username = "<demo-user>"


# --- VMDA / metadata protobuf fakes -----------------------------------------

class FakeMsg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeVmdaPb:
    class ExecuteQueryRequest(FakeMsg):
        pass

    class ExecuteQueryTypedRequest(FakeMsg):
        pass


class FakeQueryPb:
    class QueryDescription(FakeMsg):
        pass

    class MotionInArea(FakeMsg):
        pass


class FakePrimitivePb:
    class Polyline(FakeMsg):
        pass

    class Point(FakeMsg):
        pass


class FakeMediaPb:
    class EndpointRef(FakeMsg):
        pass


class FakeMetadataPb:
    class PullMetadataRequest(FakeMsg):
        pass


class FakeVmdaStub:
    def __init__(self, intervals_pages):
        self.pages = intervals_pages
        self.last_request = None

    def ExecuteQueryTyped(self, request, timeout=None):
        self.last_request = request
        for p in self.pages:
            yield p


class FakeMetaStub:
    def __init__(self, frames):
        self.frames = frames

    def PullMetadata(self, requests, timeout=None):
        list(requests)
        for f in self.frames:
            yield f


class FakeClient:
    """Stub AxxonApiClient: serves inventory, PullMetadata frames, and VMDA pages."""

    def __init__(self, config, *, inventory=None, frames=None, vmda_pages=None):
        self.config = config
        self._inventory = inventory if inventory is not None else {
            "components": [
                {"access_point": "hosts/Server/AVDetector.112/SourceEndpoint.vmda"},
                {"access_point": "hosts/Server/AVDetector.1/SourceEndpoint.vmda"},
                {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
                {"access_point": "hosts/Server/VMDA_DB.0/Database"},
            ]
        }
        self._frames = frames or []
        self._vmda_pages = vmda_pages or []
        self.authenticated = 0

    def load_inventory(self):
        return self._inventory

    def authenticate_grpc(self):
        self.authenticated += 1

    def import_module(self, name):
        return {
            "axxonsoft.bl.metadata.MetadataService_pb2": FakeMetadataPb,
            "axxonsoft.bl.media.Media_pb2": FakeMediaPb,
            "axxonsoft.bl.vmda.VMDA_pb2": FakeVmdaPb,
            "axxonsoft.bl.vmda.Query_pb2": FakeQueryPb,
            "axxonsoft.bl.primitive.Primitives_pb2": FakePrimitivePb,
        }[name]

    def stub_from_proto(self, proto_path, service):
        if service == "MetadataService":
            return FakeMetaStub(self._frames)
        if service == "VMDAService":
            return FakeVmdaStub(self._vmda_pages)
        raise AssertionError(service)

    def message_to_dict(self, message):
        if isinstance(message, dict):
            return message
        return dict(getattr(message, "__dict__", {}))


def make(**kw):
    module = importlib.import_module("axxon_mcp_metadata")
    importlib.reload(module)
    mcp = module.AxxonMcpMetadata(
        client_factory=lambda config: FakeClient(config, **kw),
        config_factory=lambda: FakeConfig(),
    )
    mcp.connect_axxon_profile("env")
    return module, mcp


class MetadataToolTests(unittest.TestCase):
    """AC1-AC5."""

    def test_list_vmda_sources(self) -> None:
        """AC2: discovers the */SourceEndpoint.vmda access points from inventory."""
        _, mcp = make()
        r = mcp.list_vmda_sources()
        self.assertEqual(r["status"], "ok")
        self.assertIn("hosts/Server/AVDetector.112/SourceEndpoint.vmda", r["sources"])
        self.assertNotIn("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", r["sources"])

    def test_live_track_sample_shape_and_caps(self) -> None:
        """AC3/AC5: returns bounded tracklets with id/state/behavior/bbox; caps clamp."""
        frames = [
            {"config_update": {"max_channel_idle_ms": 15000}},
            {"sample": {"timestamp": "20260604T115854.820000", "tracklets": {"tracklets": [
                {"id": 88639, "state": "OBJECT_STATE_APPEARED", "behavior": "MOVING_OBJECT",
                 "rectangle": {"x": 0.35, "y": 0.60, "w": 0.05, "h": 0.08}},
                {"id": 88631, "state": "OBJECT_STATE_NORMAL", "behavior": "MOVING_OBJECT",
                 "rectangle": {"x": 0.1, "y": 0.2, "w": 0.03, "h": 0.04}},
            ]}}},
        ]
        _, mcp = make(frames=frames)
        r = mcp.live_track_sample("hosts/Server/AVDetector.112/SourceEndpoint.vmda", seconds=9999, limit=99999)
        self.assertEqual(r["status"], "ok")
        # caps clamp huge requests down to module maxima
        self.assertLessEqual(r["applied"]["seconds"], mcp.MAX_SECONDS)
        self.assertLessEqual(r["applied"]["limit"], mcp.MAX_TRACKLETS)
        ids = [t["id"] for t in r["tracklets"]]
        self.assertIn(88639, ids)
        first = r["tracklets"][0]
        for key in ("id", "state", "behavior", "bbox"):
            self.assertIn(key, first)

    def test_live_track_sample_error_is_clean(self) -> None:
        """AC5: a transport failure returns a clean error dict, not a raised stack."""
        module = importlib.import_module("axxon_mcp_metadata")
        importlib.reload(module)

        class Boom(FakeClient):
            def stub_from_proto(self, *a, **k):
                raise RuntimeError("connect failed to <demo-host>")

        mcp = module.AxxonMcpMetadata(
            client_factory=lambda config: Boom(config),
            config_factory=lambda: FakeConfig(),
        )
        mcp.connect_axxon_profile("env")
        r = mcp.live_track_sample("hosts/Server/AVDetector.112/SourceEndpoint.vmda", 5, 10)
        self.assertEqual(r["status"], "error")
        self.assertIn("message", r)

    def test_vmda_query_motion_in_area(self) -> None:
        """AC4: ExecuteQuery returns intervals with object bounding boxes and time ranges."""
        pages = [
            FakeMsg(intervals=[
                FakeMsg(limit={"begin_time": "20260530T223913.371000", "end_time": "20260530T230913.115000"},
                        objects=[{"id": "14", "left": 0.05, "right": 0.19, "bottom": 0.09},
                                 {"id": "12", "left": 0.43, "top": 0.46, "right": 0.52, "bottom": 0.54}]),
                FakeMsg(limit={"begin_time": "20260530T231000.000000", "end_time": "20260530T231100.000000"},
                        objects=[{"id": "20", "left": 0.5, "right": 0.6, "bottom": 0.38}]),
            ], progress="100"),
        ]
        module, mcp = make(vmda_pages=pages)
        r = mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="motion_in_area")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["query_type"], "motion_in_area")
        self.assertEqual(r["interval_count"], 2)
        self.assertEqual(r["object_count"], 3)
        self.assertEqual(r["intervals"][0]["begin"], "20260530T223913.371000")
        self.assertEqual(r["intervals"][0]["objects"][0]["id"], "14")

    def test_vmda_query_zero_results_ok(self) -> None:
        """AC4/AC8: an empty archive returns status ok with zero counts (not an error)."""
        _, mcp = make(vmda_pages=[])
        r = mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="motion_in_area")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["interval_count"], 0)
        self.assertEqual(r["object_count"], 0)

    def test_vmda_query_binding_uses_typed_query(self) -> None:
        """AC1/AC4: ExecuteQueryTyped binds access_point=VMDA_DB, relative camera, and a typed motion_in_area QueryDescription."""
        captured = {}

        module = importlib.import_module("axxon_mcp_metadata")
        importlib.reload(module)

        class CaptureClient(FakeClient):
            def stub_from_proto(self, proto_path, service):
                stub = super().stub_from_proto(proto_path, service)
                if service == "VMDAService":
                    orig = stub.ExecuteQueryTyped
                    def wrap(request, timeout=None):
                        for f in ("access_point", "camera_ID", "schema_ID", "query"):
                            captured[f] = getattr(request, f, None)
                        return orig(request, timeout=timeout)
                    stub.ExecuteQueryTyped = wrap
                return stub

        mcp = module.AxxonMcpMetadata(
            client_factory=lambda config: CaptureClient(config, vmda_pages=[]),
            config_factory=lambda: FakeConfig(),
        )
        mcp.connect_axxon_profile("env")
        mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="motion_in_area")
        self.assertEqual(captured["access_point"], "hosts/Server/VMDA_DB.0/Database")
        self.assertEqual(captured["camera_ID"], "AVDetector.1/SourceEndpoint.vmda")
        self.assertEqual(captured["schema_ID"], "vmda_schema")
        # query is a typed QueryDescription carrying a motion_in_area with a polygon
        qd = captured["query"]
        self.assertIsInstance(qd, FakeQueryPb.QueryDescription)
        self.assertIsInstance(qd.motion_in_area, FakeQueryPb.MotionInArea)
        self.assertGreaterEqual(len(qd.motion_in_area.area.points), 3)

    def test_vmda_query_polygon_points_passed_through(self) -> None:
        """AC2: a custom normalized polygon becomes the typed Polyline points."""
        captured = {}
        module = importlib.import_module("axxon_mcp_metadata")
        importlib.reload(module)

        class CaptureClient(FakeClient):
            def stub_from_proto(self, proto_path, service):
                stub = super().stub_from_proto(proto_path, service)
                if service == "VMDAService":
                    orig = stub.ExecuteQueryTyped
                    def wrap(request, timeout=None):
                        captured["query"] = getattr(request, "query", None)
                        return orig(request, timeout=timeout)
                    stub.ExecuteQueryTyped = wrap
                return stub

        mcp = module.AxxonMcpMetadata(
            client_factory=lambda config: CaptureClient(config, vmda_pages=[]),
            config_factory=lambda: FakeConfig(),
        )
        mcp.connect_axxon_profile("env")
        mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="motion_in_area",
                       polygon=[(0.1, 0.2), (0.8, 0.2), (0.5, 0.9)])
        pts = captured["query"].motion_in_area.area.points
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[0].x, 0.1)
        self.assertAlmostEqual(pts[0].y, 0.2)

    def test_vmda_query_missing_database_is_gap(self) -> None:
        """AC4: no VMDA database in inventory and none passed returns a clean gap."""
        _, mcp = make(vmda_pages=[], inventory={"components": [
            {"access_point": "hosts/Server/AVDetector.1/SourceEndpoint.vmda"},
        ]})
        r = mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="motion_in_area")
        self.assertEqual(r["status"], "gap")

    def test_vmda_query_bad_type_refused(self) -> None:
        """AC4: an unsupported query_type returns a gap/error, not a crash."""
        _, mcp = make(vmda_pages=[])
        r = mcp.vmda_query("hosts/Server/AVDetector.1/SourceEndpoint.vmda", query_type="teleport")
        self.assertIn(r["status"], {"gap", "error"})


if __name__ == "__main__":
    unittest.main()
