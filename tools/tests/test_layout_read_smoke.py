from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class LayoutReadSmokeTests(unittest.TestCase):
    def test_layout_body_summary_extracts_map_arrangement(self) -> None:
        module = importlib.import_module("axxon_layout_read_smoke")
        summary = module.layout_body_summary(
            {
                "meta": {"layout_id": "layout-1"},
                "body": {
                    "display_name": "Map Layout",
                    "map_id": "map-1",
                    "map_view_mode": "MAP_VIEW_MODE_MAP_AND_LAYOUT",
                    "cells": {"1": {}, "2": {}},
                    "map_arrangement": {"zoom_value": 2, "is_label_on": False},
                },
            }
        )
        self.assertEqual(summary["layout_id"], "layout-1")
        self.assertEqual(summary["cells_count"], 2)
        self.assertTrue(summary["has_map_arrangement"])
        self.assertIn("zoom_value", summary["map_arrangement_keys"])

    def test_layout_body_summary_accepts_json_name_variant(self) -> None:
        module = importlib.import_module("axxon_layout_read_smoke")
        summary = module.layout_body_summary({"body": {"id": "layout-2", "mapArrangement": {"isLabelOn": True}}})
        self.assertEqual(summary["layout_id"], "layout-2")
        self.assertTrue(summary["has_map_arrangement"])


if __name__ == "__main__":
    unittest.main()
