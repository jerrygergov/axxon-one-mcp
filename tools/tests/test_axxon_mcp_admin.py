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


class FakeSecurityClient(FakeClient):
    def __init__(self, config: FakeConfig) -> None:
        super().__init__(config)
        self.calls: list[tuple[str, dict]] = []

    def security_list_roles(self, *, page_size: int = 100, page_token: str = "") -> dict:
        self.calls.append(("roles", {"page_size": page_size, "page_token": page_token}))
        if not page_token:
            return {
                "body": {
                    "roles": [
                        {"index": "role-admin", "name": "admin", "comment": "Administrators"},
                    ],
                    "next_page_token": "roles-2",
                }
            }
        return {"body": {"roles": [{"index": "role-operator", "name": "operator"}]}}

    def security_list_users(
        self,
        *,
        page_size: int = 100,
        page_token: str = "",
        role_ids: list[str] | None = None,
    ) -> dict:
        self.calls.append(
            ("users", {"page_size": page_size, "page_token": page_token, "role_ids": list(role_ids or [])})
        )
        if not page_token:
            return {
                "body": {
                    "users": [
                        {
                            "index": "user-root",
                            "login": "root",
                            "name": "Root",
                            "email": "root@example.invalid",
                            "password": marker("PASSWORD"),
                            "enabled": True,
                        },
                    ],
                    "user_assignments": [{"user_id": "user-root", "role_id": "role-admin"}],
                    "next_page_token": "users-2",
                }
            }
        return {
            "body": {
                "users": [{"index": "user-operator", "login": "operator", "enabled": False}],
                "user_assignments": [{"user_id": "user-operator", "role_id": "role-operator"}],
            }
        }

    def security_list_ldap_servers(self, *, page_size: int = 100, page_token: str = "") -> dict:
        self.calls.append(("ldap", {"page_size": page_size, "page_token": page_token}))
        return {"body": {"ldap_servers": []}}

    def security_get_policies(self) -> dict:
        self.calls.append(("policies", {}))
        return {
            "body": {
                "pwd_policy": [{"min_length": 12, "password_sample": marker("PASSWORD")}],
                "ip_filters": [{}, {}],
                "trusted_ip_list": [{}],
                "system_integrity_reaction_modes": ["notify"],
                "cloud_public_key": marker("LICENSE"),
            }
        }

    def security_list_global_permissions(self, role_ids: list[str]) -> dict:
        self.calls.append(("global_permissions", {"role_ids": list(role_ids)}))
        return {
            "body": {
                "permissions": {
                    role_ids[0]: {
                        "unrestricted_access": "UNRESTRICTED_ACCESS_NO",
                        "license_key": marker("LICENSE"),
                    }
                }
            }
        }

    def security_list_object_permissions_info(
        self,
        *,
        role_id: str,
        node_name: str,
        page_size: int = 50,
        page_token: str = "",
    ) -> dict:
        self.calls.append(
            (
                "object_permissions_info",
                {"role_id": role_id, "node_name": node_name, "page_size": page_size, "page_token": page_token},
            )
        )
        if not page_token:
            return {"body": {"items": [{"id": "camera", "display_name": "Camera"}], "next_page_token": "objects-2"}}
        return {"body": {"items": [{"id": "archive", "display_name": "Archive"}]}}

    def security_get_restricted_config(self) -> dict:
        self.calls.append(("restricted_config", {}))
        return {
            "body": {
                "current_user": {
                    "index": "user-root",
                    "login": "root",
                    "password": marker("PASSWORD"),
                    "serialNumber": marker("SERIAL"),
                },
                "current_roles": [{"index": "role-admin", "name": "admin"}],
                "all_roles": [{}, {}],
                "all_users": [{}, {}, {}],
                "pwd_policy": [{}],
                "system_integrity_reaction_modes": ["notify"],
            }
        }

    def node_name(self) -> str:
        self.calls.append(("node_name", {}))
        return "Server"


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


class AxxonMcpAdminSecurityReadTests(unittest.TestCase):
    def test_security_inventory_paginates_and_summarizes_without_sensitive_payloads(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        fake = FakeSecurityClient(FakeConfig())
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = admin.security_inventory(page_size=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["roles"]["count"], 2)
        self.assertEqual(result["users"]["count"], 2)
        self.assertEqual(result["users"]["enabled_count"], 1)
        self.assertEqual(result["users"]["assignment_count"], 2)
        self.assertEqual(result["ldap_servers"]["count"], 0)
        self.assertEqual(result["roles"]["items"][0]["role_id"], "role-admin")
        self.assertEqual(result["users"]["items"][0]["login"], "root")
        self.assertIn(("roles", {"page_size": 1, "page_token": "roles-2"}), fake.calls)
        self.assertIn(("users", {"page_size": 1, "page_token": "users-2", "role_ids": []}), fake.calls)
        self.assertNotIn("root@example.invalid", str(result))
        self.assertNotIn(marker("PASSWORD"), str(result))

    def test_security_inventory_can_skip_sections(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        fake = FakeSecurityClient(FakeConfig())
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = admin.security_inventory(include_users=False, include_ldap=False)

        self.assertEqual(result["roles"]["count"], 2)
        self.assertNotIn("users", result)
        self.assertNotIn("ldap_servers", result)
        self.assertFalse(any(call[0] == "users" for call in fake.calls))
        self.assertFalse(any(call[0] == "ldap" for call in fake.calls))

    def test_security_policy_summary_counts_sections_and_warns_without_ldap_fixture(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        fake = FakeSecurityClient(FakeConfig())
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = admin.security_policy_summary()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["password_policy_count"], 1)
        self.assertEqual(result["ip_filter_count"], 2)
        self.assertEqual(result["trusted_ip_count"], 1)
        self.assertEqual(result["ldap"]["status"], "fixture-needed")
        self.assertEqual(result["ldap"]["servers_count"], 0)
        self.assertNotIn(marker("PASSWORD"), str(result))
        self.assertNotIn(marker("LICENSE"), str(result))

    def test_role_permissions_summarizes_global_and_object_permission_pages(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        fake = FakeSecurityClient(FakeConfig())
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = admin.role_permissions("role-admin", page_size=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["role_id"], "role-admin")
        self.assertEqual(result["global"]["roles_count"], 1)
        self.assertEqual(result["objects"]["count"], 2)
        self.assertEqual(result["objects"]["items"][0]["id"], "camera")
        self.assertIn(
            (
                "object_permissions_info",
                {"role_id": "role-admin", "node_name": "Server", "page_size": 1, "page_token": "objects-2"},
            ),
            fake.calls,
        )
        self.assertNotIn(marker("LICENSE"), str(result))

    def test_current_user_security_summarizes_restricted_config(self) -> None:
        module = importlib.import_module("axxon_mcp_admin")
        fake = FakeSecurityClient(FakeConfig())
        admin = module.AxxonMcpAdmin(
            client_factory=lambda config: fake,
            config_factory=lambda: FakeConfig(),
        )

        result = admin.current_user_security()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["current_user"]["user_id"], "user-root")
        self.assertEqual(result["current_user"]["login"], "root")
        self.assertEqual(result["current_roles"]["count"], 1)
        self.assertEqual(result["all_roles_count"], 2)
        self.assertEqual(result["all_users_count"], 3)
        self.assertNotIn(marker("PASSWORD"), str(result))
        self.assertNotIn(marker("SERIAL"), str(result))


if __name__ == "__main__":
    unittest.main()
