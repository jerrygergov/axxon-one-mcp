from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ConfigMutationSmokeTests(unittest.TestCase):
    def test_mutation_groups_cover_config_object_families(self) -> None:
        module = importlib.import_module("axxon_config_mutation_smoke")
        groups = set(module.mutation_groups())
        self.assertTrue({"archive", "camera", "av_detector", "av_detector_parameters", "appdata_detector", "appdata_visual_element"}.issubset(groups))

    def test_detector_scalar_change_prefers_pdf_style_parameters(self) -> None:
        module = importlib.import_module("axxon_config_mutation_smoke")
        properties = [
            {"id": "display_name", "readonly": False, "type": "string", "value_string": "codex"},
            {"id": "period", "readonly": False, "type": "int32", "value_int32": 0, "range_constraint": {"min_int": 0, "max_int": 65535}},
            {"id": "enabled", "readonly": False, "type": "bool", "value_bool": True},
        ]

        change = module.detector_scalar_change(properties)

        self.assertEqual(change, {"id": "period", "value_int32": 1})

    def test_visual_element_change_supports_rectangle(self) -> None:
        module = importlib.import_module("axxon_config_mutation_smoke")
        child = {
            "properties": [
                {"id": "rectangle", "readonly": False, "value_rectangle": {"x": 0.01, "y": 0.01, "w": 0.98, "h": 0.98, "index": 0}}
            ]
        }

        change = module.visual_element_parameter_change(child)

        self.assertEqual(change["id"], "rectangle")
        self.assertEqual(change["value_rectangle"]["index"], 0)

    def test_optional_visual_missing_is_reportable(self) -> None:
        module = importlib.import_module("axxon_config_mutation_smoke")

        self.assertEqual(module.no_visual_parameter_summary("AVDetector"), {"visual_owner_type": "AVDetector", "visual_skipped": "no VisualElement child"})

    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_config_mutation_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x"])
        self.assertFalse(module.mutation_approved(args))
