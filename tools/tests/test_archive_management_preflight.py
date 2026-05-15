from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ArchiveManagementPreflightTests(unittest.TestCase):
    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_archive_management_preflight")
        names = {item["rpc"] for item in module.ARCHIVE_MUTATIONS_REQUIRING_APPROVAL}

        self.assertIn("ArchiveService.FormatVolumes", names)
        self.assertIn("ArchiveService.Reindex", names)
        self.assertIn("ArchiveService.CancelReindex", names)

    def test_volume_summary_redacts_size_to_counts_and_status(self) -> None:
        module = importlib.import_module("axxon_archive_management_preflight")
        summary = module.volume_state_summary(
            {
                "vol-1": {"state": "MOUNTED", "readonly": False, "used_bytes": "123", "capacity_bytes": "456"},
                "vol-2": {"state": "ERROR_STATE", "readonly": True, "used_bytes": "12", "capacity_bytes": "34"},
            }
        )

        self.assertEqual(summary["volume_count"], 2)
        self.assertEqual(summary["states"], {"MOUNTED": 1, "ERROR_STATE": 1})
        self.assertEqual(summary["readonly_count"], 1)
        self.assertNotIn("used_bytes", summary)


if __name__ == "__main__":
    unittest.main()
