from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeCatalog:
    def __init__(self, devices: list[dict] | None = None) -> None:
        self.devices = devices if devices is not None else [{"vendor": "Axis", "model": "P1375"}]
        self.calls = 0

    def list_devices(self) -> dict:
        self.calls += 1
        return {"status": "ok", "devices": list(self.devices)}


class FakeDiscovery:
    def __init__(self, devices: list[dict] | None = None, unavailable: bool = False) -> None:
        self.devices = devices or []
        self.unavailable = unavailable
        self.calls = 0

    def discover_devices(self, max_devices: int = 200, max_seconds: float = 20.0) -> dict:
        self.calls += 1
        if self.unavailable:
            return {"status": "gap", "message": "discovery unavailable"}
        return {"status": "ok", "devices": list(self.devices)}


class FakeSiteGraph:
    def __init__(
        self,
        *,
        cameras: list[dict] | None = None,
        archives: list[dict] | None = None,
        templates: list[dict] | None = None,
    ) -> None:
        self.cameras = cameras or []
        self.archives = archives or [{"uid": "archive-1", "access_point": "archive-ap"}]
        self.templates = templates or [{"id": "tpl-1", "name": "Outdoor"}]
        self.calls = 0

    def build_site_graph(self, **_kwargs: object) -> dict:
        self.calls += 1
        return {
            "status": "ok",
            "cameras": list(self.cameras),
            "archives": list(self.archives),
            "templates": list(self.templates),
        }


class FakeMutationClient:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[dict] = []
        self.units: dict[str, dict] = {}
        self._next_uid = 0

    def _alloc_uid(self, unit_type: str) -> str:
        self._next_uid += 1
        return f"hosts/Server/{unit_type}.{self._next_uid}"

    def change_config(self, payload: dict) -> dict:
        self.calls.append(payload)
        if self.fail_on_call == len(self.calls):
            return {
                "added": [],
                "failed": [{"uid": "pending", "reason": "simulated failure"}],
                "failed_reason": ["simulated failure"],
            }
        added: list[str] = []
        for parent in payload.get("added", []):
            for unit in parent.get("units", []):
                uid = unit.get("uid") or self._alloc_uid(unit.get("type", "Unit"))
                self.units[uid] = {**unit, "uid": uid, "parent_uid": parent.get("uid")}
                added.append(uid)
        for unit in payload.get("removed", []):
            self.units.pop(unit["uid"], None)
        return {"added": added, "failed": [], "failed_reason": []}

    def read_unit(self, uid: str) -> dict:
        unit = self.units.get(uid)
        return {"units": [unit]} if unit else {"units": []}


def make_registry(
    *,
    catalog: FakeCatalog | None = None,
    discovery: FakeDiscovery | None = None,
    site_graph: FakeSiteGraph | None = None,
    mutation_client: FakeMutationClient | None = None,
    env: dict[str, str] | None = None,
):
    module = importlib.import_module("axxon_mcp_bulk_onboarding")
    deps = module.BulkOnboardingDependencies(
        catalog_provider=catalog or FakeCatalog(),
        discovery_provider=discovery or FakeDiscovery(
            [{"ip_address": "192.0.2.10", "mac_address": "aa:bb:cc:dd:ee:ff", "vendor": "Axis", "model": "P1375"}]
        ),
        site_graph_provider=site_graph or FakeSiteGraph(),
        mutation_client_factory=lambda: mutation_client or FakeMutationClient(),
    )
    return module.AxxonMcpBulkOnboarding(dependencies=deps, environ=env if env is not None else {})


VALID_ROW = {
    "display_name": "Front Door",
    "display_id": "CAM-001",
    "vendor": "Axis",
    "model": "P1375",
    "ip": "192.0.2.10",
    "mac": "aa:bb:cc:dd:ee:ff",
    "login": "installer",
    "password": "secret-password",
    "archive_uid": "archive-1",
    "template_id": "tpl-1",
}


def assert_no_secret(test: unittest.TestCase, payload: object) -> None:
    encoded = json.dumps(payload, sort_keys=True)
    test.assertNotIn("secret-password", encoded)
    test.assertNotIn("Bearer abc", encoded)
    test.assertNotIn("session-secret", encoded)
    test.assertNotIn("default-pass", encoded)


