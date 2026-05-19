from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_VALUE_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self, config: FakeConfig) -> None:
        self.config = config


class AxxonMcpDetectorArchiveTests(unittest.TestCase):
    def test_module_loads_with_phase_5e_constants(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        self.assertEqual(module.DETECTOR_LIST_LIMIT_CAP, 200)
        self.assertEqual(module.METADATA_SAMPLE_TIMEOUT_DEFAULT, 5.0)
        self.assertEqual(module.METADATA_SAMPLE_TIMEOUT_CAP, 30.0)
        self.assertEqual(module.METADATA_SAMPLE_LIMIT_DEFAULT, 20)
        self.assertEqual(module.METADATA_SAMPLE_LIMIT_CAP, 200)
        self.assertIn("AVDetector", module.DETECTOR_UNIT_TYPES)
        self.assertIn("AppDataDetector", module.DETECTOR_UNIT_TYPES)
        self.assertIn("MotionDetection", module.KNOWN_DETECTOR_KINDS["AVDetector"])
        self.assertIn("MoveInZone", module.KNOWN_DETECTOR_KINDS["AppDataDetector"])

    def test_detector_archive_connect_axxon_profile_reports_redacted_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        archive = module.AxxonMcpDetectorArchive(
            client_factory=lambda config: FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )

        profile = archive.detector_archive_connect_axxon_profile("env")

        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertEqual(profile["profile"]["host"], "example.local")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertIsInstance(archive.client, FakeClient)
        self.assertEqual(archive.profile_name, "env")
        self.assertNotIn("CONFIG_VALUE_SHOULD_NOT_LEAK", str(profile))

        rejected = archive.detector_archive_connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(rejected["profile_name"], "other")

    def test_ensure_client_connects_env_profile_once(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        calls: list[str] = []

        def client_factory(config: FakeConfig) -> FakeClient:
            calls.append(config.host)
            return FakeClient(config)

        archive = module.AxxonMcpDetectorArchive(
            client_factory=client_factory,
            config_factory=lambda: FakeConfig(),
        )

        first = archive.ensure_client()
        second = archive.ensure_client()

        self.assertIs(first, second)
        self.assertEqual(calls, ["example.local"])

    def test_sensitive_property_redaction_normalizes_nested_values(self) -> None:
        module = importlib.import_module("axxon_mcp_detector_archive")
        raw: dict[str, Any] = {
            "display_name": "Detector",
            "properties": {
                "password": "PROPERTY_VALUE_SHOULD_NOT_LEAK",
                "apiToken": "TOKEN_VALUE_SHOULD_NOT_LEAK",
                "camera": {
                    "serialNumber": "SERIAL_VALUE_SHOULD_NOT_LEAK",
                    "enabled": True,
                },
                "zones": [
                    {"license": "LICENSE_VALUE_SHOULD_NOT_LEAK"},
                    {"name": "safe"},
                ],
            },
        }

        redacted = module.redact_sensitive_properties(raw)

        self.assertEqual(redacted["display_name"], "Detector")
        self.assertEqual(redacted["properties"]["password"], "<redacted>")
        self.assertEqual(redacted["properties"]["apiToken"], "<redacted>")
        self.assertEqual(redacted["properties"]["camera"]["serialNumber"], "<redacted>")
        self.assertTrue(redacted["properties"]["camera"]["enabled"])
        self.assertEqual(redacted["properties"]["zones"][0]["license"], "<redacted>")
        self.assertEqual(redacted["properties"]["zones"][1]["name"], "safe")
        self.assertNotIn("PROPERTY_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("TOKEN_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("SERIAL_VALUE_SHOULD_NOT_LEAK", str(redacted))
        self.assertNotIn("LICENSE_VALUE_SHOULD_NOT_LEAK", str(redacted))


if __name__ == "__main__":
    unittest.main()
