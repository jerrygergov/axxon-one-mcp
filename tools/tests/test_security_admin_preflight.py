from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class SecurityAdminPreflightTests(unittest.TestCase):
    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_security_admin_preflight")
        names = {item["rpc"] for item in module.SECURITY_MUTATIONS_REQUIRING_APPROVAL}

        self.assertIn("SecurityService.ChangeConfig", names)
        self.assertIn("SecurityService.SetGlobalPermissions", names)
        self.assertIn("SecurityService.SetObjectPermissions", names)
        self.assertIn("SecurityService.SetGroupsPermissions", names)
        self.assertIn("SecurityService.SetMacrosPermissions", names)

    def test_security_inventory_summary_avoids_sensitive_payloads(self) -> None:
        module = importlib.import_module("axxon_security_admin_preflight")
        summary = module.security_inventory_summary(
            roles=[{"index": "role-1", "name": "admin"}],
            users=[{"index": "user-1", "login": "root", "email": "root@example.invalid"}],
            ldap_servers=[{"index": "ldap-1", "password": "secret"}],
        )

        self.assertEqual(summary["roles_count"], 1)
        self.assertEqual(summary["users_count"], 1)
        self.assertEqual(summary["ldap_servers_count"], 1)
        self.assertEqual(summary["role_id_lengths"], [6])
        self.assertNotIn("password", str(summary).lower())
        self.assertNotIn("root@example.invalid", str(summary))

    def test_policy_summary_uses_non_sensitive_key_names(self) -> None:
        module = importlib.import_module("axxon_security_admin_preflight")
        summary = module.policy_summary(
            policies={"pwd_policy": [{}], "ip_filters": [{}, {}], "trusted_ip_list": [{}], "system_integrity_reaction_modes": ["x"]},
            ldap_sync={"enabled": False},
            ldap_state={"state": "STOPPED"},
            cloud_config={"cloud_public_key": "present"},
        )

        self.assertEqual(summary["pwd_policy_count"], 1)
        self.assertEqual(summary["ip_filter_count"], 2)
        self.assertNotIn("password", str(summary).lower())

    def test_restricted_config_summary_uses_non_sensitive_key_names(self) -> None:
        module = importlib.import_module("axxon_security_admin_preflight")
        summary = module.restricted_config_summary(
            {
                "current_user": {"login": "root"},
                "current_roles": [{}],
                "all_roles": [{}, {}],
                "all_users": [{}, {}, {}],
                "pwd_policy": [{}],
                "system_integrity_reaction_modes": ["x"],
            }
        )

        self.assertEqual(summary["pwd_policy_count"], 1)
        self.assertEqual(summary["all_users_count"], 3)
        self.assertNotIn("password", str(summary).lower())


if __name__ == "__main__":
    unittest.main()
