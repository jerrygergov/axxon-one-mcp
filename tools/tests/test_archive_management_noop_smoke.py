from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ArchiveManagementNoopSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_confirmation(self) -> None:
        module = importlib.import_module("axxon_archive_management_noop_smoke")

        with mock.patch.object(
            sys,
            "argv",
            ["axxon_archive_management_noop_smoke.py", "--password", "pw"],
        ):
            with self.assertRaises(SystemExit):
                module.parse_args()

    def test_note_for_prefers_error_message_and_keys_fallback(self) -> None:
        module = importlib.import_module("axxon_archive_management_noop_smoke")
        smoke = object.__new__(module.ArchiveManagementNoopSmoke)

        self.assertEqual(smoke.note_for({"details": {"error": "NOT_FOUND"}}), "NOT_FOUND")
        self.assertEqual(smoke.note_for({"details": {"elapsed_ms": 12, "status": "PASS"}}), "keys=['elapsed_ms', 'status']")


if __name__ == "__main__":
    unittest.main()
