from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class MacroSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_macro_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x"])
        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_macro_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        self.assertTrue(module.mutation_approved(args))

    def test_report_notes_launch_is_not_called(self) -> None:
        module = importlib.import_module("axxon_macro_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        smoke = module.MacroSmoke(args)
        note = smoke.note_for({"group": "macro_lifecycle", "details": {"macro_id": "m", "launch_tested": False, "not_found_macros": ["m"]}})
        self.assertIn("launch_tested=False", note)

    def test_launch_requires_separate_opt_in(self) -> None:
        module = importlib.import_module("axxon_macro_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])

        self.assertFalse(args.launch_disabled_empty_macro)

    def test_launch_operation_is_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_macro_smoke")

        self.assertIn("LogicService.LaunchMacro.disabled_empty_temp_macro", module.MACRO_MUTATIONS_REQUIRING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
