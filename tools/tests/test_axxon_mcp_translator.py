"""Phase 7 tests: AxxonMcpTranslator (assemble_recipe / validate_recipe / explain_recipe)."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


# ---------------------------------------------------------------------------
# Stub operator injected by every test — no network, no real operator.
# ---------------------------------------------------------------------------

class StubPlanResult:
    """Minimal plan result returned by the stub operator."""

    def __init__(self, workflow: str, *, gap: bool = False, risk: str = "mutation") -> None:
        self.workflow = workflow
        self.gap = gap
        self.risk = risk

    def as_dict(self) -> dict:
        if self.gap:
            return {
                "status": "gap",
                "workflow": self.workflow,
                "message": f"stub gap for {self.workflow}",
            }
        return {
            "status": "planned",
            "plan_id": f"stub-plan-{self.workflow}",
            "workflow": self.workflow,
            "risk": self.risk,
            "intent": f"stub intent for {self.workflow}",
            "confirmation_token": f"CONFIRM-{self.workflow}",
            "rollback_confirmation_token": f"CONFIRM-{self.workflow}-rollback",
        }


class StubOperator:
    """Fake OperatorRegistry: known_workflows + plan, no network."""

    KNOWN = [
        "temp_camera", "temp_archive", "temp_av_detector", "temp_appdata_detector",
        "create_av_detector_full", "create_appdata_detector_full", "temp_device_template",
        "external_event_inject", "temp_macro", "create_camera", "create_macro",
        "create_layout", "update_layout", "delete_layout", "set_unit_properties",
        "update_detector_parameters", "update_detector_visual_element", "delete_detector",
        "archive_policy_update", "archive_format_volume", "archive_reindex",
        "archive_cancel_reindex", "temp_wall", "videowall_register", "videowall_change",
        "videowall_set_control_data", "videowall_unregister", "create_map", "update_map",
        "delete_map", "update_markers",
    ]

    def __init__(self, *, gap_workflows: list[str] | None = None) -> None:
        self._gap_workflows = set(gap_workflows or [])

    def known_workflows(self) -> list[str]:
        return sorted(self.KNOWN)

    def plan(self, workflow: str, params: dict | None = None) -> dict:
        if workflow not in self.KNOWN:
            return {
                "status": "gap",
                "message": f"unknown workflow: {workflow}",
                "known_workflows": self.known_workflows(),
            }
        if workflow in self._gap_workflows:
            return {
                "status": "gap",
                "workflow": workflow,
                "message": f"stub gap for {workflow}",
            }
        return {
            "status": "planned",
            "plan_id": f"stub-plan-{workflow}",
            "workflow": workflow,
            "risk": "mutation",
            "intent": f"stub intent for {workflow}",
            "confirmation_token": f"CONFIRM-{workflow}",
            "rollback_confirmation_token": f"CONFIRM-{workflow}-rollback",
        }


def stub_factory(gap_workflows: list[str] | None = None):
    return lambda: StubOperator(gap_workflows=gap_workflows)


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

class TestAxxonMcpTranslatorImport(unittest.TestCase):
    def test_module_importable_no_side_effects(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self.assertTrue(hasattr(mod, "AxxonMcpTranslator"))
        self.assertTrue(hasattr(mod, "register_translator_tools"))

    def test_dataclass_fields(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        import inspect
        sig = inspect.signature(mod.AxxonMcpTranslator)
        self.assertIn("operator_factory", sig.parameters)


# ---------------------------------------------------------------------------
# assemble_recipe — 10 reference intents (AC2 / V4)
# ---------------------------------------------------------------------------

class TestAssembleRecipeReferenceIntents(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(operator_factory=stub_factory())
        # Load WORKFLOWS from operator to assert against
        op_mod = importlib.import_module("axxon_mcp_operator")
        self._known = set(op_mod.WORKFLOWS.keys())

    def _assert_steps(self, result: dict, min_count: int = 1) -> list[dict]:
        self.assertIn("steps", result, f"No 'steps' key in: {result}")
        steps = result["steps"]
        self.assertGreaterEqual(len(steps), min_count, f"Expected >= {min_count} step(s); got {steps}")
        for step in steps:
            self.assertIn("workflow", step)
            self.assertIn(step["workflow"], self._known,
                          f"Unknown workflow name: {step['workflow']!r}")
            self.assertIn("params", step)
            self.assertIn("why", step)
        return steps

    def test_i1_add_camera(self) -> None:
        result = self._translator.assemble_recipe(
            "Add a camera at 192.168.1.100",
            {"display_name": "Cam-01", "ip": "192.168.1.100"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_camera")

    def test_i2_add_av_detector(self) -> None:
        result = self._translator.assemble_recipe(
            "Add AV detector to camera abc-uid",
            {"camera_uid": "abc-uid", "video_source_ap": "hosts/Server/DeviceIpint.1/VideoSourceEndpoint.0"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_av_detector_full")

    def test_i3_add_appdata_detector(self) -> None:
        result = self._translator.assemble_recipe(
            "Add AppData detector to camera abc-uid",
            {"camera_uid": "abc-uid", "video_source_ap": "hosts/Server/DeviceIpint.1/VideoSourceEndpoint.0"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_appdata_detector_full")

    def test_i4_set_archive_policy(self) -> None:
        result = self._translator.assemble_recipe(
            "Set camera archive to 14 days",
            {"archive_uid": "hosts/Server/MultimediaStorage.1", "days": 14},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "archive_policy_update")

    def test_i5_create_export_schedule_macro(self) -> None:
        result = self._translator.assemble_recipe(
            "Create export schedule macro for camera abc-uid",
            {"camera_uid": "abc-uid", "name": "export-sched-macro"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_macro")

    def test_i6_create_layout(self) -> None:
        result = self._translator.assemble_recipe(
            "Create layout named Main View",
            {"name": "Main View"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_layout")

    def test_i7_add_camera_to_layout(self) -> None:
        result = self._translator.assemble_recipe(
            "Add camera to existing layout",
            {
                "layout_id": "layout-uid-123",
                "video_source_ap": "hosts/Server/DeviceIpint.1/VideoSourceEndpoint.0",
            },
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "update_layout")

    def test_i8_create_map(self) -> None:
        result = self._translator.assemble_recipe(
            "Create map named Floor 1",
            {"name": "Floor 1"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "create_map")

    def test_i9_place_camera_marker(self) -> None:
        result = self._translator.assemble_recipe(
            "Place camera marker on map",
            {
                "map_id": "map-uid-456",
                "access_point": "hosts/Server/DeviceIpint.1/VideoSourceEndpoint.0",
            },
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "update_markers")

    def test_i10_inject_alarm_event(self) -> None:
        result = self._translator.assemble_recipe(
            "Inject external alarm event",
            {"access_point": "hosts/Server/DetectorEx.1/EventSupplier"},
        )
        steps = self._assert_steps(result)
        self.assertEqual(steps[0]["workflow"], "external_event_inject")

    def test_all_step_workflows_in_known_set(self) -> None:
        """Iterate all 10 intents and assert no invented workflow name surfaces."""
        cases = [
            ("Add a camera at 1.2.3.4", {"display_name": "Cam-X", "ip": "1.2.3.4"}),
            ("Add AV detector to camera x", {"video_source_ap": "hosts/S/D.1/VSE.0"}),
            ("Add AppData detector to camera x", {"video_source_ap": "hosts/S/D.1/VSE.0"}),
            ("Set camera archive to 7 days", {"archive_uid": "hosts/S/MMS.1", "days": 7}),
            ("Create export schedule macro", {"name": "my-macro"}),
            ("Create layout named X", {"name": "X"}),
            ("Add camera to existing layout", {"layout_id": "lid-1"}),
            ("Create map named Y", {"name": "Y"}),
            ("Place camera marker on map", {"map_id": "mid-1"}),
            ("Inject external alarm event", {"access_point": "hosts/S/DetEx.1/ES"}),
        ]
        for intent, ctx in cases:
            result = self._translator.assemble_recipe(intent, ctx)
            if result.get("status") == "unsupported_intent":
                continue
            for step in result.get("steps", []):
                self.assertIn(step["workflow"], self._known,
                              f"Invented workflow {step['workflow']!r} for intent: {intent!r}")


# ---------------------------------------------------------------------------
# assemble_recipe — unsupported intent gaps (AC3 / V5)
# ---------------------------------------------------------------------------

class TestAssembleRecipeUnsupportedIntents(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(operator_factory=stub_factory())

    def _assert_gap(self, result: dict) -> None:
        self.assertEqual(result.get("status"), "unsupported_intent",
                         f"Expected unsupported_intent, got: {result}")
        self.assertTrue(result.get("reason"), "reason must be non-empty")
        self.assertIsInstance(result.get("known_workflows"), list)

    def test_ptz_preset_is_unsupported(self) -> None:
        result = self._translator.assemble_recipe("set PTZ preset 2 for camera X", {})
        self._assert_gap(result)
        self.assertIn("intent_text", result)

    def test_assign_role_is_unsupported(self) -> None:
        result = self._translator.assemble_recipe("assign admin role to user Y", {})
        self._assert_gap(result)
        self.assertIn("intent_text", result)

    def test_permission_change_is_unsupported(self) -> None:
        result = self._translator.assemble_recipe("grant access permission to user Z", {})
        self._assert_gap(result)

    def test_unsupported_does_not_raise(self) -> None:
        for intent in ["move camera PTZ left", "create user account", "change password for user"]:
            result = self._translator.assemble_recipe(intent, {})
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# assemble_recipe — multi-step combination intent
# ---------------------------------------------------------------------------

class TestAssembleRecipeMultiStep(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(operator_factory=stub_factory())
        op_mod = importlib.import_module("axxon_mcp_operator")
        self._known = set(op_mod.WORKFLOWS.keys())

    def test_camera_with_av_detector_two_steps(self) -> None:
        result = self._translator.assemble_recipe(
            "add a camera with AV detector",
            {"display_name": "Cam-Multi", "ip": "10.0.0.1", "video_source_ap": "hosts/S/D.1/VSE.0"},
        )
        self.assertIn("steps", result)
        steps = result["steps"]
        self.assertGreaterEqual(len(steps), 2)
        workflows = [s["workflow"] for s in steps]
        self.assertIn("create_camera", workflows)
        self.assertIn("create_av_detector_full", workflows)
        for w in workflows:
            self.assertIn(w, self._known)


# ---------------------------------------------------------------------------
# validate_recipe (AC4)
# ---------------------------------------------------------------------------

class TestValidateRecipeHappyPath(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(operator_factory=stub_factory())

    def test_all_planned_valid_true(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "Cam-01"}, "why": "add camera"},
            {"workflow": "create_layout", "params": {"name": "View-1"}, "why": "add layout"},
        ]
        result = self._translator.validate_recipe(recipe)
        self.assertTrue(result["valid"])
        self.assertEqual(result["gaps"], [])
        self.assertEqual(len(result["steps"]), 2)
        for step in result["steps"]:
            self.assertEqual(step["status"], "planned")
            self.assertIsNotNone(step["plan_id"])
            self.assertIsNotNone(step["confirmation_token"])
        self.assertIsInstance(result["risk_classes"], list)
        self.assertIsInstance(result["required_approvals"], list)

    def test_returned_keys_present(self) -> None:
        recipe = [{"workflow": "external_event_inject", "params": {}, "why": "test"}]
        result = self._translator.validate_recipe(recipe)
        for key in ("valid", "steps", "risk_classes", "required_approvals", "gaps"):
            self.assertIn(key, result)

    def test_accepts_assemble_recipe_output_dict(self) -> None:
        """validate_recipe consumes assemble_recipe's dict output directly so the chain composes."""
        assembled = self._translator.assemble_recipe("create a macro named codex-test")
        self.assertIn("steps", assembled)
        result = self._translator.validate_recipe(assembled)
        self.assertEqual(len(result["steps"]), len(assembled["steps"]))
        self.assertIn("valid", result)

    def test_does_not_call_apply_or_rollback(self) -> None:
        called = []
        mod = importlib.import_module("axxon_mcp_translator")

        class WatchedOperator(StubOperator):
            def apply(self, *a, **kw):
                called.append("apply")
            def rollback(self, *a, **kw):
                called.append("rollback")

        t = mod.AxxonMcpTranslator(operator_factory=lambda: WatchedOperator())
        t.validate_recipe([{"workflow": "create_camera", "params": {}, "why": "x"}])
        self.assertEqual(called, [], "validate_recipe must not call apply or rollback")


