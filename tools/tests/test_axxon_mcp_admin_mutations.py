from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeAdminMutationClient:
    pass


class AxxonMcpAdminMutationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_mcp_admin_mutations")

    def registry(self, *, enabled: bool = True):
        return self.module.AxxonAdminMutationRegistry(
            client_factory=lambda: FakeAdminMutationClient(),
            enabled=enabled,
        )

    def test_list_workflows_reports_5f_b1_scope(self) -> None:
        registry = self.registry()

        result = registry.list_workflows()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            {item["name"] for item in result["workflows"]},
            {
                "security_user_role_lifecycle",
                "security_role_permissions_update",
                "security_policy_noop_probe",
                "security_ldap_temp_lifecycle",
                "security_tfa_temp_user_lifecycle",
            },
        )

    def test_plan_records_tokens_and_redacted_params(self) -> None:
        registry = self.registry()

        plan = registry.plan(
            "security_user_role_lifecycle",
            {
                "display_name": "codex-user",
                "password": "<fixture-secret-value>",
                "authorization": "<fixture-bearer-value>",
            },
        )

        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["workflow"], "security_user_role_lifecycle")
        self.assertTrue(plan["plan_id"].startswith("admin-"))
        self.assertEqual(plan["confirmation_token"], "CONFIRM-admin-security_user_role_lifecycle")
        self.assertEqual(plan["rollback_confirmation_token"], "CONFIRM-admin-security_user_role_lifecycle-rollback")
        self.assertEqual(plan["params"]["password"], "<redacted>")
        self.assertEqual(plan["params"]["authorization"], "<redacted>")

    def test_unknown_workflow_returns_gap(self) -> None:
        registry = self.registry()

        result = registry.plan("license_apply", {})

        self.assertEqual(result["status"], "gap")
        self.assertIn("not in Phase 5F-B1", result["message"])

    def test_apply_rejects_when_registry_disabled(self) -> None:
        registry = self.registry(enabled=False)
        plan = registry.plan("security_user_role_lifecycle", {})

        result = registry.apply(plan["plan_id"], plan["confirmation_token"])

        self.assertEqual(result["status"], "rejected")
        self.assertIn("AXXON_ADMIN_MUTATION_APPROVE=1", result["message"])

    def test_apply_rejects_wrong_confirmation_token(self) -> None:
        registry = self.registry()
        plan = registry.plan("security_user_role_lifecycle", {})

        result = registry.apply(plan["plan_id"], "CONFIRM-wrong")

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "confirmation-token-mismatch")

    def test_scaffold_apply_verify_rollback_are_fixture_needed(self) -> None:
        registry = self.registry()
        plan = registry.plan("security_user_role_lifecycle", {})

        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        verified = registry.verify(plan["plan_id"])
        rolled_back = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        self.assertEqual(applied["status"], "fixture-needed")
        self.assertEqual(verified["status"], "fixture-needed")
        self.assertEqual(rolled_back["status"], "fixture-needed")

    def test_audit_log_redacts_sensitive_values(self) -> None:
        registry = self.registry()
        plan = registry.plan(
            "security_user_role_lifecycle",
            {
                "password": "<fixture-secret-value>",
                "token": "<fixture-token-value>",
                "license_key": "<fixture-license-value>",
                "serial_number": "<fixture-serial-value>",
                "hardware_fingerprint": "<fixture-fingerprint-value>",
                "message": "authorization=<fixture-token-value>",
            },
        )
        registry.apply(plan["plan_id"], plan["confirmation_token"])

        audit_text = str(registry.audit_log())

        self.assertNotIn("fixture-secret-value", audit_text)
        self.assertNotIn("fixture-token-value", audit_text)
        self.assertNotIn("fixture-license-value", audit_text)
        self.assertNotIn("fixture-serial-value", audit_text)
        self.assertNotIn("fixture-fingerprint-value", audit_text)


if __name__ == "__main__":
    unittest.main()
