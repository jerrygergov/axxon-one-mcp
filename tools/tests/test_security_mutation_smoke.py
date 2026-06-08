from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class SecurityMutationSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_security_mutation_smoke")
        args = SimpleNamespace(i_understand_this_mutates=False, confirm=module.CONFIRMATION)

        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_security_mutation_smoke")
        args = SimpleNamespace(i_understand_this_mutates=True, confirm="yes")

        self.assertFalse(module.mutation_approved(args))

    def test_ids_are_uuid_and_labels_are_codex_prefixed(self) -> None:
        module = importlib.import_module("axxon_security_mutation_smoke")

        ids = module.temp_security_ids()
        self.assertEqual(len(ids["role_id"]), 36)
        self.assertEqual(len(ids["user_id"]), 36)
        self.assertTrue(ids["role_name"].startswith("codex-role-"))
        self.assertTrue(ids["login"].startswith("codex_user_"))

    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_security_mutation_smoke")

        self.assertIn("SecurityService.ChangeConfig.add_role", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.ChangeConfig.add_user", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.ChangeConfig.assign_user_role", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.ChangeConfig.remove_user_role", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.GenGoogleAuthSecret", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.EnableGoogleAuth.temp_user", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("SecurityService.DisableGoogleAuth.temp_user", module.SECURITY_MUTATIONS_REQUIRING_APPROVAL)

    def test_totp_code_matches_rfc6238_vector(self) -> None:
        module = importlib.import_module("axxon_security_mutation_smoke")

        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        code = module.totp_code(secret, for_time=59, digits=8)

        self.assertEqual(code, "94287082")


if __name__ == "__main__":
    unittest.main()