class BulkOnboardingTests(unittest.TestCase):
    def test_module_imports_and_exposes_constants_without_connecting(self) -> None:
        module = importlib.import_module("axxon_mcp_bulk_onboarding")
        self.assertEqual(module.BULK_ONBOARDING_APPROVE_ENV, "AXXON_BULK_ONBOARDING_APPROVE")
        self.assertEqual(module.BULK_ONBOARDING_CONFIRMATION, "CONFIRM-bulk-onboarding")
        self.assertEqual(
            module.BULK_ONBOARDING_TOOL_NAMES,
            (
                "bulk_onboarding_connect_axxon_profile",
                "bulk_onboarding_schema",
                "bulk_onboarding_validate_manifest",
                "bulk_onboarding_plan",
                "bulk_onboarding_apply_plan",
                "bulk_onboarding_verify_plan",
                "bulk_onboarding_rollback_plan",
                "bulk_onboarding_audit_log",
            ),
        )

        def exploding_config():
            raise AssertionError("config must be lazy")

        registry = module.AxxonMcpBulkOnboarding(config_factory=exploding_config)
        schema = registry.bulk_onboarding_schema()
        self.assertEqual(schema["approval_env"], "AXXON_BULK_ONBOARDING_APPROVE")

    def test_connect_env_is_lazy_and_non_env_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_bulk_onboarding")

        class Config:
            host = "vms.example.invalid"
            port = 443
            tls_cn = "Server"
            user = "admin"
            timeout = 7

        calls: list[str] = []
        registry = module.AxxonMcpBulkOnboarding(config_factory=lambda: calls.append("config") or Config())
        gap = registry.bulk_onboarding_connect_axxon_profile("named")
        self.assertEqual(gap["status"], "gap")
        self.assertEqual(calls, [])

        connected = registry.bulk_onboarding_connect_axxon_profile("env")
        self.assertEqual(connected["connected"], True)
        self.assertEqual(connected["mode"], "bulk-onboarding")
        self.assertEqual(connected["approval_env"], "AXXON_BULK_ONBOARDING_APPROVE")
        self.assertEqual(connected["confirmation_token"], "CONFIRM-bulk-onboarding")
        self.assertEqual(calls, ["config"])
        assert_no_secret(self, connected)

    def test_schema_describes_sources_fields_profiles_and_redaction(self) -> None:
        registry = make_registry()
        schema = registry.bulk_onboarding_schema()
        self.assertEqual(schema["status"], "ok")
        self.assertEqual(schema["input_sources"], ["rows", "csv_text", "json_text"])
        self.assertIn("display_name", schema["required_fields"])
        self.assertIn("archive_uid", schema["optional_fields"])
        self.assertIn("av_motion", schema["supported_detector_profiles"])
        self.assertIn("redact", " ".join(schema["redaction_policy"]).lower())

    def test_csv_json_rows_parse_with_exclusive_sources_and_row_numbers(self) -> None:
        registry = make_registry()
        csv_result = registry.bulk_onboarding_validate_manifest(
            csv_text=(
                "display_name,vendor,model,ip,mac\n"
                "Front Door,Axis,P1375,192.0.2.10,aa:bb:cc:dd:ee:ff\n"
            )
        )
        self.assertEqual(csv_result["summary"]["total_rows"], 1)
        self.assertEqual(csv_result["rows"][0]["row_number"], 1)
        self.assertEqual(csv_result["rows"][0]["display_name"], "Front Door")

        json_result = registry.bulk_onboarding_validate_manifest(json_text=json.dumps({"rows": [VALID_ROW]}))
        self.assertEqual(json_result["rows"][0]["row_number"], 1)

        array_result = registry.bulk_onboarding_validate_manifest(json_text=json.dumps([VALID_ROW]))
        self.assertEqual(array_result["summary"]["valid_rows"], 1)

        explicit_rows = registry.bulk_onboarding_validate_manifest(rows=[VALID_ROW])
        self.assertEqual(explicit_rows["rows"][0]["row_number"], 1)

        no_source = registry.bulk_onboarding_validate_manifest()
        self.assertEqual(no_source["status"], "error")
        self.assertIn("exactly one", no_source["errors"][0]["message"])

        two_sources = registry.bulk_onboarding_validate_manifest(rows=[VALID_ROW], json_text=json.dumps([VALID_ROW]))
        self.assertEqual(two_sources["status"], "error")
        self.assertIn("exactly one", two_sources["errors"][0]["message"])

    def test_rejects_path_like_import_options_and_non_object_rows(self) -> None:
        registry = make_registry()
        rejected = registry.bulk_onboarding_validate_manifest(path="/tmp/cameras.csv")
        self.assertEqual(rejected["status"], "error")
        self.assertIn("file", rejected["errors"][0]["message"].lower())

        non_object = registry.bulk_onboarding_validate_manifest(json_text=json.dumps(["bad"]))
        self.assertEqual(non_object["status"], "error")
        self.assertEqual(non_object["row_errors"][0]["row_number"], 1)

    def test_validation_reports_required_duplicates_catalog_discovery_site_conflicts(self) -> None:
        site_graph = FakeSiteGraph(
            cameras=[
                {
                    "uid": "hosts/Server/DeviceIpint.9",
                    "display_name": "Existing",
                    "display_id": "CAM-099",
                    "ip": "192.0.2.99",
                    "mac": "aa:bb:cc:dd:ee:99",
                }
            ]
        )
        discovery = FakeDiscovery(
            [
                {"ip_address": "192.0.2.20", "mac_address": "aa:bb:cc:dd:ee:20", "vendor": "Axis", "model": "Wrong"},
            ]
        )
        rows = [
            {"display_name": "", "vendor": "Axis", "model": "P1375", "ip": "not-an-ip"},
            {"display_name": "Unsupported", "vendor": "Nope", "model": "Nope", "ip": "192.0.2.21"},
            {"display_name": "Conflict", "display_id": "CAM-099", "vendor": "Axis", "model": "P1375", "ip": "192.0.2.99"},
            {"display_name": "Discovery Mismatch", "vendor": "Axis", "model": "P1375", "ip": "192.0.2.20"},
            {**VALID_ROW, "display_name": "Dup A", "display_id": "DUP", "ip": "192.0.2.30"},
            {**VALID_ROW, "display_name": "Dup B", "display_id": "DUP", "ip": "192.0.2.31"},
        ]
        result = make_registry(site_graph=site_graph, discovery=discovery).bulk_onboarding_validate_manifest(rows=rows)
        self.assertEqual(result["status"], "error")
        errors = json.dumps(result["row_errors"], sort_keys=True)
        self.assertIn("display_name", errors)
        self.assertIn("ip", errors)
        self.assertIn("unsupported", errors.lower())
        self.assertIn("existing_camera", errors)
        self.assertIn("discovery_mismatch", errors)
        self.assertIn("duplicate", errors)
        self.assertEqual(result["dependencies"]["catalog"]["status"], "ok")
        self.assertEqual(result["dependencies"]["discovery"]["status"], "ok")
        self.assertEqual(result["dependencies"]["site_graph"]["status"], "ok")

    def test_discovery_unavailable_warns_unless_required(self) -> None:
        registry = make_registry(discovery=FakeDiscovery(unavailable=True))
        warn = registry.bulk_onboarding_validate_manifest(rows=[VALID_ROW])
        self.assertEqual(warn["status"], "warn")
        self.assertEqual(warn["dependencies"]["discovery"]["status"], "warn")

        required = registry.bulk_onboarding_validate_manifest(rows=[VALID_ROW], options={"require_discovery": True})
        self.assertEqual(required["status"], "error")
        self.assertIn("discovery", json.dumps(required["row_errors"]).lower())

    def test_archive_template_and_detector_validation(self) -> None:
        registry = make_registry(site_graph=FakeSiteGraph(archives=[], templates=[]))
        result = registry.bulk_onboarding_validate_manifest(
            rows=[{**VALID_ROW, "detector_profile": "unsupported", "archive_uid": "missing", "template_id": "missing"}]
        )
        self.assertEqual(result["status"], "error")
        encoded = json.dumps(result["row_errors"], sort_keys=True).lower()
        self.assertIn("archive", encoded)
        self.assertIn("template", encoded)
        self.assertIn("detector", encoded)

    def test_validation_and_errors_redact_nested_secrets(self) -> None:
        row = {
            **VALID_ROW,
            "credentials": {"password": "secret-password"},
            "authorization": "Bearer abc",
            "session_id": "session-secret",
            "default_credentials": {"password": "default-pass"},
        }
        result = make_registry(catalog=FakeCatalog([])).bulk_onboarding_validate_manifest(rows=[row])
        assert_no_secret(self, result)
        self.assertIn("<redacted>", json.dumps(result))

    def test_plan_emits_deterministic_per_camera_metadata_without_detector_by_default(self) -> None:
        registry = make_registry()
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["batch_plan_id"], registry.bulk_onboarding_plan(rows=[VALID_ROW])["batch_plan_id"])
        self.assertEqual(plan["confirmation_token"], "CONFIRM-bulk-onboarding")
        self.assertEqual(plan["rollback_confirmation_token"], "CONFIRM-bulk-onboarding-rollback")
        camera_plan = plan["camera_plans"][0]
        self.assertTrue(camera_plan["apply_ready"])
        self.assertEqual(camera_plan["row_number"], 1)
        self.assertEqual(camera_plan["display_name"], "Front Door")
        self.assertEqual(camera_plan["host_uid"], "hosts/Server")
        self.assertEqual(camera_plan["vendor"], "Axis")
        self.assertEqual(camera_plan["model"], "P1375")
        self.assertEqual(camera_plan["risk"], "mutation")
        self.assertIn("DeviceIpint", json.dumps(camera_plan["steps"]))
        self.assertNotIn("Detector", json.dumps(camera_plan["steps"]))
        self.assertEqual(plan["batch_rollback_order"], [camera_plan["row_id"]])
        assert_no_secret(self, plan)

    def test_plan_handles_templates_archives_and_opt_in_detectors(self) -> None:
        registry = make_registry()
        plan = registry.bulk_onboarding_plan(
            rows=[{**VALID_ROW, "detector_profile": "av_motion", "detector_sensitivity": "0.7"}],
            options={"detector_overrides": {"min_object_size": 8}},
        )
        steps = plan["camera_plans"][0]["steps"]
        encoded = json.dumps(steps, sort_keys=True)
        self.assertIn("ConfigurationService.ChangeTemplates", encoded)
        self.assertIn("archive_assign", encoded)
        self.assertIn("create_av_detector_full", encoded)
        self.assertIn("detector_overrides", encoded)
        self.assertIn("archive_create", encoded)
        self.assertNotIn("archive_create", [step.get("operation") for step in steps])
        self.assertNotIn("archive_format", [step.get("operation") for step in steps])
        self.assertEqual(plan["camera_plans"][0]["rollback"]["strategy"], "reverse_recorded_steps")

    def test_plan_refuses_apply_ready_entries_for_error_rows(self) -> None:
        registry = make_registry(catalog=FakeCatalog([]))
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])
        self.assertEqual(plan["status"], "error")
        self.assertFalse(plan["camera_plans"][0]["apply_ready"])
        self.assertEqual(plan["batch_rollback_order"], [])

    def test_apply_requires_known_planned_confirmation_and_env_gate(self) -> None:
        env: dict[str, str] = {}
        registry = make_registry(env=env)
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])

        unknown = registry.bulk_onboarding_apply_plan("missing", "CONFIRM-bulk-onboarding")
        self.assertEqual(unknown["status"], "rejected")

        wrong = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "WRONG")
        self.assertEqual(wrong["status"], "rejected")
        self.assertIn("confirmation", wrong["message"].lower())

        missing_env = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        self.assertEqual(missing_env["status"], "rejected")
        self.assertIn("AXXON_BULK_ONBOARDING_APPROVE", missing_env["message"])

        env["AXXON_BULK_ONBOARDING_APPROVE"] = "1"
        applied = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        self.assertEqual(applied["status"], "applied")

        stale = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        self.assertEqual(stale["status"], "rejected")
        self.assertIn("planned", stale["message"].lower())

    def test_apply_records_partial_failure_and_rollback_reverses_only_applied_steps(self) -> None:
        env = {"AXXON_BULK_ONBOARDING_APPROVE": "1"}
        client = FakeMutationClient(fail_on_call=2)
        rows = [
            {**VALID_ROW, "display_name": "First", "display_id": "CAM-1", "ip": "192.0.2.10"},
            {**VALID_ROW, "display_name": "Second", "display_id": "CAM-2", "ip": "192.0.2.11", "mac": "aa:bb:cc:dd:ee:11"},
        ]
        registry = make_registry(mutation_client=client, env=env)
        plan = registry.bulk_onboarding_plan(rows=rows)
        applied = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        self.assertEqual(applied["status"], "partial")
        self.assertEqual(applied["row_results"][0]["status"], "applied")
        self.assertEqual(applied["row_results"][1]["status"], "error")
        self.assertEqual(len(applied["applied_rows"]), 1)

        rolled = registry.bulk_onboarding_rollback_plan(
            plan["batch_plan_id"],
            "CONFIRM-bulk-onboarding-rollback",
        )
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual([row["row_id"] for row in rolled["row_results"]], [applied["applied_rows"][0]["row_id"]])
        self.assertEqual(client.units, {})

    def test_rollback_requires_approval_and_confirmation(self) -> None:
        env = {"AXXON_BULK_ONBOARDING_APPROVE": "1"}
        registry = make_registry(env=env)
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])
        registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")

        env.pop("AXXON_BULK_ONBOARDING_APPROVE")
        missing_env = registry.bulk_onboarding_rollback_plan(
            plan["batch_plan_id"],
            "CONFIRM-bulk-onboarding-rollback",
        )
        self.assertEqual(missing_env["status"], "rejected")

        env["AXXON_BULK_ONBOARDING_APPROVE"] = "1"
        wrong = registry.bulk_onboarding_rollback_plan(plan["batch_plan_id"], "WRONG")
        self.assertEqual(wrong["status"], "rejected")

    def test_verify_reports_created_missing_and_rolled_back_state(self) -> None:
        env = {"AXXON_BULK_ONBOARDING_APPROVE": "1"}
        client = FakeMutationClient()
        registry = make_registry(mutation_client=client, env=env)
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])
        applied = registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        verify = registry.bulk_onboarding_verify_plan(plan["batch_plan_id"])
        self.assertEqual(verify["status"], "verified")
        self.assertEqual(verify["rows"][0]["camera"]["created_uid"], applied["applied_rows"][0]["created_uids"][0])
        self.assertEqual(verify["rows"][0]["camera"]["still_present"], True)
        self.assertIn("archive", verify["rows"][0])
        self.assertIn("template", verify["rows"][0])

        client.units.clear()
        missing = registry.bulk_onboarding_verify_plan(plan["batch_plan_id"])
        self.assertEqual(missing["rows"][0]["camera"]["still_present"], False)

        registry.bulk_onboarding_rollback_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding-rollback")
        rolled = registry.bulk_onboarding_verify_plan(plan["batch_plan_id"])
        self.assertEqual(rolled["snapshot_status"], "rolled_back")

    def test_audit_log_covers_actions_and_redacts_manifest_secrets(self) -> None:
        env = {"AXXON_BULK_ONBOARDING_APPROVE": "1"}
        registry = make_registry(env=env)
        registry.bulk_onboarding_connect_axxon_profile("named")
        registry.bulk_onboarding_schema()
        registry.bulk_onboarding_validate_manifest(rows=[VALID_ROW])
        plan = registry.bulk_onboarding_plan(rows=[VALID_ROW])
        registry.bulk_onboarding_apply_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding")
        registry.bulk_onboarding_verify_plan(plan["batch_plan_id"])
        registry.bulk_onboarding_rollback_plan(plan["batch_plan_id"], "CONFIRM-bulk-onboarding-rollback")
        audit = registry.bulk_onboarding_audit_log()
        actions = [entry["action"] for entry in audit["entries"]]
        for action in ("connect", "schema", "validate", "plan", "apply", "verify", "rollback"):
            self.assertIn(action, actions)
        self.assertTrue(all("sequence" in entry for entry in audit["entries"]))
        assert_no_secret(self, audit)


if __name__ == "__main__":
    unittest.main()