class TestValidateRecipeGappedPath(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(
            operator_factory=stub_factory(gap_workflows=["create_layout"])
        )

    def test_gapped_step_valid_false(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "Cam-01"}, "why": "add camera"},
            {"workflow": "create_layout", "params": {}, "why": "add layout"},
        ]
        result = self._translator.validate_recipe(recipe)
        self.assertFalse(result["valid"])
        self.assertIn("create_layout", result["gaps"])

    def test_gapped_step_status_is_gap(self) -> None:
        recipe = [{"workflow": "create_layout", "params": {}, "why": "test"}]
        result = self._translator.validate_recipe(recipe)
        step = result["steps"][0]
        self.assertEqual(step["status"], "gap")
        self.assertIsNone(step["plan_id"])

    def test_partially_gapped_result_shape(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "C"}, "why": "a"},
            {"workflow": "create_layout", "params": {}, "why": "b"},
        ]
        result = self._translator.validate_recipe(recipe)
        statuses = {s["workflow"]: s["status"] for s in result["steps"]}
        self.assertEqual(statuses["create_camera"], "planned")
        self.assertEqual(statuses["create_layout"], "gap")


# ---------------------------------------------------------------------------
# validate_recipe — archive maintenance env gate surfaced in required_approvals
# ---------------------------------------------------------------------------

