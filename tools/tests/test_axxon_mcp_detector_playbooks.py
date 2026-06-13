from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


SECRET_MARKERS = (
    "CONFIG_SECRET_SHOULD_NOT_LEAK",
    "SCHEMA_SECRET_SHOULD_NOT_LEAK",
    "OPERATOR_SECRET_SHOULD_NOT_LEAK",
    "EVENT_TOKEN_SHOULD_NOT_LEAK",
    "RAW_METADATA_SHOULD_NOT_LEAK",
    "RAW_MEDIA_SHOULD_NOT_LEAK",
    "BIOMETRIC_VECTOR_SHOULD_NOT_LEAK",
    "CONFIRM-create_av_detector_full",
    "CONFIRM-update_detector_visual_element",
    "operator-plan-",
)


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_SECRET_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/root-ca.crt")
    timeout = 7.0


class FakeArchive:
    def __init__(self) -> None:
        self.connect_calls: list[str] = []
        self.catalog_calls: list[bool] = []
        self.schema_calls: list[tuple[str, str]] = []
        self.visual_calls: list[str] = []
        self.client_built = False

    def detector_archive_connect_axxon_profile(self, profile: str = "env") -> dict:
        self.connect_calls.append(profile)
        if profile != "env":
            return {"connected": False, "status": "gap", "profile_name": profile}
        self.client_built = True
        return {
            "connected": True,
            "profile_name": profile,
            "profile": {
                "host": "example.local",
                "username": "root",
                "password": "CONFIG_SECRET_SHOULD_NOT_LEAK",
                "password_present": True,
                "ca": "/tmp/root-ca.crt",
            },
            "mode": "read-only",
        }

    def detector_kind_catalog(self, include_live: bool = True) -> dict:
        self.catalog_calls.append(include_live)
        return {
            "status": "ok",
            "tool": "detector_kind_catalog",
            "include_live": include_live,
            "by_unit_type": {
                "AVDetector": [
                    {
                        "unit_type": "AVDetector",
                        "detector_kind": "MotionDetection",
                        "source_type": "Video",
                        "provenance": ["known-catalog"],
                    },
                    {
                        "unit_type": "AVDetector",
                        "detector_kind": "CrowdDensity",
                        "source_type": "Video",
                        "provenance": ["live-unit", "template"],
                    },
                ],
                "AppDataDetector": [
                    {
                        "unit_type": "AppDataDetector",
                        "detector_kind": "MoveInZone",
                        "source_type": "TargetList",
                        "provenance": ["known-catalog"],
                    },
                    {
                        "unit_type": "AppDataDetector",
                        "detector_kind": "QueueLength",
                        "source_type": "TargetList",
                        "provenance": ["factory"],
                    },
                ],
            },
        }

    def detector_parameter_schema(self, unit_type: str, detector_kind: str) -> dict:
        self.schema_calls.append((unit_type, detector_kind))
        return {
            "status": "ok",
            "tool": "detector_parameter_schema",
            "unit_type": unit_type,
            "detector_kind": detector_kind,
            "source_type": "TargetList" if unit_type == "AppDataDetector" else "Video",
            "schema": {
                "type": "object",
                "properties": {
                    "input.detector": {
                        "id": "detector",
                        "path": "input.detector",
                        "value_kind": "value_string",
                        "enum": [detector_kind],
                    },
                    "advanced.sensitivity": {
                        "id": "sensitivity",
                        "path": "advanced.sensitivity",
                        "value_kind": "value_int32",
                        "range": {"min_int": 0, "max_int": 100},
                    },
                    "advanced.apiToken": {
                        "id": "apiToken",
                        "path": "advanced.apiToken",
                        "value_kind": "value_string",
                        "value": "SCHEMA_SECRET_SHOULD_NOT_LEAK",
                    },
                },
            },
            "visual_elements": self._visual_elements(),
            "provenance": ["live-unit"],
        }

    def detector_visual_elements(self, detector_uid: str) -> dict:
        self.visual_calls.append(detector_uid)
        return {
            "status": "ok",
            "tool": "detector_visual_elements",
            "detector_uid": detector_uid,
            "visual_elements": self._visual_elements(),
        }

    def metadata_schema_catalog(self) -> dict:
        return {"status": "ok", "schemas": {"MetadataSample": {"fields": []}}}

    def metadata_sample_bounded(self, *_args, **_kwargs) -> dict:
        raise AssertionError("metadata samples must not be pulled by guidance")

    def _visual_elements(self) -> list[dict]:
        return [
            {
                "uid": "hosts/Server/AppDataDetector.1/VisualElement.zone",
                "path": "zone",
                "type": "VisualElement",
                "shape_fields": [
                    "value_rectangle",
                    "value_polyline",
                    "value_mask",
                    "value_simple_polygon",
                ],
                "properties": [
                    {"id": "rect", "path": "rect", "value_kind": "value_rectangle"},
                    {"id": "line", "path": "line", "value_kind": "value_polyline"},
                    {"id": "mask", "path": "mask", "value_kind": "value_mask"},
                    {"id": "area", "path": "area", "value_kind": "value_simple_polygon"},
                    {
                        "id": "overlayToken",
                        "path": "overlayToken",
                        "value_kind": "value_string",
                        "value": "SCHEMA_SECRET_SHOULD_NOT_LEAK",
                    },
                ],
            }
        ]


