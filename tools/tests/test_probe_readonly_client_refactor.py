from __future__ import annotations

from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class ProbeReadOnlyClientRefactorTests(unittest.TestCase):
    def test_probe_uses_reusable_client_for_transport_helpers(self) -> None:
        source = (TOOLS_DIR / "axxon_api_probe.py").read_text(encoding="utf-8")
        self.assertIn("from axxon_api_client import AxxonApiClient, config_from_args", source)
        self.assertIn("self.client = AxxonApiClient(config_from_args(args))", source)
        self.assertIn("return self.client.http_request(", source)
        self.assertNotIn("import base64", source)
        self.assertNotIn("import urllib.request", source)
        self.assertNotIn("import urllib.error", source)

    def test_readonly_sweep_uses_client_directly_not_probe_transport(self) -> None:
        source = (TOOLS_DIR / "axxon_readonly_sweep.py").read_text(encoding="utf-8")
        self.assertIn("from axxon_api_client import AxxonApiClient, config_from_args", source)
        self.assertIn("self.client = AxxonApiClient(config_from_args(args))", source)
        self.assertNotIn("from axxon_api_probe import Probe", source)
        self.assertNotIn("self.probe = Probe(args)", source)
        self.assertNotIn("self.probe.channel", source)

    def test_readonly_sweep_has_precise_fixtures_for_known_fixable_warns(self) -> None:
        source = (TOOLS_DIR / "axxon_readonly_sweep.py").read_text(encoding="utf-8")
        self.assertIn("def security_role_id(self)", source)
        self.assertIn("def layout_id(self)", source)
        self.assertIn("fixture_axxonsoft_bl_security_SecurityService_ListObjectsPermissionsInfo", source)
        self.assertIn("fixture_axxonsoft_bl_layout_LayoutImagesManager_ListLayoutImages", source)


if __name__ == "__main__":
    unittest.main()