class TestValidateRecipeRequiredApprovals(unittest.TestCase):
    def test_mutation_risk_no_archive_approval_required(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        t = mod.AxxonMcpTranslator(operator_factory=stub_factory())
        recipe = [{"workflow": "create_camera", "params": {"display_name": "C"}, "why": "test"}]
        result = t.validate_recipe(recipe)
        # mutation risk does not require the archive maintenance env gate
        self.assertNotIn("AXXON_ARCHIVE_MAINTENANCE_APPROVE", result.get("required_approvals", []))


# ---------------------------------------------------------------------------
# explain_recipe (AC5)
# ---------------------------------------------------------------------------

class TestExplainRecipeValid(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(operator_factory=stub_factory())

    def _get_text(self, result) -> str:
        if isinstance(result, str):
            return result
        return result.get("text", "")

    def test_returns_non_empty_output(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "Cam-01"}, "why": "add camera"},
        ]
        result = self._translator.explain_recipe(recipe)
        text = self._get_text(result)
        self.assertTrue(text, "explain_recipe must return non-empty text")

    def test_contains_why(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {}, "why": "add camera for entrance"},
        ]
        text = self._get_text(self._translator.explain_recipe(recipe))
        self.assertIn("add camera for entrance", text)

    def test_contains_risk_word(self) -> None:
        recipe = [
            {"workflow": "create_layout", "params": {}, "why": "create view layout"},
        ]
        text = self._get_text(self._translator.explain_recipe(recipe))
        # should mention risk classification
        self.assertTrue(
            any(w in text.lower() for w in ("mutation", "archive_maintenance", "risk")),
            f"risk word missing in: {text!r}",
        )

    def test_contains_time_estimate(self) -> None:
        recipe = [{"workflow": "create_map", "params": {}, "why": "add floor map"}]
        text = self._get_text(self._translator.explain_recipe(recipe))
        # wall-clock estimate must appear (seconds or minutes)
        self.assertTrue(
            any(w in text.lower() for w in ("second", "minute", "~")),
            f"time estimate missing in: {text!r}",
        )

    def test_contains_rollback_note(self) -> None:
        recipe = [{"workflow": "update_markers", "params": {}, "why": "place marker"}]
        text = self._get_text(self._translator.explain_recipe(recipe))
        self.assertTrue(
            any(w in text.lower() for w in ("rollback", "revert", "undo", "reverse")),
            f"rollback note missing in: {text!r}",
        )

    def test_no_network_call(self) -> None:
        """explain_recipe must work with stub operator and no network."""
        recipe = [{"workflow": "create_camera", "params": {}, "why": "test"}]
        # Just verify it doesn't raise. If it tried network it would fail.
        result = self._translator.explain_recipe(recipe)
        self.assertIsNotNone(result)

    def test_accepts_validate_recipe_output(self) -> None:
        """explain_recipe must accept the enriched validate_recipe output."""
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "C"}, "why": "test camera"},
        ]
        validated = self._translator.validate_recipe(recipe)
        result = self._translator.explain_recipe(validated)
        text = self._get_text(result)
        self.assertTrue(text)


