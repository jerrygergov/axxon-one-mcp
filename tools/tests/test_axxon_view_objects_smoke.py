from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class AxxonViewObjectsSmokeTests(unittest.TestCase):
    def test_sanitize_replaces_demo_host_recursively(self) -> None:
        module = importlib.import_module("axxon_view_objects_smoke")
        host = "demo.internal"
        raw = {
            "url": f"http://{host}/grpc",
            "cookie": "real-cookie-value",
            "intent": "change videowall data (cookie=<fake-cookie>, seq=0)",
            "nested": [host, {"wall_cookie": "another-real-cookie"}],
        }
        self.assertEqual(
            module.sanitize(raw, host),
            {
                "url": "http://<demo-host>/grpc",
                "cookie": "<demo-wall-cookie>",
                "intent": "change videowall data (cookie=<demo-wall-cookie>, seq=0)",
                "nested": ["<demo-host>", {"wall_cookie": "<demo-wall-cookie>"}],
            },
        )

    def test_wall_seq_helpers_read_first_and_last_seq(self) -> None:
        module = importlib.import_module("axxon_view_objects_smoke")
        self.assertEqual(module.first_wall_seq({"wall_seq_numbers": ["0"]}, fallback=9), 0)
        self.assertEqual(module.latest_wall_seq({"wall_seq_numbers": [0, "2"]}, fallback=9), 2)
        self.assertEqual(module.first_wall_seq({}, fallback=9), 9)
        self.assertEqual(module.latest_wall_seq({}, fallback=9), 9)


if __name__ == "__main__":
    unittest.main()
