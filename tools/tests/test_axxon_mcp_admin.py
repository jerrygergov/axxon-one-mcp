from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


def marker(name: str) -> str:
    return name + "_SHOULD_NOT_LEAK"


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = marker("CONFIG_PASSWORD")
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    def __init__(self, config: FakeConfig) -> None:
        self.config = config


class AxxonMcpAdminScaffoldTests(unittest.TestCase):
    def test_module_constants_name_phase_5f_a_tools(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        expected = {
            "admin_connect_axxon_profile",
            "security_inventory",
            "security_policy_summary",
            "role_permissions",
            "current_user_security",
            "license_status",
            "time_status",
            "system_health",
            "domain_event_subscribe",
            "node_event_subscribe",
            "schedule_descriptor_get",
        }
        self.assertTrue(expected.issubset(set(module.ADMIN_TOOL_NAMES)))
        self.assertEqual(module.ADMIN_MODE, "read-only")

    def test_admin_connect_axxon_profile_reports_redacted_env_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )

        profile = admin.admin_connect_axxon_profile("env")

        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], module.ADMIN_MODE)
        self.assertEqual(profile["profile"]["host"], "example.local")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn(marker("CONFIG_PASSWORD"), str(profile))

    def test_admin_connect_axxon_profile_rejects_non_env_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: FakeClient(config),
            config_factory=lambda: FakeConfig(),
        )

        rejected = admin.admin_connect_axxon_profile("other")

        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(rejected["profile_name"], "other")

    def test_ensure_client_connects_env_profile_once(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        created: list[FakeConfig] = []

        def client_factory(config: FakeConfig) -> FakeClient:
            created.append(config)
            return FakeClient(config)

        admin = module.AxxonMcpAdmin(
            client_factory=client_factory,
            config_factory=lambda: FakeConfig(),
        )

        first = admin.ensure_client()
        second = admin.ensure_client()

        self.assertIs(first, second)
        self.assertEqual(len(created), 1)
        self.assertEqual(admin.profile_name, "env")

    def test_redact_admin_secrets_handles_nested_security_values(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        raw = {
            "login": "operator",
            "password": marker("PASSWORD"),
            "authorization": "Bear" + "er " + marker("TOKEN"),
            "tfa_secret_key": marker("TFA"),
            "license_key": marker("LICENSE"),
            "serialNumber": marker("SERIAL"),
            "host": {
                "hardwareFingerprint": marker("FINGERPRINT"),
                "machine_id": marker("MACHINE_ID"),
                "display_name": "Server",
            },
            "sessions": [
                {"session_token": marker("SESSION")},
                {"state": "ok"},
            ],
        }

        redacted = module.redact_admin_secrets(raw)

        self.assertEqual(redacted["login"], "operator")
        self.assertEqual(redacted["password"], "<redacted>")
        self.assertEqual(redacted["authorization"], "<redacted>")
        self.assertEqual(redacted["tfa_secret_key"], "<redacted>")
        self.assertEqual(redacted["license_key"], "<redacted>")
        self.assertEqual(redacted["serialNumber"], "<redacted>")
        self.assertEqual(redacted["host"]["hardwareFingerprint"], "<redacted>")
        self.assertEqual(redacted["host"]["machine_id"], "<redacted>")
        self.assertEqual(redacted["host"]["display_name"], "Server")
        self.assertEqual(redacted["sessions"][0]["session_token"], "<redacted>")
        self.assertEqual(redacted["sessions"][1]["state"], "ok")
        self.assertNotIn("SHOULD_NOT_LEAK", str(redacted))

    def test_redact_admin_text_replaces_bearer_and_assignments(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        text = (
            "failed with Bear" + "er " + marker("TOKEN") + " "
            "pass" + "word=" + marker("PASSWORD") + " tfa_code=123456 "
            "license_key=" + marker("LICENSE") + " "
            "serial_number=" + marker("SERIAL") + " "
            "hardware_fingerprint=" + marker("FINGERPRINT")
        )

        redacted = module.redact_admin_text(text)

        self.assertIn("Bearer <redacted>", redacted)
        self.assertNotIn(marker("TOKEN"), redacted)
        self.assertNotIn(marker("PASSWORD"), redacted)
        self.assertNotIn(marker("LICENSE"), redacted)
        self.assertNotIn(marker("SERIAL"), redacted)
        self.assertNotIn(marker("FINGERPRINT"), redacted)


if __name__ == "__main__":
    unittest.main()
