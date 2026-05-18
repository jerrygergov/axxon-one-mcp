from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeMutationClient:
    """Records ChangeConfig calls so plan/apply/verify can be tested offline."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._next_uid = 0
        self.units: dict[str, dict] = {}

    def _alloc_uid(self, unit_type: str) -> str:
        self._next_uid += 1
        return f"hosts/Server/{unit_type}.{self._next_uid}"

    def change_config(self, payload: dict) -> dict:
        self.calls.append(payload)
        added_uids: list[str] = []
        failed: list[dict] = []
        for parent in payload.get("added", []):
            for unit in parent.get("units", []):
                uid = self._alloc_uid(unit["type"])
                self.units[uid] = {"type": unit["type"], "properties": unit.get("properties", [])}
                added_uids.append(uid)
        for unit in payload.get("changed", []):
            uid = unit["uid"]
            if uid not in self.units:
                failed.append({"uid": uid, "reason": "missing"})
                continue
            self.units[uid]["properties"] = unit.get("properties", [])
        for unit in payload.get("removed", []):
            uid = unit["uid"]
            if uid not in self.units:
                failed.append({"uid": uid, "reason": "missing"})
                continue
            del self.units[uid]
        return {"added": added_uids, "failed": failed, "failed_reason": []}

    def read_unit(self, uid: str) -> dict:
        if uid not in self.units:
            return {"units": []}
        return {"units": [{"uid": uid, **self.units[uid]}]}


class FakeTemplateClient(FakeMutationClient):
    """Adds ChangeTemplates support on top of the basic ChangeConfig fake."""

    def __init__(self) -> None:
        super().__init__()
        self.templates: dict[str, dict] = {}

    def change_templates(self, payload: dict) -> dict:
        self.calls.append({"_templates": True, **payload})
        created_ids: list[str] = []
        for item in payload.get("created", []):
            tid = item["id"]
            self.templates[tid] = item
            created_ids.append(tid)
        for tid in payload.get("removed", []):
            self.templates.pop(tid, None)
        return {"created": created_ids}

    def read_template(self, template_id: str) -> dict:
        if template_id in self.templates:
            return {"items": [{"id": template_id, **self.templates[template_id]}]}
        return {"items": []}


class FakeEventClient(FakeMutationClient):
    """Adds http_post_bearer for external-event injection."""

    def __init__(self) -> None:
        super().__init__()
        self.posts: list[dict] = []

    def http_post_bearer(self, path: str, body: dict) -> dict:
        self.posts.append({"path": path, "body": body})
        return {"status": 200, "body": {"accepted": True}}


class FakeMacroClient(FakeMutationClient):
    """Adds ChangeMacros support for the temp_macro operator workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.macros: dict[str, dict] = {}

    def change_macros(self, payload: dict) -> dict:
        self.calls.append({"_macros": True, **payload})
        created_ids: list[str] = []
        for macro in payload.get("added_macros", []):
            mid = macro["guid"]
            self.macros[mid] = macro
            created_ids.append(mid)
        for mid in payload.get("removed_macros", []):
            self.macros.pop(mid, None)
        return {"created_macro_ids": created_ids}

    def read_macro(self, macro_id: str) -> dict:
        if macro_id in self.macros:
            return {"items": [self.macros[macro_id]]}
        return {"items": []}


