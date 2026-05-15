from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FixtureDiscoveryTests(unittest.TestCase):
    def test_discovery_declares_fixture_types(self) -> None:
        module = importlib.import_module("axxon_fixture_discovery")
        fixture_types = set(module.fixture_types())
        self.assertTrue({"ptz", "control_panel", "water_level", "export_agent", "map", "template"}.issubset(fixture_types))
        self.assertTrue({"client_http", "embeddable_host", "rtsp_playback"}.issubset(fixture_types))

    def test_export_agent_units_from_config_tree(self) -> None:
        module = importlib.import_module("axxon_fixture_discovery")
        data = {
            "units": [
                {
                    "uid": "hosts/Server",
                    "units": [
                        {"uid": "hosts/Server/MMExportAgent.0", "type": "MMExportAgent"},
                        {"uid": "hosts/Server/Other.0", "type": "Other"},
                    ],
                }
            ]
        }
        agents = module.export_agent_units_from_list_units(data)
        self.assertEqual([item["uid"] for item in agents], ["hosts/Server/MMExportAgent.0"])

    def test_embeddable_signature_accepts_pdf_embedded_entrypoint(self) -> None:
        module = importlib.import_module("axxon_fixture_discovery")
        signature = module.embeddable_signature(
            url="http://example.invalid/embedded.html",
            status=200,
            content_type="text/html",
            size=856,
            text_prefix="<title>Video component</title><script src='./embedded.js'></script>",
        )

        self.assertTrue(signature["mentions_component"])
        self.assertTrue(signature["mentions_video"])
        self.assertTrue(signature["mentions_embed"])
