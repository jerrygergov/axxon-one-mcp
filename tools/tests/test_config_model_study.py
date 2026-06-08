from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ConfigModelStudyTests(unittest.TestCase):
    def test_study_groups_cover_mutation_object_families(self) -> None:
        module = importlib.import_module("axxon_config_model_study")
        groups = set(module.study_groups())
        self.assertTrue({"domain", "unit_tree", "factories", "properties", "similar_units", "appdata_detectors"}.issubset(groups))

    def test_sensitive_property_filter_mentions_known_secret_fields(self) -> None:
        module = importlib.import_module("axxon_config_model_study")
        fields = module.sensitive_property_tokens()
        self.assertIn("password", fields)
        self.assertIn("serial", fields)

    def test_unit_sort_key_orders_numeric_display_ids_first(self) -> None:
        module = importlib.import_module("axxon_config_model_study")
        numeric = module.unit_sort_key({"display_id": "22", "uid": "b"})
        text = module.unit_sort_key({"display_id": "Pose 1", "uid": "a"})
        self.assertLess(numeric, text)
