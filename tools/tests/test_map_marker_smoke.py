from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class MapMarkerSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_map_marker_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x"])
        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_map_marker_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        self.assertTrue(module.mutation_approved(args))

    def test_embedded_png_is_present(self) -> None:
        module = importlib.import_module("axxon_map_marker_smoke")
        self.assertTrue(module.PNG_1X1.startswith(b"\x89PNG"))
        self.assertGreater(len(module.PNG_1X1), 30)


if __name__ == "__main__":
    unittest.main()
