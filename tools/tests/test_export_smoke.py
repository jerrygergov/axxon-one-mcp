from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class ExportSmokeTests(unittest.TestCase):
    def test_builds_snapshot_export_options(self) -> None:
        module = importlib.import_module("axxon_export_smoke")

        class Fake:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        archive_mode = SimpleNamespace(Source=Fake)
        snapshot_type = SimpleNamespace(JPEG=1)
        export_pb2 = SimpleNamespace(
            Options=Fake,
            ArchiveMode=lambda **kwargs: Fake(**kwargs),
            SnapshotType=lambda **kwargs: Fake(**kwargs),
            CommonSetting=Fake,
        )
        export_pb2.ArchiveMode.Source = archive_mode.Source
        export_pb2.SnapshotType.JPEG = snapshot_type.JPEG

        request = module.build_snapshot_export_options(
            export_pb2,
            camera_ap="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            storage_ap="hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
            timestamp="20260511T080411.155000",
            file_name="codex-export-smoke-test",
            max_file_size=1048576,
        )

        self.assertEqual(request.kwargs["archive"].kwargs["start_timestamp"], "20260511T080411.155000")
        self.assertEqual(request.kwargs["snapshot"].kwargs["format"], 1)
        self.assertEqual(request.kwargs["settings"][0].kwargs["file_name"], "codex-export-smoke-test")
        self.assertFalse(request.kwargs["store_result_by_export_agent"])

    def test_builds_live_stop_export_options(self) -> None:
        module = importlib.import_module("axxon_export_smoke")

        class Fake:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeDuration:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        export_pb2 = SimpleNamespace(
            Options=Fake,
            LiveMode=lambda **kwargs: Fake(**kwargs),
            StreamType=lambda **kwargs: Fake(**kwargs),
            StreamSetting=Fake,
            CommonSetting=Fake,
        )
        export_pb2.LiveMode.Source = Fake
        export_pb2.StreamType.MP4 = 4
        duration_pb2 = SimpleNamespace(Duration=FakeDuration)

        request = module.build_live_stop_export_options(
            export_pb2,
            duration_pb2,
            camera_ap="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            file_name="codex-export-stop-test",
            duration_seconds=30,
            max_file_size=1048576,
        )

        self.assertEqual(request.kwargs["live"].kwargs["duration"].kwargs["seconds"], 30)
        self.assertEqual(request.kwargs["stream"].kwargs["format"], 4)
        self.assertTrue(request.kwargs["stream"].kwargs["settings"][0].kwargs["reject_audio"])

    def test_parse_requires_mutation_confirmation(self) -> None:
        module = importlib.import_module("axxon_export_smoke")

        with mock.patch.object(sys, "argv", ["axxon_export_smoke.py", "--password", "pw"]):
            with self.assertRaises(SystemExit):
                module.parse_args()


if __name__ == "__main__":
    unittest.main()
