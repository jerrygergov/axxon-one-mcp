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
        self.reads: list[str] = []
        self._next_uid = 0
        self.units: dict[str, dict] = {}
        self.parents: dict[str, str] = {}

    def _alloc_uid(self, unit_type: str) -> str:
        self._next_uid += 1
        return f"hosts/Server/{unit_type}.{self._next_uid}"

    def _merge_properties(self, current: list[dict], changed: list[dict]) -> list[dict]:
        merged = [dict(prop) for prop in current]
        by_id = {prop.get("id"): idx for idx, prop in enumerate(merged)}
        for prop in changed:
            prop_id = prop.get("id")
            if prop_id in by_id:
                merged[by_id[prop_id]] = dict(prop)
            else:
                merged.append(dict(prop))
        return merged

    def change_config(self, payload: dict) -> dict:
        self.calls.append(payload)
        added_uids: list[str] = []
        failed: list[dict] = []
        for parent in payload.get("added", []):
            parent_uid = parent["uid"]
            for unit in parent.get("units", []):
                uid = unit.get("uid") or self._alloc_uid(unit["type"])
                self.units[uid] = {
                    "type": unit["type"],
                    "properties": unit.get("properties", []),
                    "units": unit.get("units", []),
                }
                self.parents[uid] = parent_uid
                added_uids.append(uid)
        for unit in payload.get("changed", []):
            uid = unit["uid"]
            if uid not in self.units:
                failed.append({"uid": uid, "reason": "missing"})
                continue
            if "type" in unit:
                self.units[uid]["type"] = unit["type"]
            if "properties" in unit:
                self.units[uid]["properties"] = self._merge_properties(
                    self.units[uid].get("properties", []),
                    unit.get("properties", []),
                )
            if "units" in unit:
                self.units[uid]["units"] = unit.get("units", [])
        for unit in payload.get("removed", []):
            uid = unit["uid"]
            if uid not in self.units:
                failed.append({"uid": uid, "reason": "missing"})
                continue
            del self.units[uid]
            self.parents.pop(uid, None)
        return {"added": added_uids, "failed": failed, "failed_reason": []}

    def read_unit(self, uid: str) -> dict:
        self.reads.append(uid)
        if uid not in self.units:
            return {"units": []}
        return {"units": [{"uid": uid, **self.units[uid], "parent_uid": self.parents.get(uid)}]}


