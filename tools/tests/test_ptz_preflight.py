from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class PtzPreflightTests(unittest.TestCase):
    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_ptz_preflight")
        names = {item["rpc"] for item in module.PTZ_MUTATIONS_REQUIRING_APPROVAL}

        self.assertIn("TelemetryService.AcquireSessionId", names)
        self.assertIn("TelemetryService.Move", names)
        self.assertIn("TelemetryService.AbsoluteMove", names)
        self.assertIn("TelemetryService.GoPreset", names)
        self.assertIn("TagAndTrackService.SetMode", names)
        self.assertIn("TagAndTrackService.FollowTrack", names)

    def test_telemetry_summary_is_count_and_shape_only(self) -> None:
        module = importlib.import_module("axxon_ptz_preflight")
        summary = module.telemetry_summary(
            [
                {"access_point": "hosts/Server/Telemetry.1", "display_name": "PTZ"},
                {"access_point": "hosts/Server/Telemetry.22", "secret": "value"},
            ]
        )

        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["access_point_lengths"], [24, 25])
        self.assertNotIn("secret", str(summary).lower())


if __name__ == "__main__":
    unittest.main()