class FakeLayoutClient(FakeMutationClient):
    """Adds LayoutManager.Update support for layout workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.layouts: dict[str, dict] = {}

    def change_layouts(self, payload: dict) -> dict:
        self.calls.append({"_layouts": True, **payload})
        for item in payload.get("created", []):
            self.layouts[item["id"]] = item
        for lid in payload.get("removed", []):
            self.layouts.pop(lid, None)
        return {}

    def read_layout(self, layout_id: str) -> dict:
        if layout_id in self.layouts:
            return {"items": [self.layouts[layout_id]]}
        return {"items": []}


class OperatorPlanTests(unittest.TestCase):
    def test_plan_temp_camera_returns_typed_plan_without_server_call(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = registry.plan("temp_camera", {"display_name_hint": "smoke"})

        self.assertIn("plan_id", plan)
        self.assertTrue(plan["plan_id"].startswith("plan-"))
        self.assertEqual(plan["workflow"], "temp_camera")
        self.assertEqual(plan["status"], "planned")
        self.assertIn("rollback", plan)
        self.assertEqual(plan["risk"], "mutation")
        # No server calls should have happened during planning.
        self.assertEqual(client.calls, [])
        # Plan must include the exact ChangeConfig payload that apply() will send.
        self.assertIn("payload", plan["steps"][0])
        self.assertEqual(plan["steps"][0]["operation"], "add")

    def test_apply_requires_known_plan_id_and_confirmation(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_camera", {"display_name_hint": "smoke"})

        # Unknown plan_id is rejected.
        bad = registry.apply("plan-does-not-exist", confirmation="CONFIRM-temp_camera")
        self.assertEqual(bad["status"], "rejected")
        self.assertIn("unknown", bad["message"].lower())

        # Wrong confirmation token is rejected.
        wrong = registry.apply(plan["plan_id"], confirmation="WRONG")
        self.assertEqual(wrong["status"], "rejected")
        self.assertIn("confirmation", wrong["message"].lower())
        self.assertEqual(client.calls, [])

    def test_apply_then_verify_then_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_camera", {"display_name_hint": "smoke"})

        applied = registry.apply(plan["plan_id"], confirmation=f"CONFIRM-{plan['workflow']}")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(applied["created_uids"]), 1)
        created_uid = applied["created_uids"][0]
        self.assertTrue(created_uid.startswith("hosts/Server/DeviceIpint."))

        verified = registry.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["created_uids"], applied["created_uids"])
        self.assertEqual(verified["still_present"], applied["created_uids"])

        rolled = registry.rollback(plan["plan_id"], confirmation=f"CONFIRM-{plan['workflow']}-rollback")
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertNotIn(created_uid, client.units)

        # Final verify after rollback must reflect cleanup.
        post = registry.verify(plan["plan_id"])
        self.assertEqual(post["still_present"], [])

    def test_audit_log_records_every_action(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_camera", {"display_name_hint": "audit"})
        registry.apply(plan["plan_id"], confirmation=f"CONFIRM-{plan['workflow']}")
        registry.rollback(plan["plan_id"], confirmation=f"CONFIRM-{plan['workflow']}-rollback")

        log = registry.audit_log()
        actions = [entry["action"] for entry in log]
        self.assertEqual(actions, ["plan", "apply", "rollback"])
        # No raw credential/token fields are stored in audit entries.
        for entry in log:
            self.assertNotIn("password", entry)
            self.assertNotIn("bearer", str(entry).lower())

    def test_unknown_workflow_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        plan = registry.plan("not_a_real_workflow", {})
        self.assertEqual(plan["status"], "gap")
        self.assertIn("workflow", plan["message"].lower())

    def test_plan_temp_archive_returns_typed_plan(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_archive", {"display_name_hint": "smoke"})
        self.assertEqual(plan["workflow"], "temp_archive")
        self.assertEqual(plan["steps"][0]["unit_type"], "MultimediaStorage")
        self.assertTrue(plan["expected"]["display_name"].startswith("codex-temp-archive-smoke-"))
        self.assertEqual(client.calls, [])

    def test_plan_temp_archive_apply_verify_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_archive", {})
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertTrue(applied["created_uids"][0].startswith("hosts/Server/MultimediaStorage."))
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(registry.verify(plan["plan_id"])["still_present"], [])

    def test_temp_av_detector_requires_video_source_ap(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        gap = registry.plan("temp_av_detector", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("video_source_ap", gap["message"])

    def test_temp_av_detector_plan_with_source(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "temp_av_detector",
            {"video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "detector": "MotionDetection"},
        )
        self.assertEqual(plan["workflow"], "temp_av_detector")
        self.assertEqual(plan["steps"][0]["unit_type"], "AVDetector")
        self.assertEqual(plan["expected"]["detector"], "MotionDetection")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertTrue(applied["created_uids"][0].startswith("hosts/Server/AVDetector."))

    def test_temp_appdata_detector_requires_at_least_video_source_ap(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        gap = registry.plan("temp_appdata_detector", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("video_source_ap", gap["message"])

    def test_temp_appdata_detector_chains_scene_when_vmda_missing(self) -> None:
        """When only video_source_ap is given, the workflow chain-creates a SceneDescription first then the AppDataDetector."""
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "temp_appdata_detector",
            {"video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
        )
        self.assertEqual(plan["workflow"], "temp_appdata_detector")
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["unit_type"], "AVDetector")
        self.assertEqual(plan["steps"][1]["unit_type"], "AppDataDetector")
        # The vmda source AP is resolved at apply time from the first step's created UID.
        self.assertEqual(plan["steps"][1].get("resolve_vmda_from_step"), 0)
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(applied["created_uids"]), 2)
        # Rollback removes both in reverse order.
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(len(rolled["removed_uids"]), 2)

    def test_temp_appdata_detector_plan_apply_verify_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "temp_appdata_detector",
            {
                "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                "vmda_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.vmda_source_ap:0",
                "detector": "MoveInZone",
            },
        )
        self.assertEqual(plan["workflow"], "temp_appdata_detector")
        self.assertEqual(plan["steps"][0]["unit_type"], "AppDataDetector")
        self.assertEqual(plan["expected"]["detector"], "MoveInZone")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertTrue(applied["created_uids"][0].startswith("hosts/Server/AppDataDetector."))
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(registry.verify(plan["plan_id"])["still_present"], [])

    def test_temp_device_template_requires_camera_uid(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        gap = registry.plan("temp_device_template", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("camera_uid", gap["message"])

    def test_temp_device_template_plan_apply_verify_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeTemplateClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "temp_device_template",
            {"camera_uid": "hosts/Server/DeviceIpint.1", "display_name_hint": "smoke"},
        )
        self.assertEqual(plan["workflow"], "temp_device_template")
        self.assertEqual(plan["steps"][0]["operation"], "add_template")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(applied["created_uids"]), 1)
        template_id = applied["created_uids"][0]
        self.assertTrue(template_id.startswith("codex-"))
        self.assertIn(template_id, client.templates)
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertNotIn(template_id, client.templates)

    def test_external_event_inject_requires_access_point(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeEventClient(), host="hosts/Server")
        gap = registry.plan("external_event_inject", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("access_point", gap["message"])

    def test_external_event_inject_plan_apply_no_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeEventClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "external_event_inject",
            {"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "test"},
        )
        self.assertEqual(plan["workflow"], "external_event_inject")
        self.assertEqual(plan["steps"][0]["operation"], "http_post")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(client.posts[0]["path"], "/v1/detectors/external:raiseOccasionalEvent")
        self.assertEqual(client.posts[0]["body"]["accessPoint"], "hosts/Server/DetectorEx.1/EventSupplier")
        # Rollback for one-shot events is a no-op (no UIDs created).
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(rolled["removed_uids"], [])

    def test_temp_macro_plan_apply_verify_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMacroClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("temp_macro", {"display_name_hint": "smoke"})
        self.assertEqual(plan["workflow"], "temp_macro")
        self.assertEqual(plan["steps"][0]["operation"], "add_macro")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(applied["created_uids"]), 1)
        macro_id = applied["created_uids"][0]
        self.assertIn(macro_id, client.macros)
        verified = registry.verify(plan["plan_id"])
        self.assertEqual(verified["still_present"], [macro_id])
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertNotIn(macro_id, client.macros)
        self.assertEqual(registry.verify(plan["plan_id"])["still_present"], [])

    def test_create_camera_requires_display_name(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        reg = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        gap = reg.plan("create_camera", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("display_name", gap["message"])

    def test_create_camera_persistent_marker(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = reg.plan("create_camera", {"display_name": "test-cam", "ip": "10.0.0.5", "login": "u", "password": "p"})
        self.assertTrue(plan.get("persistent"))
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertTrue(applied["created_uids"][0].startswith("hosts/Server/DeviceIpint."))

    def test_create_macro_persistent(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMacroClient()
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = reg.plan("create_macro", {"name": "test-macro", "enabled": True})
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertIn(applied["created_uids"][0], client.macros)

    def test_set_unit_properties_requires_uid_and_properties(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        reg = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")
        self.assertEqual(reg.plan("set_unit_properties", {})["status"], "gap")
        self.assertEqual(reg.plan("set_unit_properties", {"uid": "x"})["status"], "gap")
        self.assertEqual(reg.plan("set_unit_properties", {"properties": [{"id": "x"}]})["status"], "gap")

    def test_set_unit_properties_applies_change(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        client.units["hosts/Server/DeviceIpint.99"] = {"type": "DeviceIpint", "properties": []}
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = reg.plan("set_unit_properties", {
            "uid": "hosts/Server/DeviceIpint.99",
            "properties": [{"id": "display_name", "value_string": "renamed"}],
        })
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(client.units["hosts/Server/DeviceIpint.99"]["properties"][0]["value_string"], "renamed")

    def test_create_layout_persistent(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeLayoutClient()
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = reg.plan("create_layout", {
            "name": "test-layout",
            "cells": ["hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"],
            "rows": 1,
            "cols": 1,
        })
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        layout_id = applied["created_uids"][0]
        self.assertIn(layout_id, client.layouts)
        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertNotIn(layout_id, client.layouts)

    def test_default_mode_is_read_only(self) -> None:
        """Without explicit enablement, apply() must refuse even with a valid plan_id."""
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server", enabled=False)
        plan = registry.plan("temp_camera", {})
        result = registry.apply(plan["plan_id"], confirmation=f"CONFIRM-{plan['workflow']}")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("disabled", result["message"].lower())
        self.assertEqual(client.calls, [])

    def test_operator_client_change_maps_dispatches(self) -> None:
        from axxon_mcp_operator import AxxonOperatorClient

        class FakeApi:
            def __init__(self):
                self.calls: list[tuple[str, dict]] = []

            def change_maps(self, payload):
                self.calls.append(("change_maps", payload))
                return {"status": 200, "body": {"result": True}}

        api = FakeApi()
        c = AxxonOperatorClient(api)
        out = c.change_maps_via_api({"added": [{"meta": {"name": "x"}}]})
        self.assertEqual(out["status"], 200)
        self.assertEqual(api.calls[0][0], "change_maps")


if __name__ == "__main__":
    unittest.main()
