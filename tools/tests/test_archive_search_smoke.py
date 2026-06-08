from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class ArchiveSearchSmokeTests(unittest.TestCase):
    def test_search_modes_cover_pdf_families(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        modes = set(module.search_modes())
        self.assertTrue({"lpr", "face", "vmda", "heatmap", "stranger"}.issubset(modes))
        self.assertTrue({"legacy_auto", "legacy_vmda", "legacy_heatmap"}.issubset(modes))
        self.assertIn("build_heatmap", modes)
        self.assertIn("face_appearance_rate", modes)

    def test_default_vmda_query_is_all_frame_polygon(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        query = module.default_vmda_query()
        self.assertIn("polygon(0,0,1,0,1,1,0,1)", query)
        self.assertIn("vmda_object", query)

    def test_builds_execute_heatmap_query_request(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")

        class FakeRequest:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        heatmap_pb2 = SimpleNamespace(ExecuteHeatmapQueryRequest=FakeRequest)
        request = module.build_execute_heatmap_query_request(
            heatmap_pb2,
            camera_id="hosts/Server/AVDetector.1/SourceEndpoint.vmda",
            begin="20260502T080000.000000",
            end="20260502T090000.000000",
            query="",
        )

        self.assertEqual(request.kwargs["camera_ID"], "hosts/Server/AVDetector.1/SourceEndpoint.vmda")
        self.assertEqual(request.kwargs["dt_posix_start_time"], "20260502T080000.000000")
        self.assertEqual(request.kwargs["dt_posix_end_time"], "20260502T090000.000000")
        self.assertEqual(request.kwargs["query"], "")

    def test_builds_bounded_build_heatmap_request(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")

        class FakeRequest:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeSize:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        heatmap_pb2 = SimpleNamespace(
            BuildHeatmapRequest=FakeRequest,
            RESULT_TYPE_IMAGE=1,
        )
        primitive_pb2 = SimpleNamespace(SizeInt=FakeSize)
        request = module.build_build_heatmap_request(
            heatmap_pb2,
            primitive_pb2,
            builder_ap="hosts/Server/HeatMapBuilder.0/HeatMapBuilder",
            camera_id="hosts/Server/AVDetector.1/SourceEndpoint.vmda",
            begin="20260502T080000.000000",
            end="20260502T090000.000000",
            query="",
            image_width=64,
            image_height=48,
            mask_width=32,
            mask_height=24,
        )

        self.assertEqual(request.kwargs["access_point"], "hosts/Server/HeatMapBuilder.0/HeatMapBuilder")
        self.assertEqual(request.kwargs["camera_ID"], "hosts/Server/AVDetector.1/SourceEndpoint.vmda")
        self.assertEqual(request.kwargs["result_type"], 1)
        self.assertEqual(request.kwargs["image_size"].kwargs, {"width": 64, "height": 48})
        self.assertEqual(request.kwargs["mask_size"].kwargs, {"width": 32, "height": 24})

    def test_heatmap_builder_fallback_uses_node_name(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.inventory = {"components": []}
        smoke.node_name = "Server"

        self.assertEqual(
            smoke.heatmap_builder_access_point(),
            "hosts/Server/HeatMapBuilder.0/HeatMapBuilder",
        )

    def test_legacy_auto_body_uses_plate_predicate_when_supplied(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.args = SimpleNamespace(predicate="ABC*", face_accuracy=None, face_image=None, stranger_threshold=None, stranger_op="")

        self.assertEqual(smoke.legacy_search_body("auto"), {"body": {"plate": "ABC*"}, "query": "", "headers": {}})

    def test_legacy_auto_falls_back_to_empty_body(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.args = SimpleNamespace(predicate="", face_accuracy=None, face_image=None, stranger_threshold=None, stranger_op="")

        self.assertEqual(smoke.legacy_search_body("auto"), {"body": {}, "query": "", "headers": {}})

    def test_legacy_face_search_allows_empty_post_body(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.args = SimpleNamespace(predicate="", face_accuracy=0.7, face_image=None, stranger_threshold=None, stranger_op="")

        self.assertEqual(smoke.legacy_search_body("face"), {"body": None, "query": "accuracy=0.7", "headers": {}})

    def test_legacy_face_search_with_image_uses_json_base64_body(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        fixture = Path("/tmp/axxon_archive_search_face_unit.jpg")
        fixture.write_bytes(b"\xff\xd8\xff")
        try:
            smoke.args = SimpleNamespace(
                predicate="",
                face_accuracy=0.7,
                face_image=str(fixture),
                stranger_threshold=None,
                stranger_op="",
            )

            self.assertEqual(
                smoke.legacy_search_body("face", "Server/AVDetector.93/EventSupplier"),
                {
                    "body": {"image": "/9j/", "sources": ["hosts/Server/AVDetector.93/EventSupplier"]},
                    "query": "accuracy=0.7",
                    "headers": {},
                },
            )
        finally:
            fixture.unlink(missing_ok=True)

    def test_legacy_stranger_search_uses_threshold_and_direction(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.args = SimpleNamespace(predicate="", face_accuracy=0.8, face_image=None, stranger_threshold=0.6, stranger_op="gt")

        self.assertEqual(
            smoke.legacy_search_body("stranger"),
            {"body": None, "query": "accuracy=0.8&threshold=0.6&op=gt", "headers": {}},
        )

    def test_face_event_supplier_prefers_camera_detector_entries(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        smoke = object.__new__(module.ArchiveSearchSmoke)
        smoke.fixtures = {}
        smoke.client = SimpleNamespace(http_token="")
        smoke.inventory = {
            "cameras": [
                {
                    "detectors": [
                        {
                            "accessPoint": "hosts/Server/AVDetector.93/EventSupplier",
                            "type": "VaFaceDetector",
                            "events": ["TargetList", "faceAppeared"],
                        }
                    ]
                }
            ],
            "components": [],
        }

        self.assertEqual(smoke.face_event_supplier(), "hosts/Server/AVDetector.93/EventSupplier")

    def test_build_face_appearance_rate_body_uses_base64_image(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")

        self.assertEqual(module.build_face_appearance_rate_body(b"\xff\xd8\xff"), {"image": "/9j/"})
