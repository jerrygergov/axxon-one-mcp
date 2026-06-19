from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class VerifyMcpStartupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("verify_mcp_startup")

    def test_cases_cover_customer_profiles_in_order(self) -> None:
        self.assertEqual(
            [(case.name, case.args) for case in self.module.CASES],
            [
                ("knowledge", ()),
                ("live-import", ("--enable-live",)),
                ("all-read-only", ("--enable-all", "--read-only")),
            ],
        )

    def test_cases_are_immutable(self) -> None:
        with self.assertRaises((AttributeError, TypeError)):
            self.module.CASES[0].name = "changed"

    def test_clean_environment_removes_all_axxon_values(self) -> None:
        clean = self.module.clean_environment(
            {
                "PATH": "/bin",
                "HOME": "/tmp/home",
                "AXXON_PASSWORD": "secret",
                "AXXON_OPERATOR_APPROVE": "1",
            }
        )
        self.assertEqual(clean, {"PATH": "/bin", "HOME": "/tmp/home"})

    def test_clean_environment_does_not_change_input(self) -> None:
        source = {"PATH": "/bin", "AXXON_PASSWORD": "secret"}
        self.module.clean_environment(source)
        self.assertEqual(source, {"PATH": "/bin", "AXXON_PASSWORD": "secret"})

    def test_default_expected_tools_are_exact(self) -> None:
        self.assertEqual(
            self.module.KNOWLEDGE_TOOLS,
            {
                "search_api_docs",
                "get_api_method",
                "get_http_endpoint",
                "get_verified_example",
                "explain_task_recipe",
                "list_remaining_gaps",
                "list_capabilities",
            },
        )

    def test_all_read_only_environment_injects_every_approval(self) -> None:
        clean = self.module.clean_environment(dict(os.environ))
        prepared = self.module.environment_for_case(
            self.module.StartupCase("all-read-only", ("--enable-all", "--read-only")),
            clean,
        )
        self.assertTrue(self.module.APPROVAL_ENV_VARS)
        self.assertTrue(
            all(prepared[name] == "1" for name in self.module.APPROVAL_ENV_VARS)
        )


if __name__ == "__main__":
    unittest.main()