class TestExplainRecipeGapped(unittest.TestCase):
    def setUp(self) -> None:
        mod = importlib.import_module("axxon_mcp_translator")
        self._translator = mod.AxxonMcpTranslator(
            operator_factory=stub_factory(gap_workflows=["create_layout"])
        )

    def _get_text(self, result) -> str:
        if isinstance(result, str):
            return result
        return result.get("text", "")

    def test_gapped_recipe_does_not_raise(self) -> None:
        recipe = [
            {"workflow": "create_camera", "params": {"display_name": "C"}, "why": "add camera"},
            {"workflow": "create_layout", "params": {}, "why": "add layout"},
        ]
        # Should not raise even though create_layout is a gap
        result = self._translator.explain_recipe(recipe)
        text = self._get_text(result)
        self.assertIsNotNone(text)

    def test_gapped_recipe_from_validate_does_not_raise(self) -> None:
        recipe = [{"workflow": "create_layout", "params": {}, "why": "bad"}]
        validated = self._translator.validate_recipe(recipe)
        result = self._translator.explain_recipe(validated)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# register_translator_tools (AC6 — server registration)
# ---------------------------------------------------------------------------

class TestRegisterTranslatorTools(unittest.TestCase):
    """verify register_translator_tools wires the 3 tool names."""

    def setUp(self) -> None:
        self._mod = importlib.import_module("axxon_mcp_translator")
        self._translator = self._mod.AxxonMcpTranslator(operator_factory=stub_factory())

    def _make_fake_server(self):
        class FakeServer:
            def __init__(self):
                self.tools: dict = {}

            def tool(self, name=None):
                def decorator(fn):
                    self.tools[name or fn.__name__] = fn
                    return fn
                return decorator

        return FakeServer()

    def test_three_tool_names_registered(self) -> None:
        server = self._make_fake_server()
        self._mod.register_translator_tools(server, self._translator)
        for name in ("assemble_recipe", "validate_recipe", "explain_recipe"):
            self.assertIn(name, server.tools, f"Tool {name!r} not registered")

    def test_assemble_recipe_tool_callable(self) -> None:
        server = self._make_fake_server()
        self._mod.register_translator_tools(server, self._translator)
        fn = server.tools["assemble_recipe"]
        result = fn("Create layout named X", {"name": "X"})
        self.assertIn("steps", result)

    def test_validate_recipe_tool_callable(self) -> None:
        server = self._make_fake_server()
        self._mod.register_translator_tools(server, self._translator)
        fn = server.tools["validate_recipe"]
        recipe = [{"workflow": "create_camera", "params": {"display_name": "C"}, "why": "test"}]
        result = fn(recipe)
        self.assertIn("valid", result)

    def test_explain_recipe_tool_callable(self) -> None:
        server = self._make_fake_server()
        self._mod.register_translator_tools(server, self._translator)
        fn = server.tools["explain_recipe"]
        recipe = [{"workflow": "create_camera", "params": {}, "why": "test"}]
        result = fn(recipe)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
