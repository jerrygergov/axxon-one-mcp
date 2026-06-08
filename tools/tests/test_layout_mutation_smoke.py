from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class LayoutMutationSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_layout_mutation_smoke")
        args = SimpleNamespace(i_understand_this_mutates=False, confirm=module.CONFIRMATION)

        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_layout_mutation_smoke")
        args = SimpleNamespace(i_understand_this_mutates=True, confirm="yes")

        self.assertFalse(module.mutation_approved(args))

    def test_temp_layout_ids_are_codex_prefixed(self) -> None:
        module = importlib.import_module("axxon_layout_mutation_smoke")

        self.assertTrue(module.temp_layout_id().startswith("codex-layout-"))

    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_layout_mutation_smoke")

        self.assertIn("LayoutManager.Update.create_temp_layout", module.LAYOUT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("LayoutManager.Update.modify_temp_layout", module.LAYOUT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("LayoutManager.Update.remove_temp_layout", module.LAYOUT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("LayoutManager.LayoutsOnView.temp_layout", module.LAYOUT_MUTATIONS_REQUIRING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
