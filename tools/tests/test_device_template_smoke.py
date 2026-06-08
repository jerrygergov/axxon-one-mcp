from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class DeviceTemplateSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_device_template_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x"])
        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_device_template_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        self.assertTrue(module.mutation_approved(args))

    def test_template_ids_are_codex_prefixed(self) -> None:
        module = importlib.import_module("axxon_device_template_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        smoke = module.DeviceTemplateSmoke(args)
        smoke.created_camera_uid = "hosts/Server/DeviceIpint.1"
        smoke.create_template = lambda: None
        smoke.created_template_id = ""
        body = smoke.template_body("codex-123", "name", 35.0, 45.0)
        self.assertEqual(body["id"], "codex-123")
        self.assertEqual(body["unit"]["type"], "DeviceIpint")
        self.assertEqual(body["unit"]["properties"][0]["id"], "geoLocationLatitude")


if __name__ == "__main__":
    unittest.main()