class FakeOperator:
    def __init__(self) -> None:
        self.plan_calls: list[tuple[str, dict]] = []
        self.apply_calls: list[tuple[str, str]] = []
        self.verify_calls: list[str] = []
        self.rollback_calls: list[tuple[str, str]] = []
        self.next_plan_index = 0

    def known_workflows(self) -> list[str]:
        return [
            "create_av_detector_full",
            "create_appdata_detector_full",
            "update_detector_parameters",
            "update_detector_visual_element",
            "delete_detector",
            "external_event_inject",
            "raise_periodical_event",
        ]

    def plan(self, workflow: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.plan_calls.append((workflow, params))
        self.next_plan_index += 1
        plan_id = f"operator-plan-{self.next_plan_index}"
        return {
            "status": "planned",
            "plan_id": plan_id,
            "workflow": workflow,
            "risk": "mutation",
            "intent": f"operator {workflow}",
            "steps": [
                {
                    "operation": "operator_step",
                    "payload": {
                        "params": params,
                        "apiToken": "OPERATOR_SECRET_SHOULD_NOT_LEAK",
                    },
                }
            ],
            "source_bindings": {
                key: params[key]
                for key in ("video_source_ap", "vmda_source_ap", "access_point")
                if key in params
            },
            "diff": {"changed": params.get("properties", [])},
            "rollback": {
                "strategy": "noop" if workflow in {"external_event_inject", "raise_periodical_event"} else "restore",
                "description": "operator rollback",
            },
            "expected": {"workflow": workflow},
            "confirmation_token": f"CONFIRM-{workflow}",
            "rollback_confirmation_token": f"CONFIRM-{workflow}-rollback",
        }

    def apply(self, plan_id: str, confirmation: str) -> dict:
        self.apply_calls.append((plan_id, confirmation))
        return {
            "status": "applied",
            "plan_id": plan_id,
            "created_uids": ["hosts/Server/AVDetector.1"],
            "apiToken": "OPERATOR_SECRET_SHOULD_NOT_LEAK",
        }

    def verify(self, plan_id: str) -> dict:
        self.verify_calls.append(plan_id)
        return {"status": "verified", "plan_id": plan_id, "still_present": ["hosts/Server/AVDetector.1"]}

    def rollback(self, plan_id: str, confirmation: str) -> dict:
        self.rollback_calls.append((plan_id, confirmation))
        return {"status": "rolled_back", "plan_id": plan_id, "removed_uids": ["hosts/Server/AVDetector.1"]}


def _playbooks(archive: FakeArchive | None = None, operator: FakeOperator | None = None, env: dict[str, str] | None = None):
    module = importlib.import_module("axxon_mcp_detector_playbooks")
    return module.AxxonMcpDetectorPlaybooks(
        detector_archive=archive or FakeArchive(),
        operator=operator or FakeOperator(),
        environ={} if env is None else env,
    )


def _assert_no_secret_markers(testcase: unittest.TestCase, value: object) -> None:
    text = str(value)
    for marker in SECRET_MARKERS:
        testcase.assertNotIn(marker, text)


class AxxonMcpDetectorPlaybooksTests(unittest.TestCase):
    def test_connect_catalog_matrix_and_schema_are_sanitized_and_descriptor_backed(self) -> None:
        archive = FakeArchive()
        playbooks = _playbooks(archive=archive)

        connected = playbooks.detector_playbooks_connect_axxon_profile("env")

        self.assertTrue(connected["connected"])
        self.assertEqual(connected["mode"], "detector-playbooks")
        self.assertEqual(connected["approval_env"], "AXXON_DETECTOR_PLAYBOOKS_APPROVE")
        self.assertEqual(connected["confirmation_token"], "CONFIRM-detector-playbooks")
        self.assertEqual(connected["rollback_confirmation_token"], "CONFIRM-detector-playbooks-rollback")
        self.assertTrue(connected["profile"]["password_present"])
        _assert_no_secret_markers(self, connected)

        rejected = playbooks.detector_playbooks_connect_axxon_profile("named")
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(archive.connect_calls, ["env"])

        catalog = playbooks.list_detector_playbooks(include_live=True)
        self.assertEqual(catalog["status"], "ok")
        self.assertIn("create_av_detector", catalog["intents"])
        self.assertIn("update_detector_geometry", catalog["intents"])
        self.assertEqual(catalog["gate"]["approval_env"], "AXXON_DETECTOR_PLAYBOOKS_APPROVE")
        matrix = catalog["detector_family_matrix"]
        self.assertIn("MotionDetection", matrix["supported_fallback_local"]["AVDetector"])
        self.assertIn("MoveInZone", matrix["supported_fallback_local"]["AppDataDetector"])
        self.assertEqual(matrix["live_unit_discovered"]["AVDetector"][0]["detector_kind"], "CrowdDensity")
        self.assertEqual(matrix["template_discovered"]["AVDetector"][0]["detector_kind"], "CrowdDensity")
        self.assertEqual(matrix["factory_discovered"]["AppDataDetector"][0]["detector_kind"], "QueueLength")
        self.assertIn("ChangeGlobalTrackerProfiles", str(matrix["fixture_needed"]))
        self.assertIn("RealtimeRecognizerExternalService.GetData", str(matrix["fixture_needed"]))
        self.assertIn("TagAndTrackService.FollowTrack", str(matrix["fixture_needed"]))

        schema = playbooks.detector_playbook_parameter_schema("AppDataDetector", "MoveInZone", "create_appdata_detector")
        self.assertEqual(schema["status"], "ok")
        self.assertEqual(schema["base_schema"]["schema"]["properties"]["input.detector"]["value_kind"], "value_string")
        self.assertEqual(schema["playbook_required_params"], ["display_name", "video_source_ap"])
        self.assertIn("vmda_source_ap", schema["playbook_optional_params"])
        self.assertEqual(schema["visual_elements"][0]["shape_fields"], [
            "value_mask",
            "value_polyline",
            "value_rectangle",
            "value_simple_polygon",
        ])
        self.assertEqual(archive.schema_calls, [("AppDataDetector", "MoveInZone")])
        _assert_no_secret_markers(self, schema)

    def test_operator_backed_intents_plan_without_apply_and_hide_operator_internals(self) -> None:
        operator = FakeOperator()
        playbooks = _playbooks(operator=operator)
        cases = [
            ("create_av_detector", "create_av_detector_full", {"display_name": "Motion", "video_source_ap": "video", "detector_kind": "MotionDetection"}),
            ("create_appdata_detector", "create_appdata_detector_full", {"display_name": "Zone", "video_source_ap": "video", "detector_kind": "MoveInZone"}),
            ("update_detector_parameters", "update_detector_parameters", {"detector_uid": "hosts/Server/AVDetector.1", "properties": [{"id": "threshold", "value_int32": 7}]}),
            ("delete_detector", "delete_detector", {"detector_uid": "hosts/Server/AppDataDetector.1"}),
            ("raise_external_event", "external_event_inject", {"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "event", "data": {"apiToken": "EVENT_TOKEN_SHOULD_NOT_LEAK"}}),
            ("raise_periodical_external_event", "raise_periodical_event", {"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "tracklets": [{"objectId": 1, "embedding": "BIOMETRIC_VECTOR_SHOULD_NOT_LEAK"}]}),
        ]

        for intent, workflow, params in cases:
            with self.subTest(intent=intent):
                response = playbooks.plan_detector_playbook(intent, params)
                self.assertEqual(response["status"], "planned")
                self.assertTrue(response["playbook_plan_id"].startswith("detector-playbook-plan-"))
                self.assertEqual(response["intent"], intent)
                self.assertEqual(response["operator_workflow"], workflow)
                self.assertTrue(response["apply_ready"])
                self.assertEqual(response["confirmation_token"], "CONFIRM-detector-playbooks")
                self.assertEqual(response["rollback_confirmation_token"], "CONFIRM-detector-playbooks-rollback")
                _assert_no_secret_markers(self, response)

        self.assertEqual([workflow for workflow, _params in operator.plan_calls], [case[1] for case in cases])
        self.assertEqual(operator.apply_calls, [])
        self.assertEqual(operator.rollback_calls, [])
        periodical_params = operator.plan_calls[-1][1]
        self.assertNotIn("embedding", str(periodical_params))
        self.assertNotIn("BIOMETRIC_VECTOR_SHOULD_NOT_LEAK", str(periodical_params))

    def test_update_detector_geometry_uses_descriptor_value_kind_payloads(self) -> None:
        operator = FakeOperator()
        archive = FakeArchive()
        playbooks = _playbooks(archive=archive, operator=operator)
        values = {
            "value_rectangle": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
            "value_polyline": {"points": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.9}]},
            "value_mask": {"bits": "1010", "width": 2, "height": 2},
            "value_simple_polygon": {"points": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, {"x": 0.9, "y": 0.8}]},
        }
        paths = {
            "value_rectangle": "rect",
            "value_polyline": "line",
            "value_mask": "mask",
            "value_simple_polygon": "area",
        }

        for value_kind, value in values.items():
            with self.subTest(value_kind=value_kind):
                response = playbooks.plan_detector_playbook(
                    "update_detector_geometry",
                    {
                        "detector_uid": "hosts/Server/AppDataDetector.1",
                        "visual_element_uid": "hosts/Server/AppDataDetector.1/VisualElement.zone",
                        "property_path": paths[value_kind],
                        "value_kind": value_kind,
                        "value": value,
                    },
                )
                self.assertEqual(response["status"], "planned")
                self.assertEqual(response["typed_geometry"]["value_kind"], value_kind)
                workflow, operator_params = operator.plan_calls[-1]
                self.assertEqual(workflow, "update_detector_visual_element")
                self.assertEqual(operator_params["visual_element_uid"], "hosts/Server/AppDataDetector.1/VisualElement.zone")
                self.assertEqual(operator_params["properties"], [{"id": paths[value_kind], value_kind: value}])

        mismatch = playbooks.plan_detector_playbook(
            "update_detector_geometry",
            {
                "detector_uid": "hosts/Server/AppDataDetector.1",
                "visual_element_uid": "hosts/Server/AppDataDetector.1/VisualElement.zone",
                "property_path": "area",
                "value_kind": "value_polyline",
                "value": {"points": []},
            },
        )
        self.assertIn(mismatch["status"], {"error", "gap"})
        self.assertIn("value_kind", mismatch["message"])
        self.assertEqual(operator.plan_calls[-1][1]["properties"], [{"id": "area", "value_simple_polygon": values["value_simple_polygon"]}])

    def test_apply_verify_and_rollback_are_phase_gated_and_delegate_internal_tokens(self) -> None:
        env: dict[str, str] = {}
        operator = FakeOperator()
        playbooks = _playbooks(operator=operator, env=env)
        plan = playbooks.plan_detector_playbook(
            "create_av_detector",
            {"display_name": "Motion", "video_source_ap": "video", "detector_kind": "MotionDetection"},
        )
        plan_id = plan["playbook_plan_id"]

        missing_env = playbooks.apply_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks")
        self.assertEqual(missing_env["status"], "rejected")
        self.assertIn("AXXON_DETECTOR_PLAYBOOKS_APPROVE=1", missing_env["message"])
        self.assertEqual(operator.apply_calls, [])

        env["AXXON_DETECTOR_PLAYBOOKS_APPROVE"] = "1"
        wrong_confirmation = playbooks.apply_detector_playbook_plan(plan_id, "WRONG")
        self.assertEqual(wrong_confirmation["status"], "rejected")
        self.assertEqual(operator.apply_calls, [])

        applied = playbooks.apply_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(operator.apply_calls, [("operator-plan-1", "CONFIRM-create_av_detector_full")])
        _assert_no_secret_markers(self, applied)

        reapplied = playbooks.apply_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks")
        self.assertEqual(reapplied["status"], "applied")
        self.assertIn("already", reapplied["message"])
        self.assertEqual(operator.apply_calls, [("operator-plan-1", "CONFIRM-create_av_detector_full")])

        verified = playbooks.verify_detector_playbook_plan(plan_id)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(operator.verify_calls, ["operator-plan-1"])
        _assert_no_secret_markers(self, verified)

        wrong_rollback = playbooks.rollback_detector_playbook_plan(plan_id, "WRONG")
        self.assertEqual(wrong_rollback["status"], "rejected")
        self.assertEqual(operator.rollback_calls, [])

        rolled = playbooks.rollback_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks-rollback")
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(operator.rollback_calls, [("operator-plan-1", "CONFIRM-create_av_detector_full-rollback")])
        _assert_no_secret_markers(self, rolled)

        rerolled = playbooks.rollback_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks-rollback")
        self.assertEqual(rerolled["status"], "rolled_back")
        self.assertIn("already", rerolled["message"])
        self.assertEqual(operator.rollback_calls, [("operator-plan-1", "CONFIRM-create_av_detector_full-rollback")])

    def test_guidance_and_fixture_needed_intents_are_not_apply_ready(self) -> None:
        operator = FakeOperator()
        playbooks = _playbooks(operator=operator, env={"AXXON_DETECTOR_PLAYBOOKS_APPROVE": "1"})

        preflight = playbooks.plan_detector_playbook(
            "preflight_vmda_appdata",
            {"video_source_ap": "video", "detector_kind": "MoveInZone"},
        )
        self.assertEqual(preflight["status"], "guidance")
        self.assertFalse(preflight["apply_ready"])
        self.assertIn("SceneDescription", str(preflight["guidance"]))

        metadata = playbooks.plan_detector_playbook("metadata_vmda_heatmap_guidance", {"raw_metadata": "RAW_METADATA_SHOULD_NOT_LEAK"})
        self.assertEqual(metadata["status"], "guidance")
        self.assertFalse(metadata["apply_ready"])
        self.assertIn("metadata_schema_catalog", str(metadata["next_tools"]))
        self.assertIn("heatmap", str(metadata["next_tools"]).lower())
        _assert_no_secret_markers(self, metadata)

        for intent, service_name in (
            ("global_tracker_profile", "GlobalTrackerService"),
            ("realtime_recognizer_external", "RealtimeRecognizerExternalService.GetData"),
            ("tag_and_track", "TagAndTrackService"),
        ):
            with self.subTest(intent=intent):
                plan = playbooks.plan_detector_playbook(intent, {})
                self.assertEqual(plan["status"], "fixture-needed")
                self.assertFalse(plan["apply_ready"])
                self.assertIn(service_name, str(plan))
                rejected = playbooks.apply_detector_playbook_plan(plan["playbook_plan_id"], "CONFIRM-detector-playbooks")
                self.assertEqual(rejected["status"], "rejected")
                self.assertIn("not apply-ready", rejected["message"])

        self.assertEqual(operator.plan_calls, [])

    def test_audit_log_and_public_responses_are_recursively_sanitized(self) -> None:
        operator = FakeOperator()
        playbooks = _playbooks(operator=operator, env={"AXXON_DETECTOR_PLAYBOOKS_APPROVE": "1"})
        plan = playbooks.plan_detector_playbook(
            "raise_external_event",
            {
                "access_point": "hosts/Server/DetectorEx.1/EventSupplier",
                "event_type": "door",
                "password": "CONFIG_SECRET_SHOULD_NOT_LEAK",
                "data": {
                    "apiToken": "EVENT_TOKEN_SHOULD_NOT_LEAK",
                    "raw_metadata": "RAW_METADATA_SHOULD_NOT_LEAK",
                    "raw_media": "RAW_MEDIA_SHOULD_NOT_LEAK",
                },
            },
        )
        applied = playbooks.apply_detector_playbook_plan(plan["playbook_plan_id"], "CONFIRM-detector-playbooks")
        audit = playbooks.detector_playbooks_audit_log()

        self.assertEqual(audit["status"], "ok")
        self.assertGreaterEqual(len(audit["entries"]), 2)
        self.assertEqual([entry["seq"] for entry in audit["entries"]], list(range(1, len(audit["entries"]) + 1)))
        for value in (plan, applied, audit):
            _assert_no_secret_markers(self, value)
        for entry in audit["entries"]:
            self.assertIn("action", entry)
            self.assertIn("timestamp", entry)
            self.assertIn("intent", entry)
            self.assertIn("status", entry)
            self.assertNotIn("operator_plan_id", entry)


if __name__ == "__main__":
    unittest.main()
