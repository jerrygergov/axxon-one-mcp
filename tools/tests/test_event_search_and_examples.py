from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class EventSearchRefactorTests(unittest.TestCase):
    def test_event_search_delegates_transport_to_reusable_client(self) -> None:
        source = (TOOLS_DIR / "axxon_event_search.py").read_text(encoding="utf-8")
        self.assertIn("from axxon_api_client import AxxonApiClient, config_from_args", source)
        self.assertNotIn("def ensure_stubs(self)", source)
        self.assertNotIn("def authenticate(self)", source)

    def test_setup_registers_export_event_body_type(self) -> None:
        module = importlib.import_module("axxon_event_search")

        class RecordingClient:
            def __init__(self):
                self.imported: list[str] = []

            def authenticate_grpc(self):
                pass

            def import_module(self, name):
                self.imported.append(name)
                return object()

        search = module.AxxonEventSearch.__new__(module.AxxonEventSearch)
        search.client = RecordingClient()
        search.pb = {}
        search.setup()
        self.assertTrue(any("ExportEvent" in name for name in search.client.imported))

    def test_examples_are_importable_and_expose_main(self) -> None:
        modules = [
            "examples.inventory_sync",
            "examples.event_search_summary",
            "examples.camera_archive_status",
            "examples.metadata_tracker_stream",
            "examples.http_grpc_vs_grpc",
        ]
        for module_name in modules:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertTrue(callable(getattr(module, "main", None)))


if __name__ == "__main__":
    unittest.main()
