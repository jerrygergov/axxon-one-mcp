from __future__ import annotations

import importlib
import unittest


class MutationPlaybookRunnerTests(unittest.TestCase):
    def test_runner_requires_explicit_approval_flag(self) -> None:
        module = importlib.import_module("axxon_mutation_playbook_runner")
        self.assertIn("--i-understand-this-mutates", module.build_parser().format_help())
