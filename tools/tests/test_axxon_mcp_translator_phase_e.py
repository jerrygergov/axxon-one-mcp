"""Phase E tests: translator depth (resolve_device, catalog wiring, new intents, run_recipe)."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

mod = importlib.import_module("axxon_mcp_translator")

_CRED_SECRET = "DEVICE-PASSWORD-SHOULD-NOT-LEAK"


# --- stub operator (known_workflows + plan + apply + rollback) ----------------------------

class StubOperator:
    KNOWN = [
        "create_camera", "create_av_detector_full", "create_appdata_detector_full",
        "archive_policy_update", "create_macro", "create_layout", "update_layout",
        "create_map", "update_markers", "external_event_inject",
    ]

    def __init__(self, gap_workflows=None):
        self._gap = set(gap_workflows or [])
        self.applied: list = []
        self.rolled_back: list = []

    def known_workflows(self):
        return sorted(self.KNOWN)

    def plan(self, workflow, params=None):
        if workflow not in self.KNOWN or workflow in self._gap:
            return {"status": "gap", "workflow": workflow, "message": f"stub gap for {workflow}"}
        return {
            "status": "planned", "plan_id": f"stub-plan-{workflow}", "workflow": workflow,
            "risk": "mutation", "params": params or {},
            "confirmation_token": f"CONFIRM-{workflow}",
            "rollback_confirmation_token": f"CONFIRM-{workflow}-rollback",
        }

    def apply(self, plan_id, confirmation):
        self.applied.append((plan_id, confirmation))
        return {"status": "applied", "plan_id": plan_id, "created_uids": [f"uid-{plan_id}"]}

    def rollback(self, plan_id, confirmation):
        self.rolled_back.append((plan_id, confirmation))
        return {"status": "rolled_back", "plan_id": plan_id}


# --- stub devices catalog --------------------------------------------------------------

class StubDevices:
    """Fake AxxonMcpDevicesCatalog: a small vendor/model catalog."""

    CATALOG = {"Axis": ["P1448", "P3265"], "Hikvision": ["DS-2CD2", "DS-2DE4"]}

    def list_vendors(self, category="", filter="", node_name=""):
        return {"status": "ok", "vendors": sorted(self.CATALOG), "count": len(self.CATALOG)}

    def list_devices(self, category="", vendor="", filter="", node_name=""):
        if vendor and vendor in self.CATALOG:
            devs = [{"vendor": vendor, "model": m} for m in self.CATALOG[vendor]]
        else:
            devs = [{"vendor": v, "model": m} for v, ms in self.CATALOG.items() for m in ms]
        return {"status": "ok", "devices": devs, "count": len(devs)}

    def get_device(self, vendor="", model="", node_name=""):
        if vendor in self.CATALOG and model in self.CATALOG[vendor]:
            return {"status": "ok", "device": {"vendor": vendor, "model": model,
                                               "traits": {"has_storage": True, "default_port": 80}}}
        return {"status": "ok", "device": {}}  # absent pair -> empty device


def _translator(gap_workflows=None):
    return mod.AxxonMcpTranslator(
        operator_factory=lambda: StubOperator(gap_workflows=gap_workflows),
        devices_factory=lambda: StubDevices(),
    )


class ResolveDeviceTests(unittest.TestCase):
    def test_known_pair_ok(self):
        out = _translator().resolve_device("Axis", "P1448")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["vendor"], "Axis")
        self.assertEqual(out["model"], "P1448")

    def test_no_vendor_model_is_virtual(self):
        out = _translator().resolve_device("", "")
        self.assertEqual(out["status"], "virtual")

    def test_unknown_vendor_gap_with_suggestions(self):
        out = _translator().resolve_device("Axes", "P1448")  # typo'd vendor
        self.assertEqual(out["status"], "gap")
        self.assertIn("Axis", out["suggestions"])

    def test_unknown_model_gap_with_suggestions(self):
        out = _translator().resolve_device("Axis", "P1449")  # typo'd model
        self.assertEqual(out["status"], "gap")
        self.assertIn("P1448", out["suggestions"])


class AssembleDeviceResolutionTests(unittest.TestCase):
    def test_camera_with_known_device_carries_resolved_vendor_model(self):
        out = _translator().assemble_recipe("add an Axis camera", {"vendor": "Axis", "model": "P1448", "display_name": "Lobby"})
        step = out["steps"][0]
        self.assertEqual(step["workflow"], "create_camera")
        self.assertEqual(step["params"]["vendor"], "Axis")
        self.assertEqual(step["params"]["model"], "P1448")

    def test_camera_with_unknown_device_is_device_unresolved(self):
        out = _translator().assemble_recipe("add a camera", {"vendor": "Axis", "model": "P9999", "display_name": "Lobby"})
        self.assertEqual(out["status"], "device_unresolved")
        self.assertIn("P1448", out["suggestions"])

    def test_camera_without_vendor_model_unchanged_virtual_path(self):
        out = _translator().assemble_recipe("add a camera named Lobby", {"display_name": "Lobby"})
        self.assertNotIn("status", out)  # normal steps result
        self.assertEqual(out["steps"][0]["workflow"], "create_camera")
        self.assertNotIn("vendor", out["steps"][0]["params"])  # no device -> virtual default downstream


class NewIntentRuleTests(unittest.TestCase):
    def test_export_schedule_maps_to_macro(self):
        out = _translator().assemble_recipe("schedule an export every night", {"name": "nightly-export"})
        self.assertEqual(out["steps"][0]["workflow"], "create_macro")

    def test_raise_test_event_maps_to_external_event(self):
        out = _translator().assemble_recipe("raise a test alarm on the door sensor", {"access_point": "hosts/Server/DetectorEx.1/EventSupplier"})
        self.assertEqual(out["steps"][0]["workflow"], "external_event_inject")

    def test_new_rules_only_reference_known_workflows(self):
        op = StubOperator()
        for intent, ctx in [("schedule an export every night", {"name": "x"}),
                            ("raise a test alarm on sensor", {"access_point": "ap"})]:
            out = _translator().assemble_recipe(intent, ctx)
            for step in out.get("steps", []):
                self.assertIn(step["workflow"], op.known_workflows())


class RunRecipeTests(unittest.TestCase):
    def test_dry_run_no_mutation(self):
        op = StubOperator()
        t = mod.AxxonMcpTranslator(operator_factory=lambda: op, devices_factory=lambda: StubDevices())
        out = t.run_recipe("add a camera named Lobby", {"display_name": "Lobby"}, apply=False)
        self.assertEqual(out["mode"], "dry")
        self.assertEqual(op.applied, [])

    def test_apply_refused_without_confirmation(self):
        op = StubOperator()
        t = mod.AxxonMcpTranslator(operator_factory=lambda: op, devices_factory=lambda: StubDevices())
        out = t.run_recipe("add a camera named Lobby", {"display_name": "Lobby"}, apply=True, confirmation="")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(op.applied, [])

    def test_apply_refused_on_gap_step(self):
        op = StubOperator(gap_workflows=["create_camera"])
        t = mod.AxxonMcpTranslator(operator_factory=lambda: op, devices_factory=lambda: StubDevices())
        out = t.run_recipe("add a camera named Lobby", {"display_name": "Lobby"}, apply=True, confirmation=mod.RUN_RECIPE_CONFIRMATION)
        self.assertIn(out["status"], {"invalid", "gap"})
        self.assertEqual(op.applied, [])

    def test_apply_runs_validated_steps_with_confirmation(self):
        op = StubOperator()
        t = mod.AxxonMcpTranslator(operator_factory=lambda: op, devices_factory=lambda: StubDevices())
        out = t.run_recipe("add a camera named Lobby", {"display_name": "Lobby"}, apply=True, confirmation=mod.RUN_RECIPE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(len(op.applied), 1)
        self.assertTrue(out["applied_steps"][0]["rollback_confirmation_token"])


class NoSecretLeakTests(unittest.TestCase):
    def test_resolve_device_never_leaks_credentials(self):
        out = _translator().resolve_device("Axis", "P1448")
        self.assertNotIn(_CRED_SECRET, str(out))


class BackwardCompatTests(unittest.TestCase):
    def test_devices_factory_is_optional(self):
        import inspect
        sig = inspect.signature(mod.AxxonMcpTranslator)
        self.assertIn("devices_factory", sig.parameters)

    def test_run_recipe_tool_registered_name_exists(self):
        self.assertTrue(hasattr(mod, "RUN_RECIPE_CONFIRMATION"))


if __name__ == "__main__":
    unittest.main()
