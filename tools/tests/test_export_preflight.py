from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ExportPreflightTests(unittest.TestCase):
    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_export_preflight")
        names = {item["rpc"] for item in module.EXPORT_MUTATIONS_REQUIRING_APPROVAL}

        self.assertIn("ExportService.StartSession", names)
        self.assertIn("ExportService.DownloadFile", names)
        self.assertIn("ExportService.StopSession", names)
        self.assertIn("ExportService.DestroySession", names)
        self.assertIn("DomainSettingsService.UpdateExportSettings", names)

    def test_export_agent_discovery_summary_is_count_and_shape_only(self) -> None:
        module = importlib.import_module("axxon_export_preflight")
        summary = module.export_agent_summary(
            [
                {"access_point": "hosts/Server/ExportAgent.1", "display_name": "Export Agent"},
                {"access_point": "hosts/Server/NotExport.1", "secret": "value"},
            ]
        )

        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["access_point_lengths"], [24, 26])
        self.assertNotIn("secret", str(summary).lower())


if __name__ == "__main__":
    unittest.main()
