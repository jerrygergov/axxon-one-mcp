from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ArmStateSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_armstate_smoke")
        args = SimpleNamespace(i_understand_this_mutates=False, confirm=module.CONFIRMATION)

        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_armstate_smoke")
        args = SimpleNamespace(i_understand_this_mutates=True, confirm="yes")

        self.assertFalse(module.mutation_approved(args))

    def test_temporary_camera_display_id_is_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_armstate_smoke")

        self.assertTrue(module.temp_display_id().startswith("9"))

    def test_arm_state_uses_proto_enum_name(self) -> None:
        module = importlib.import_module("axxon_armstate_smoke")

        self.assertEqual(module.arm_state_name(), "CS_Arm")

    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_armstate_smoke")

        self.assertIn("ConfigurationService.ChangeConfig.add_temp_virtual_camera", module.ARMSTATE_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("LogicService.ChangeArmState.temp_virtual_camera", module.ARMSTATE_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ConfigurationService.ChangeConfig.remove_temp_virtual_camera", module.ARMSTATE_MUTATIONS_REQUIRING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
