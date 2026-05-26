from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeAdminMutationClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.roles: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.assignments: list[dict] = []
        self.password_assignments: list[dict] = []

    def security_change_config(self, payload: dict) -> dict:
        self.calls.append(payload)
        for role in payload.get("added_roles", []):
            self.roles[role["index"]] = dict(role)
        for user in payload.get("added_users", []):
            self.users[user["index"]] = dict(user)
        for assignment in payload.get("added_users_assignments", []):
            self.assignments.append(dict(assignment))
        for assignment in payload.get("modified_user_passwords", []):
            self.password_assignments.append(dict(assignment))
        removed_assignments = {
            (item.get("user_id"), item.get("role_id"))
            for item in payload.get("removed_users_assignments", [])
        }
        if removed_assignments:
            self.assignments = [
                item
                for item in self.assignments
                if (item.get("user_id"), item.get("role_id")) not in removed_assignments
            ]
        for user_id in payload.get("removed_users", []):
            self.users.pop(user_id, None)
        for role_id in payload.get("removed_roles", []):
            self.roles.pop(role_id, None)
        return {"status": 200, "body": {"failed": []}}

    def security_list_roles(self, *, page_size: int = 100, page_token: str = "") -> dict:
        return {"body": {"roles": list(self.roles.values())[:page_size]}}

    def security_list_users(
        self,
        *,
        page_size: int = 100,
        page_token: str = "",
        role_ids: list[str] | None = None,
    ) -> dict:
        users = list(self.users.values())
        assignments = list(self.assignments)
        if role_ids:
            role_set = set(role_ids)
            user_ids = {item["user_id"] for item in assignments if item.get("role_id") in role_set}
            users = [item for item in users if item.get("index") in user_ids]
            assignments = [item for item in assignments if item.get("role_id") in role_set]
        return {"body": {"users": users[:page_size], "user_assignments": assignments}}


class AxxonMcpAdminMutationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_mcp_admin_mutations")

    def registry(self, *, enabled: bool = True):
        self.fake = FakeAdminMutationClient()
        return self.module.AxxonAdminMutationRegistry(
            client_factory=lambda: self.fake,
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

    def test_scaffold_apply_verify_rollback_are_fixture_needed_for_later_workflow(self) -> None:
        registry = self.registry()
        plan = registry.plan("security_policy_noop_probe", {})

        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        verified = registry.verify(plan["plan_id"])
        rolled_back = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        self.assertEqual(applied["status"], "fixture-needed")
        self.assertEqual(verified["status"], "fixture-needed")
        self.assertEqual(rolled_back["status"], "fixture-needed")

    def test_user_role_lifecycle_applies_verifies_and_rolls_back_without_password_leak(self) -> None:
        registry = self.registry()
        plan = registry.plan("security_user_role_lifecycle", {"display_name_hint": "unit"})

        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        verified = registry.verify(plan["plan_id"])
        rolled_back = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        self.assertEqual(applied["status"], "applied")
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(rolled_back["status"], "rolled-back")
        self.assertTrue(applied["role_name"].startswith("codex-role-"))
        self.assertTrue(applied["login"].startswith("codex_user_"))
        self.assertEqual(verified["assigned_user_count"], 1)
        self.assertTrue(rolled_back["role_removed"])
        self.assertTrue(rolled_back["user_removed"])
        self.assertEqual(self.fake.roles, {})
        self.assertEqual(self.fake.users, {})
        self.assertEqual(self.fake.assignments, [])
        self.assertIn("modified_user_passwords", self.fake.calls[0])
        self.assertNotIn("password", str(applied).lower())
        self.assertNotIn("password", str(verified).lower())
        self.assertNotIn("password", str(rolled_back).lower())

    def test_user_role_lifecycle_rollback_rejects_wrong_confirmation(self) -> None:
        registry = self.registry()
        plan = registry.plan("security_user_role_lifecycle", {})
        registry.apply(plan["plan_id"], plan["confirmation_token"])

        result = registry.rollback(plan["plan_id"], "CONFIRM-wrong")

        self.assertEqual(result["status"], "rejected")
        self.assertIn(plan["plan_id"], registry.plans)
        self.assertNotEqual(self.fake.roles, {})

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