class FailDetectorSnapshotRestoreClient(FakeMutationClient):
    """Fails only detector snapshot restore payloads."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_restore_for: set[str] = set()

    def change_config(self, payload: dict) -> dict:
        for unit in payload.get("changed", []):
            uid = unit.get("uid")
            if uid in self.fail_restore_for:
                self.calls.append(payload)
                return {
                    "added": [],
                    "failed": [{"uid": uid, "reason": "restore failed"}],
                    "failed_reason": ["restore failed"],
                }
        for parent in payload.get("added", []):
            for unit in parent.get("units", []):
                uid = unit.get("uid")
                if uid in self.fail_restore_for:
                    self.calls.append(payload)
                    return {
                        "added": [],
                        "failed": [{"uid": uid, "reason": "restore failed"}],
                        "failed_reason": ["restore failed"],
                    }
        return super().change_config(payload)


class OmitParentReadUnitClient(FakeMutationClient):
    """Simulates read_unit responses that omit parent metadata."""

    def read_unit(self, uid: str) -> dict:
        self.reads.append(uid)
        if uid not in self.units:
            return {"units": []}
        return {"units": [{"uid": uid, **self.units[uid]}]}


def _test_find_property(properties: list[dict], prop_id: str) -> dict:
    for prop in properties:
        if prop.get("id") == prop_id or prop.get("name") == prop_id or prop.get("key") == prop_id:
            return prop
    raise AssertionError(f"missing property {prop_id}")


def _test_detector_input_properties(unit: dict) -> list[dict]:
    input_prop = _test_find_property(unit["properties"], "input")
    return input_prop["properties"]


def _test_detector_camera_properties(unit: dict) -> list[dict]:
    camera_ref = _test_find_property(_test_detector_input_properties(unit), "camera_ref")
    return camera_ref["properties"]


class FailSecondAddMutationClient(FakeMutationClient):
    """Creates the first added unit, then fails the next add without creating it."""

    def __init__(self) -> None:
        super().__init__()
        self.add_calls = 0

    def change_config(self, payload: dict) -> dict:
        if payload.get("added"):
            self.add_calls += 1
            if self.add_calls == 2:
                self.calls.append(payload)
                return {
                    "added": [],
                    "failed": [{"uid": "pending-AppDataDetector", "reason": "simulated failure"}],
                    "failed_reason": ["simulated failure"],
                }
        return super().change_config(payload)


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


class FakeArchiveMaintenanceClient(FakeMutationClient):
    """Records archive maintenance calls."""

    def __init__(self) -> None:
        super().__init__()
        self.archive_calls: list[tuple[str, str, list[str], dict]] = []

    def archive_format_volumes_via_api(self, access_point: str, volume_ids: list[str]) -> dict:
        self.archive_calls.append(("format", access_point, list(volume_ids), {}))
        return {"status": 200, "body": {"accepted": True}}

    def archive_reindex_via_api(self, access_point: str, volume_ids: list[str], *, full: bool = True) -> dict:
        self.archive_calls.append(("reindex", access_point, list(volume_ids), {"full": full}))
        return {"status": 200, "body": {"started": True}}

    def archive_cancel_reindex_via_api(self, access_point: str, volume_ids: list[str]) -> dict:
        self.archive_calls.append(("cancel_reindex", access_point, list(volume_ids), {}))
        return {"status": 200, "body": {"cancelled": True}}


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

        appdata_plan = registry.plan("create_appdata_detector_full", {
            "display_name": "persistent-appdata-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MoveInZone",
            "properties": [{"id": "zone", "value_string": "entry"}],
        })
        appdata_applied = registry.apply(appdata_plan["plan_id"], appdata_plan["confirmation_token"])
        self.assertEqual(appdata_applied["status"], "applied")
        self.assertEqual(len(appdata_applied["created_uids"]), 2)
        appdata_verified = registry.verify(appdata_plan["plan_id"])
        self.assertEqual(appdata_verified["detector_checks"], {
            "display_name": True,
            "detector": True,
            "video_source_ap": True,
            "vmda_source_ap": True,
        })
        appdata_rolled = registry.rollback(appdata_plan["plan_id"], appdata_plan["rollback_confirmation_token"])
        self.assertEqual(appdata_rolled["status"], "rolled_back")
        self.assertEqual(len(appdata_rolled["removed_uids"]), 2)
        self.assertEqual(registry.verify(appdata_plan["plan_id"])["still_present"], [])

    def test_create_av_detector_full_plan_includes_full_properties_and_provenance(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        video_ap = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"

        plan = module._build_create_av_detector_full_plan("hosts/Server", {
            "display_name": "persistent-motion",
            "video_source_ap": video_ap,
            "detector": "MotionDetection",
            "schema_source": {"source": "fixture-schema", "unit_type": "AVDetector"},
            "properties": [
                {"id": "threshold", "value_int32": 42},
                {"id": "input", "value_string": "caller-input-must-not-replace-binding"},
            ],
        })

        self.assertEqual(plan["workflow"], "create_av_detector_full")
        self.assertTrue(plan["caller_owns_lifecycle"])
        self.assertEqual(plan["rollback"]["strategy"], "remove_created_uids")
        self.assertEqual(plan["schema_source"], {"source": "fixture-schema", "unit_type": "AVDetector"})
        self.assertEqual(plan["source_bindings"], {"video_source_ap": video_ap})
        self.assertEqual(plan["expected"], {
            "display_name": "persistent-motion",
            "detector": "MotionDetection",
            "video_source_ap": video_ap,
        })
        props = plan["steps"][0]["payload"]["added"][0]["units"][0]["properties"]
        self.assertEqual([prop["id"] for prop in props], ["display_name", "input", "threshold"])
        self.assertEqual(plan["diff"], {"added": [{"unit_type": "AVDetector", "properties": props}]})

    def test_create_appdata_detector_full_plan_chains_scene_and_preserves_parameter_tree(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        video_ap = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"

        plan = module._build_create_appdata_detector_full_plan("hosts/Server", {
            "name": "persistent-appdata",
            "video_source_ap": video_ap,
            "detector": "MoveInZone",
            "schema_provenance": ["template", "operator"],
            "parameter_tree": {
                "properties": [
                    {"id": "zone", "value_string": "main-entry"},
                    {"id": "display_name", "value_string": "caller-name-must-not-replace-display-name"},
                ],
            },
        })

        self.assertEqual(plan["workflow"], "create_appdata_detector_full")
        self.assertTrue(plan["caller_owns_lifecycle"])
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["unit_type"], "AVDetector")
        self.assertEqual(plan["steps"][1]["unit_type"], "AppDataDetector")
        self.assertEqual(plan["steps"][1]["resolve_vmda_from_step"], 0)
        self.assertEqual(plan["steps"][1]["appdata_template"]["properties"], [{"id": "zone", "value_string": "main-entry"}])
        self.assertEqual(plan["schema_source"], ["template", "operator"])
        self.assertEqual(plan["expected"], {
            "display_name": "persistent-appdata",
            "detector": "MoveInZone",
            "video_source_ap": video_ap,
            "vmda_source_ap": "<chain-created from step 0>",
        })
        self.assertEqual(plan["source_bindings"], {
            "video_source_ap": video_ap,
            "vmda_source_ap": "<chain-created from step 0>",
        })
        appdata_diff = plan["diff"]["added"][1]
        self.assertEqual(appdata_diff["unit_type"], "AppDataDetector")
        self.assertEqual([prop["id"] for prop in appdata_diff["properties"]], ["display_name", "input", "zone"])

    def test_create_detector_full_workflows_are_registered_and_apply_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        self.assertIn("create_av_detector_full", registry.known_workflows())
        self.assertIn("create_appdata_detector_full", registry.known_workflows())

        plan = registry.plan("create_av_detector_full", {
            "display_name": "persistent-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MotionDetection",
            "properties": [{"id": "threshold", "value_int32": 7}],
        })
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        verified = registry.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["detector_checks"], {
            "display_name": True,
            "detector": True,
            "video_source_ap": True,
        })
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(registry.verify(plan["plan_id"])["still_present"], [])

        appdata_plan = registry.plan("create_appdata_detector_full", {
            "display_name": "persistent-appdata-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MoveInZone",
            "properties": [{"id": "zone", "value_string": "entry"}],
        })
        appdata_applied = registry.apply(appdata_plan["plan_id"], appdata_plan["confirmation_token"])
        self.assertEqual(appdata_applied["status"], "applied")
        self.assertEqual(len(appdata_applied["created_uids"]), 2)
        appdata_verified = registry.verify(appdata_plan["plan_id"])
        self.assertEqual(appdata_verified["detector_checks"], {
            "display_name": True,
            "detector": True,
            "video_source_ap": True,
            "vmda_source_ap": True,
        })
        appdata_rolled = registry.rollback(appdata_plan["plan_id"], appdata_plan["rollback_confirmation_token"])
        self.assertEqual(appdata_rolled["status"], "rolled_back")
        self.assertEqual(len(appdata_rolled["removed_uids"]), 2)
        self.assertEqual(registry.verify(appdata_plan["plan_id"])["still_present"], [])

    def test_create_av_detector_full_verify_fails_on_wrong_detector_config(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("create_av_detector_full", {
            "display_name": "persistent-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MotionDetection",
        })
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")

        unit = client.units[applied["created_uids"][0]]
        _test_find_property(unit["properties"], "display_name")["value_string"] = "wrong-name"
        input_properties = _test_detector_input_properties(unit)
        _test_find_property(input_properties, "detector")["value_string"] = "SceneDescription"
        _test_find_property(input_properties, "camera_ref")["value_string"] = (
            "hosts/Server/DeviceIpint.99/SourceEndpoint.video:0:0"
        )

        verified = registry.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "error")
        self.assertEqual(verified["detector_checks"], {
            "display_name": False,
            "detector": False,
            "video_source_ap": False,
        })

        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        post = registry.verify(plan["plan_id"])
        self.assertEqual(post["status"], "verified")
        self.assertEqual(post["still_present"], [])
        self.assertNotIn("detector_checks", post)

    def test_create_av_detector_full_verify_accepts_live_normalized_readback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        video_ap = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"
        plan = registry.plan("create_av_detector_full", {
            "display_name": "persistent-live-normalized",
            "video_source_ap": video_ap,
            "detector": "MotionDetection",
        })
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        uid = applied["created_uids"][0]
        client.units[uid]["properties"] = [
            {"id": "display_name", "value_string": "persistent-live-normalized"},
            {"id": "detector", "value_string": "MotionDetection", "readonly": True},
            {"id": "streaming_id", "value_string": video_ap, "internal": True},
            {
                "id": "input",
                "value_string": "Video",
                "enum_constraint": {
                    "items": [{
                        "value_string": "Video",
                        "properties": [
                            {"id": "detector", "value_string": "MotionDetection"},
                            {"id": "camera_ref", "value_string": video_ap},
                        ],
                    }]
                },
            },
        ]

        verified = registry.verify(plan["plan_id"])

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["detector_checks"], {
            "display_name": True,
            "detector": True,
            "video_source_ap": True,
        })

    def test_create_appdata_detector_full_verify_requires_chained_vmda_uid(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("create_appdata_detector_full", {
            "display_name": "persistent-appdata-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MoveInZone",
        })
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        scene_uid, appdata_uid = applied["created_uids"]

        appdata_unit = client.units[appdata_uid]
        streaming_id = _test_find_property(_test_detector_camera_properties(appdata_unit), "streaming_id")
        streaming_id["value_string"] = "hosts/Server/AVDetector.999/SourceEndpoint.vmda"
        unrelated = registry.verify(plan["plan_id"])
        self.assertEqual(unrelated["status"], "error")
        self.assertFalse(unrelated["detector_checks"]["vmda_source_ap"])

        streaming_id["value_string"] = f"{scene_uid}/SourceEndpoint.vmda"
        chained = registry.verify(plan["plan_id"])
        self.assertEqual(chained["status"], "verified")
        self.assertTrue(chained["detector_checks"]["vmda_source_ap"])

    def test_create_appdata_detector_full_verify_accepts_live_normalized_readback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        video_ap = "hosts/Server/DeviceIpint.14/SourceEndpoint.video:0:0"
        vmda_ap = "hosts/Server/AVDetector.72/SourceEndpoint.vmda"
        plan = registry.plan("create_appdata_detector_full", {
            "display_name": "persistent-appdata-live-normalized",
            "video_source_ap": video_ap,
            "vmda_source_ap": vmda_ap,
            "detector": "MoveInZone",
        })
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        uid = applied["created_uids"][0]
        client.units[uid]["properties"] = [
            {"id": "display_name", "value_string": "persistent-appdata-live-normalized"},
            {"id": "detector", "value_string": "MoveInZone", "readonly": True},
            {"id": "streaming_id", "value_string": vmda_ap, "internal": True},
            {
                "id": "input",
                "value_string": "TargetList",
                "enum_constraint": {
                    "items": [{
                        "value_string": "TargetList",
                        "properties": [
                            {"id": "detector", "value_string": "MoveInZone"},
                            {
                                "id": "camera_ref",
                                "value_string": video_ap,
                                "enum_constraint": {
                                    "items": [{
                                        "value_string": video_ap,
                                        "properties": [{"id": "streaming_id", "value_string": vmda_ap}],
                                    }]
                                },
                            },
                        ],
                    }]
                },
            },
        ]

        verified = registry.verify(plan["plan_id"])

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["detector_checks"], {
            "display_name": True,
            "detector": True,
            "video_source_ap": True,
            "vmda_source_ap": True,
        })

    def test_create_appdata_detector_full_partial_apply_records_scene_for_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FailSecondAddMutationClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan("create_appdata_detector_full", {
            "display_name": "persistent-appdata-registered",
            "video_source_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "detector": "MoveInZone",
        })

        result = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(result["status"], "error")
        scene_uids = [uid for uid, unit in client.units.items() if unit["type"] == "AVDetector"]
        self.assertEqual(len(scene_uids), 1)
        scene_uid = scene_uids[0]
        self.assertEqual(registry._state[plan["plan_id"]]["status"], "error")
        self.assertEqual(registry._state[plan["plan_id"]]["created_uids"], [scene_uid])
        self.assertEqual(registry._state[plan["plan_id"]]["created_kinds"], ["unit"])

        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(rolled["removed_uids"], [scene_uid])
        self.assertNotIn(scene_uid, client.units)

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

    def test_update_detector_parameters_captures_snapshot_verifies_and_rolls_back(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        target_uid = "hosts/Server/AVDetector.42"
        original_properties = [
            {"id": "display_name", "value_string": "motion"},
            {"id": "threshold", "value_int32": 5},
        ]
        requested_properties = [{"id": "threshold", "value_int32": 8}]
        client.units[target_uid] = {"type": "AVDetector", "properties": list(original_properties), "units": []}
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan(
            "update_detector_parameters",
            {"uid": target_uid, "properties": requested_properties},
        )

        self.assertEqual(plan["workflow"], "update_detector_parameters")
        self.assertTrue(plan["persistent"])
        self.assertEqual(plan["risk"], "mutation")
        self.assertEqual(plan["confirmation_token"], "CONFIRM-update_detector_parameters")
        self.assertEqual(plan["rollback_confirmation_token"], "CONFIRM-update_detector_parameters-rollback")
        self.assertEqual(plan["rollback"]["strategy"], "restore_detector_snapshot")
        self.assertEqual(plan["snapshot_capture"], {
            "source": "read_unit",
            "snapshot_key": f"unit:{target_uid}",
            "target_uid": target_uid,
            "target_role": "detector",
        })
        self.assertEqual(plan["diff"]["changed"][0]["target_uid"], target_uid)
        self.assertEqual(plan["diff"]["changed"][0]["property_paths"], ["threshold"])
        self.assertEqual(plan["diff"]["changed"][0]["before"], "<captured during apply>")
        self.assertEqual(plan["diff"]["changed"][0]["after"], requested_properties)
        self.assertEqual(client.calls, [])
        self.assertEqual(client.reads, [])

        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["snapshots"][0]["target_uid"], target_uid)
        self.assertEqual(applied["snapshots"][0]["unit"]["properties"], original_properties)
        self.assertEqual(client.reads, [target_uid])
        self.assertEqual(client.calls[-1], {"changed": [{"uid": target_uid, "properties": requested_properties}]})
        self.assertEqual(_test_find_property(client.units[target_uid]["properties"], "threshold")["value_int32"], 8)

        verified = reg.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["target"]["still_present"])
        self.assertEqual(verified["property_checks"], {"threshold": True})

        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(rolled["restored_uids"], [target_uid])
        self.assertEqual(client.calls[-1], {"changed": [{"uid": target_uid, "properties": [{"id": "threshold", "value_int32": 5}]}]})
        self.assertEqual(client.units[target_uid]["properties"], original_properties)

    def test_update_detector_parameters_rollback_restore_failure_is_error(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FailDetectorSnapshotRestoreClient()
        target_uid = "hosts/Server/AVDetector.42"
        original_properties = [{"id": "threshold", "value_int32": 5}]
        requested_properties = [{"id": "threshold", "value_int32": 8}]
        client.units[target_uid] = {"type": "AVDetector", "properties": list(original_properties), "units": []}
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan("update_detector_parameters", {"uid": target_uid, "properties": requested_properties})
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        client.fail_restore_for.add(target_uid)

        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        self.assertEqual(rolled["status"], "error")
        self.assertEqual(rolled["restored_uids"], [])
        self.assertEqual(rolled["failed"], [{"uid": target_uid, "reason": ["restore failed"]}])

    def test_update_detector_parameters_verify_after_rollback_infers_omitted_parent(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = OmitParentReadUnitClient()
        target_uid = "hosts/Server/AVDetector.42"
        original_properties = [{"id": "threshold", "value_int32": 5}]
        requested_properties = [{"id": "threshold", "value_int32": 8}]
        client.units[target_uid] = {"type": "AVDetector", "properties": list(original_properties), "units": []}
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan("update_detector_parameters", {"uid": target_uid, "properties": requested_properties})
        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["snapshots"][0]["parent_uid"], "hosts/Server")
        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")

        verified = reg.verify(plan["plan_id"])

        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["snapshot_restored"])

    def test_update_detector_parameters_verify_after_rollback_requires_snapshot(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FailDetectorSnapshotRestoreClient()
        target_uid = "hosts/Server/AVDetector.42"
        client.units[target_uid] = {
            "type": "AVDetector",
            "properties": [{"id": "threshold", "value_int32": 5}],
            "units": [],
        }
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan(
            "update_detector_parameters",
            {"uid": target_uid, "properties": [{"id": "threshold", "value_int32": 8}]},
        )
        reg.apply(plan["plan_id"], plan["confirmation_token"])
        client.fail_restore_for.add(target_uid)
        reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        verified = reg.verify(plan["plan_id"])

        self.assertEqual(verified["status"], "error")
        self.assertEqual(verified["target"], {"uid": target_uid, "still_present": True})

    def test_update_detector_visual_element_captures_snapshot_verifies_and_rolls_back(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        target_uid = "hosts/Server/AVDetector.42/VisualElement.1"
        original_properties = [
            {"id": "display_name", "value_string": "Zone A"},
            {"id": "color", "value_string": "#ff0000"},
        ]
        requested_properties = [{"id": "color", "value_string": "#00ff00"}]
        client.units[target_uid] = {"type": "VisualElement", "properties": list(original_properties), "units": []}
        client.parents[target_uid] = "hosts/Server/AVDetector.42"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan(
            "update_detector_visual_element",
            {"visual_element_uid": target_uid, "properties": requested_properties},
        )

        self.assertEqual(plan["workflow"], "update_detector_visual_element")
        self.assertEqual(plan["steps"][0]["operation"], "change_detector_snapshot_unit")
        self.assertEqual(plan["snapshot_capture"]["target_role"], "visual_element")
        self.assertEqual(plan["diff"]["changed"][0]["target_uid"], target_uid)
        self.assertEqual(plan["diff"]["changed"][0]["property_paths"], ["color"])
        self.assertEqual(client.calls, [])
        self.assertEqual(client.reads, [])

        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["snapshots"][0]["unit"]["properties"], original_properties)
        verified = reg.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["target"]["still_present"])
        self.assertEqual(verified["property_checks"], {"color": True})

        _test_find_property(client.units[target_uid]["properties"], "color")["value_string"] = "#000000"
        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(client.units[target_uid]["properties"], original_properties)

    def test_delete_detector_captures_snapshot_deletes_verifies_and_readds_on_rollback(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        target_uid = "hosts/Server/AppDataDetector.77"
        original_unit = {
            "type": "AppDataDetector",
            "properties": [
                {"id": "display_name", "value_string": "queue analytics"},
                {"id": "zone", "value_string": "entry"},
            ],
            "units": [],
        }
        client.units[target_uid] = dict(original_unit)
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan("delete_detector", {"uid": target_uid})

        self.assertEqual(plan["workflow"], "delete_detector")
        self.assertEqual(plan["steps"][0], {
            "operation": "remove_detector_snapshot_unit",
            "target_uid": target_uid,
            "payload": {"removed": [{"uid": target_uid}]},
        })
        self.assertEqual(plan["diff"], {
            "removed": [{
                "target_uid": target_uid,
                "delete": True,
                "before": "<captured during apply>",
            }]
        })
        self.assertEqual(client.calls, [])
        self.assertEqual(client.reads, [])

        applied = reg.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["snapshots"][0]["parent_uid"], "hosts/Server")
        self.assertNotIn(target_uid, client.units)

        verified = reg.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertFalse(verified["target"]["still_present"])

        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(rolled["restored_uids"], [target_uid])
        self.assertIn(target_uid, client.units)
        self.assertEqual(client.parents[target_uid], "hosts/Server")
        self.assertEqual(client.units[target_uid], original_unit)

    def test_delete_detector_rollback_readd_failure_is_error(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FailDetectorSnapshotRestoreClient()
        target_uid = "hosts/Server/AppDataDetector.77"
        client.units[target_uid] = {
            "type": "AppDataDetector",
            "properties": [{"id": "display_name", "value_string": "queue analytics"}],
            "units": [],
        }
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan("delete_detector", {"uid": target_uid})
        reg.apply(plan["plan_id"], plan["confirmation_token"])
        client.fail_restore_for.add(target_uid)

        rolled = reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        self.assertEqual(rolled["status"], "error")
        self.assertEqual(rolled["restored_uids"], [])
        self.assertEqual(rolled["failed"], [{"uid": target_uid, "reason": ["restore failed"]}])

    def test_delete_detector_verify_after_rollback_requires_restored_snapshot(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FailDetectorSnapshotRestoreClient()
        target_uid = "hosts/Server/AppDataDetector.77"
        client.units[target_uid] = {
            "type": "AppDataDetector",
            "properties": [{"id": "display_name", "value_string": "queue analytics"}],
            "units": [],
        }
        client.parents[target_uid] = "hosts/Server"
        reg = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = reg.plan("delete_detector", {"uid": target_uid})
        reg.apply(plan["plan_id"], plan["confirmation_token"])
        client.fail_restore_for.add(target_uid)
        reg.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

        verified = reg.verify(plan["plan_id"])

        self.assertEqual(verified["status"], "error")
        self.assertEqual(verified["target"], {"uid": target_uid, "still_present": False})

    def test_archive_policy_update_requires_descriptor_backed_properties(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")

        missing_descriptor = registry.plan(
            "archive_policy_update",
            {"uid": "hosts/Server/MultimediaStorage.1", "properties": [{"id": "day_depth", "value_int32": 7}]},
        )
        self.assertEqual(missing_descriptor["status"], "gap")
        self.assertIn("descriptor", missing_descriptor["message"])

        guessed_field = registry.plan(
            "archive_policy_update",
            {
                "uid": "hosts/Server/MultimediaStorage.1",
                "descriptor": {"properties": [{"id": "day_depth"}]},
                "properties": [{"id": "undocumented_policy", "value_bool": True}],
            },
        )
        self.assertEqual(guessed_field["status"], "gap")
        self.assertIn("descriptor-backed", guessed_field["message"])

    def test_archive_policy_update_rejects_guessed_nested_descriptor_properties(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")

        guessed_nested = registry.plan(
            "archive_policy_update",
            {
                "uid": "hosts/Server/MultimediaStorage.1",
                "descriptor": {
                    "properties": [
                        {
                            "id": "retention",
                            "properties": [
                                {"id": "day_depth"},
                            ],
                        }
                    ]
                },
                "properties": [
                    {
                        "id": "retention",
                        "properties": [
                            {"id": "undocumented_nested_policy", "value_bool": True},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(guessed_nested["status"], "gap")
        self.assertIn("retention.undocumented_nested_policy", guessed_nested["message"])

    def test_archive_policy_update_rejects_parameter_tree_wrapper_guesses(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeMutationClient(), host="hosts/Server")

        guessed_nested = registry.plan(
            "archive_policy_update",
            {
                "uid": "hosts/Server/MultimediaStorage.1",
                "descriptor": {
                    "parameter_tree": {
                        "properties": [
                            {
                                "id": "retention",
                                "parameter_tree": {
                                    "properties": [
                                        {"id": "day_depth"},
                                    ]
                                },
                            }
                        ]
                    }
                },
                "properties": [
                    {
                        "id": "retention",
                        "parameter_tree": {
                            "properties": [
                                {"id": "undocumented_nested_policy", "value_bool": True},
                            ]
                        },
                    }
                ],
            },
        )

        self.assertEqual(guessed_nested["status"], "gap")
        self.assertIn("retention.undocumented_nested_policy", guessed_nested["message"])

    def test_archive_policy_update_captures_snapshot_verifies_and_rolls_back(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeMutationClient()
        target_uid = "hosts/Server/MultimediaStorage.9"
        original_properties = [
            {"id": "display_name", "value_string": "Main archive"},
            {"id": "day_depth", "value_int32": 3},
            {"id": "storage_type", "value_string": "object"},
        ]
        requested_properties = [{"id": "day_depth", "value_int32": 5}]
        client.units[target_uid] = {"type": "MultimediaStorage", "properties": list(original_properties), "units": []}
        client.parents[target_uid] = "hosts/Server"
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")

        plan = registry.plan(
            "archive_policy_update",
            {
                "uid": target_uid,
                "descriptor": {"properties": [{"id": "day_depth"}, {"id": "storage_type"}]},
                "properties": requested_properties,
            },
        )

        self.assertEqual(plan["workflow"], "archive_policy_update")
        self.assertEqual(plan["steps"][0]["operation"], "change_archive_policy_snapshot_unit")
        self.assertEqual(plan["rollback"]["strategy"], "restore_archive_policy_snapshot")
        self.assertEqual(plan["snapshot_capture"]["target_uid"], target_uid)
        self.assertEqual(plan["diff"]["changed"][0]["property_paths"], ["day_depth"])
        self.assertEqual(client.calls, [])
        self.assertEqual(client.reads, [])

        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["snapshots"][0]["unit"]["properties"], original_properties)
        self.assertEqual(_test_find_property(client.units[target_uid]["properties"], "day_depth")["value_int32"], 5)

        verified = registry.verify(plan["plan_id"])
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["property_checks"], {"day_depth": True})

        _test_find_property(client.units[target_uid]["properties"], "day_depth")["value_int32"] = 99
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(rolled["restored_uids"], [target_uid])
        self.assertEqual(client.units[target_uid]["properties"], original_properties)

    def test_archive_maintenance_plan_gates_real_volumes_but_allows_safe_and_noop(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeArchiveMaintenanceClient(), host="hosts/Server")
        access_point = "hosts/Server/MultimediaStorage.1/Archive"

        real = registry.plan(
            "archive_format_volume",
            {"access_point": access_point, "volume_ids": ["volume-real-1"]},
        )
        self.assertEqual(real["status"], "gap")
        self.assertIn("safe-volume", real["message"])

        declared_safe = registry.plan(
            "archive_format_volume",
            {
                "access_point": access_point,
                "volume_ids": ["volume-real-1"],
                "safe_volume_ids": ["volume-real-1"],
            },
        )
        self.assertEqual(declared_safe["status"], "planned")
        self.assertFalse(declared_safe["noop_volume_only"])

        noop = registry.plan(
            "archive_reindex",
            {"access_point": access_point, "volume_ids": ["codex-nonexistent-volume-1"]},
        )
        self.assertEqual(noop["status"], "planned")
        self.assertTrue(noop["noop_volume_only"])

    def test_archive_maintenance_rejects_broad_boolean_safe_volume_declaration(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        registry = module.OperatorRegistry(client_factory=lambda: FakeArchiveMaintenanceClient(), host="hosts/Server")
        access_point = "hosts/Server/MultimediaStorage.1/Archive"

        broad_declared = registry.plan(
            "archive_format_volume",
            {
                "access_point": access_point,
                "volume_ids": ["volume-real-1"],
                "safe_volume_declared": True,
            },
        )

        self.assertEqual(broad_declared["status"], "gap")
        self.assertIn("safe-volume", broad_declared["message"])

    def test_archive_maintenance_apply_requires_env_gate(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeArchiveMaintenanceClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        plan = registry.plan(
            "archive_format_volume",
            {
                "access_point": "hosts/Server/MultimediaStorage.1/Archive",
                "volume_ids": ["codex-nonexistent-volume-1"],
            },
        )

        old_value = module._os.environ.pop("AXXON_ARCHIVE_MAINTENANCE_APPROVE", None)
        try:
            applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        finally:
            if old_value is not None:
                module._os.environ["AXXON_ARCHIVE_MAINTENANCE_APPROVE"] = old_value

        self.assertEqual(applied["status"], "rejected")
        self.assertIn("AXXON_ARCHIVE_MAINTENANCE_APPROVE=1", applied["message"])
        self.assertEqual(client.archive_calls, [])

    def test_archive_maintenance_dispatches_noop_volumes_when_env_gate_is_set(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeArchiveMaintenanceClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        access_point = "hosts/Server/MultimediaStorage.1/Archive"
        old_value = module._os.environ.get("AXXON_ARCHIVE_MAINTENANCE_APPROVE")
        module._os.environ["AXXON_ARCHIVE_MAINTENANCE_APPROVE"] = "1"
        try:
            workflows = [
                ("archive_format_volume", "format", {}),
                ("archive_reindex", "reindex", {"full": False}),
                ("archive_cancel_reindex", "cancel_reindex", {}),
            ]
            for workflow, expected_call, extra in workflows:
                plan = registry.plan(
                    workflow,
                    {
                        "access_point": access_point,
                        "volume_ids": [f"codex-nonexistent-{workflow}"],
                        **extra,
                    },
                )
                applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
                self.assertEqual(applied["status"], "applied")
                self.assertEqual(applied["created_uids"], [])
                self.assertEqual(client.archive_calls[-1][0], expected_call)
                self.assertEqual(client.archive_calls[-1][1], access_point)
                self.assertEqual(client.archive_calls[-1][2], [f"codex-nonexistent-{workflow}"])
        finally:
            if old_value is None:
                module._os.environ.pop("AXXON_ARCHIVE_MAINTENANCE_APPROVE", None)
            else:
                module._os.environ["AXXON_ARCHIVE_MAINTENANCE_APPROVE"] = old_value

    def test_archive_reindex_rollback_cancels_started_reindex(self) -> None:
        module = importlib.import_module("axxon_mcp_operator")
        client = FakeArchiveMaintenanceClient()
        registry = module.OperatorRegistry(client_factory=lambda: client, host="hosts/Server")
        access_point = "hosts/Server/MultimediaStorage.1/Archive"
        old_value = module._os.environ.get("AXXON_ARCHIVE_MAINTENANCE_APPROVE")
        module._os.environ["AXXON_ARCHIVE_MAINTENANCE_APPROVE"] = "1"
        try:
            plan = registry.plan(
                "archive_reindex",
                {"access_point": access_point, "volume_ids": ["codex-nonexistent-reindex-rollback"]},
            )
            applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
            self.assertEqual(applied["status"], "applied")

            rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])

            self.assertEqual(rolled["status"], "rolled_back")
            self.assertEqual(client.archive_calls[-1], (
                "cancel_reindex",
                access_point,
                ["codex-nonexistent-reindex-rollback"],
                {},
            ))
        finally:
            if old_value is None:
                module._os.environ.pop("AXXON_ARCHIVE_MAINTENANCE_APPROVE", None)
            else:
                module._os.environ["AXXON_ARCHIVE_MAINTENANCE_APPROVE"] = old_value

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
        self.assertTrue(plan["caller_owns_lifecycle"])
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

    def test_temp_wall_plan_includes_register_step(self) -> None:
        from axxon_mcp_operator import _build_temp_wall_plan

        plan = _build_temp_wall_plan("hosts/Server", {"name": "codex-w", "display_name": "Codex Wall"})
        self.assertEqual(plan["workflow"], "temp_wall")
        self.assertEqual(plan["risk"], "mutation")
        self.assertFalse(plan["persistent"])
        self.assertEqual(plan["steps"][0]["operation"], "register_wall")
        self.assertEqual(plan["steps"][0]["params"]["name"], "codex-w")
        self.assertEqual(plan["confirmation_token"], "CONFIRM-temp_wall")
        self.assertEqual(plan["rollback_confirmation_token"], "CONFIRM-temp_wall-rollback")

    def test_videowall_register_persistent_no_auto_rollback(self) -> None:
        from axxon_mcp_operator import _build_videowall_register_plan

        plan = _build_videowall_register_plan("hosts/Server", {"name": "perm", "display_name": "Perm"})
        self.assertEqual(plan["workflow"], "videowall_register")
        self.assertTrue(plan["persistent"])
        self.assertEqual(plan["rollback"]["strategy"], "unregister_wall")

    def test_videowall_change_requires_cookie(self) -> None:
        from axxon_mcp_operator import _build_videowall_change_plan

        gap = _build_videowall_change_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("cookie", gap["message"])
        plan = _build_videowall_change_plan("hosts/Server", {"cookie": "ck", "data_b64": "AAA=", "seq_number": 2})
        self.assertEqual(plan["steps"][0]["operation"], "change_wall")
        self.assertEqual(plan["steps"][0]["params"]["cookie"], "ck")
        self.assertEqual(plan["steps"][0]["params"]["seq_number"], 2)
        self.assertNotIn("ck", plan["intent"])
        self.assertNotIn("cookie_prefix", plan["expected"])
        self.assertTrue(plan["expected"]["cookie_present"])

    def test_videowall_set_control_data_requires_wall_id(self) -> None:
        from axxon_mcp_operator import _build_videowall_set_control_data_plan

        gap = _build_videowall_set_control_data_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_videowall_set_control_data_plan(
            "hosts/Server",
            {"wall_id": "w-1", "data_b64": "AAA=", "seq_number": 1},
        )
        self.assertEqual(plan["steps"][0]["operation"], "set_control_data")
        self.assertEqual(plan["steps"][0]["params"]["wall_id"], "w-1")

    def test_videowall_unregister_requires_cookie(self) -> None:
        from axxon_mcp_operator import _build_videowall_unregister_plan

        gap = _build_videowall_unregister_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_videowall_unregister_plan("hosts/Server", {"cookie": "ck"})
        self.assertEqual(plan["steps"][0]["operation"], "unregister_wall")
        self.assertNotIn("ck", plan["intent"])
        self.assertNotIn("cookie_prefix", plan["expected"])
        self.assertTrue(plan["expected"]["cookie_present"])

    def test_create_map_plan_includes_added(self) -> None:
        from axxon_mcp_operator import _build_create_map_plan

        gap = _build_create_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_create_map_plan("hosts/Server", {"name": "codex-test", "type": "MAP_TYPE_RASTER"})
        self.assertEqual(plan["workflow"], "create_map")
        self.assertEqual(plan["steps"][0]["operation"], "change_maps")
        created = plan["steps"][0]["payload"]["created"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["id"], plan["expected"]["map_id"])
        self.assertEqual(created[0]["map"]["name"], "codex-test")
        self.assertEqual(created[0]["map"]["type"], "MAP_TYPE_RASTER")
        self.assertIn("image_data", created[0])
        self.assertEqual(created[0]["map"]["image_meta"]["mime_type"], "image/png")

    def test_update_map_plan_requires_map_id(self) -> None:
        from axxon_mcp_operator import _build_update_map_plan

        gap = _build_update_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_map_plan("hosts/Server", {"map_id": "m-1", "etag": "e1", "patch": {"name": "renamed"}})
        self.assertEqual(plan["steps"][0]["operation"], "change_maps")
        updated = plan["steps"][0]["payload"]["updated"]
        self.assertEqual(updated[0]["map_id"], "m-1")
        self.assertEqual(updated[0]["etag"], "e1")
        self.assertEqual(updated[0]["map"]["name"], "renamed")
        self.assertEqual(plan["rollback"]["strategy"], "restore_map_snapshot")

    def test_delete_map_plan_includes_removed(self) -> None:
        from axxon_mcp_operator import _build_delete_map_plan

        gap = _build_delete_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_delete_map_plan("hosts/Server", {"map_id": "m-1"})
        self.assertEqual(plan["steps"][0]["payload"]["removed"], ["m-1"])
        self.assertEqual(plan["rollback"]["strategy"], "restore_map_snapshot")

    def test_update_markers_plan_requires_map_id(self) -> None:
        from axxon_mcp_operator import _build_update_markers_plan

        gap = _build_update_markers_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_markers_plan(
            "hosts/Server",
            {"map_id": "m-1", "markers": [{"access_point": "hosts/Server/x"}]},
        )
        self.assertEqual(plan["steps"][0]["operation"], "update_markers")
        self.assertEqual(plan["steps"][0]["params"]["map_id"], "m-1")
        self.assertEqual(plan["steps"][0]["params"]["markers"][0]["component_name"], "hosts/Server/x")
        self.assertIn("camera_marker", plan["steps"][0]["params"]["markers"][0])

    def test_update_layout_requires_layout_id(self) -> None:
        from axxon_mcp_operator import _build_update_layout_plan

        gap = _build_update_layout_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_layout_plan(
            "hosts/Server",
            {"layout_id": "lid-1", "etag": "e", "body": {"display_name": "Renamed"}},
        )
        self.assertEqual(plan["workflow"], "update_layout")
        self.assertEqual(plan["steps"][0]["operation"], "update_layout")
        updated = plan["steps"][0]["payload"]["updated"]
        self.assertEqual(updated[0]["meta"]["layout_id"], "lid-1")
        self.assertEqual(updated[0]["meta"]["etag"], "e")
        self.assertEqual(updated[0]["body"]["display_name"], "Renamed")

    def test_delete_layout_requires_layout_id(self) -> None:
        from axxon_mcp_operator import _build_delete_layout_plan

        gap = _build_delete_layout_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_delete_layout_plan("hosts/Server", {"layout_id": "lid-1"})
        self.assertEqual(plan["steps"][0]["payload"]["removed_layouts"], ["lid-1"])
        self.assertEqual(plan["rollback"]["strategy"], "restore_layout_snapshot")

    def test_apply_dispatches_register_wall_and_records_cookie(self) -> None:
        import importlib

        ao = importlib.import_module("axxon_mcp_operator")

        class FakeClient:
            def __init__(self):
                self.calls = []

            def register_wall_via_api(self, **kwargs):
                self.calls.append(("register_wall", kwargs))
                return {"status": 200, "body": {"cookie": "ck-1", "wall_id": "w-1", "seq_number": 1}}

            def unregister_wall_via_api(self, cookie):
                self.calls.append(("unregister_wall", cookie))
                return {"status": 200, "body": {}}

        fake = FakeClient()
        registry = ao.OperatorRegistry(client_factory=lambda: fake, host="hosts/Server", enabled=True)
        plan = registry.plan("temp_wall", {"name": "codex-test"})
        self.assertEqual(plan["workflow"], "temp_wall")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertIn("w-1", applied.get("created_uids", []))
        self.assertEqual(registry._state[plan["plan_id"]]["wall_seq_numbers"], [1])
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(fake.calls[-1][0], "unregister_wall")

    def test_apply_dispatches_create_map_and_rolls_back_with_change_maps_removed(self) -> None:
        import importlib

        ao = importlib.import_module("axxon_mcp_operator")

        class FakeClient:
            def __init__(self):
                self.calls = []

            def change_maps_via_api(self, payload):
                self.calls.append(("change_maps", payload))
                return {"status": 200, "body": {}}

        fake = FakeClient()
        registry = ao.OperatorRegistry(client_factory=lambda: fake, host="hosts/Server", enabled=True)
        plan = registry.plan("create_map", {"name": "codex-map", "map_id": "m-created"})
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["created_uids"], ["m-created"])
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(fake.calls[-1], ("change_maps", {"removed": ["m-created"]}))

    def test_apply_dispatches_update_markers_and_update_layout(self) -> None:
        import importlib

        ao = importlib.import_module("axxon_mcp_operator")

        class FakeClient:
            def __init__(self):
                self.calls = []

            def update_markers_via_api(self, map_id, markers):
                self.calls.append(("update_markers", map_id, markers))
                return {"status": 200, "body": {}}

            def update_layout_via_api(self, payload):
                self.calls.append(("update_layout", payload))
                return {"status": 200, "body": {}}

        fake = FakeClient()
        registry = ao.OperatorRegistry(client_factory=lambda: fake, host="hosts/Server", enabled=True)
        markers = registry.plan("update_markers", {"map_id": "m-1", "markers": [{"id": "mk"}]})
        markers_applied = registry.apply(markers["plan_id"], markers["confirmation_token"])
        self.assertEqual(markers_applied["status"], "applied")
        layout = registry.plan("update_layout", {"layout_id": "lid-1", "body": {"display_name": "Renamed"}})
        layout_applied = registry.apply(layout["plan_id"], layout["confirmation_token"])
        self.assertEqual(layout_applied["status"], "applied")
        self.assertEqual(fake.calls[0][0], "update_markers")
        self.assertEqual(fake.calls[1][0], "update_layout")


if __name__ == "__main__":
    unittest.main()
