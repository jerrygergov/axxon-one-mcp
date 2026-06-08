from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class HttpExportSmokeTests(unittest.TestCase):
    def test_parse_requires_mutation_confirmation(self) -> None:
        module = importlib.import_module("axxon_http_export_smoke")

        with mock.patch.object(sys, "argv", ["axxon_http_export_smoke.py", "--password", "pw"]):
            with self.assertRaises(SystemExit):
                module.parse_args()

    def test_parser_accepts_explicit_confirmation(self) -> None:
        module = importlib.import_module("axxon_http_export_smoke")

        argv = [
            "axxon_http_export_smoke.py",
            "--password",
            "pw",
            "--i-understand-this-mutates",
            "--confirm",
            module.HTTP_EXPORT_CONFIRMATION,
        ]
        with mock.patch.object(sys, "argv", argv):
            args = module.parse_args()

        self.assertTrue(args.i_understand_this_mutates)
        self.assertEqual(args.confirm, module.HTTP_EXPORT_CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
