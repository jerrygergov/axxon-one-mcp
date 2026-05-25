from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import datetime as dt
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class AxxonDetectorArchiveSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_detector_archive_smoke")

    def test_mutation_requires_operator_env_approval(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.module.parse_args(["--mutation"])

    def test_mutation_requires_archive_maintenance_env_approval(self) -> None:
        with mock.patch.dict("os.environ", {"AXXON_OPERATOR_APPROVE": "1"}, clear=True):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.module.parse_args(["--mutation"])

        with mock.patch.dict(
            "os.environ",
            {"AXXON_OPERATOR_APPROVE": "1", "AXXON_ARCHIVE_MAINTENANCE_APPROVE": "1"},
            clear=True,
        ):
            args = self.module.parse_args(["--mutation"])

        self.assertTrue(args.mutation)

    def test_archive_maintenance_noop_requires_both_env_approvals(self) -> None:
        with mock.patch.dict("os.environ", {"AXXON_OPERATOR_APPROVE": "1"}, clear=True):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.module.parse_args(["--archive-maintenance-noop"])

        with mock.patch.dict(
            "os.environ",
            {"AXXON_OPERATOR_APPROVE": "1", "AXXON_ARCHIVE_MAINTENANCE_APPROVE": "1"},
            clear=True,
        ):
            args = self.module.parse_args(["--archive-maintenance-noop"])

        self.assertTrue(args.archive_maintenance_noop)

    def test_rejects_cli_connection_and_credential_flags(self) -> None:
        for argv in (["--password", "root"], ["--host", "demo.internal"], ["--tls-cn", "Server"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        self.module.parse_args(argv)

    def test_rejects_abbreviated_cli_connection_and_credential_flags(self) -> None:
        for argv in (["--pass", "root"], ["--user", "root"], ["--tls", "Server"], ["--hos", "demo.internal"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        self.module.parse_args(argv)

    def test_cap_defaults_are_bounded_and_use_nonexistent_volume_prefix(self) -> None:
        args = self.module.parse_args([])

        self.assertEqual(args.metadata_sample_limit, 20)
        self.assertEqual(args.metadata_sample_timeout, 5.0)
        self.assertEqual(args.noop_volume_prefix, "codex-nonexistent-")

    def test_sanitize_evidence_recursively_redacts_host_and_secrets(self) -> None:
        raw = {
            "url": "http://demo.internal/api",
            "auth": "Bearer live-token",
            "username": "root",
            "user": "root",
            "login": "root",
            "tls_cn": "Server",
            "tls-cn": "Server",
            "tls_common_name": "Server",
            "password": "root",
            "root_password": "secret",
            "nested": [
                "demo.internal",
                {"token": "abc", "uid": "hosts/Server/AVDetector.1"},
                "Authorization: Bearer nested-token; password=plain",
            ],
        }

        sanitized = self.module.sanitize_evidence(raw, host="demo.internal")

        self.assertEqual(sanitized["url"], "http://<demo-host>/api")
        self.assertEqual(sanitized["auth"], "Bearer <redacted>")
        self.assertEqual(sanitized["username"], "<demo-user>")
        self.assertEqual(sanitized["user"], "<demo-user>")
        self.assertEqual(sanitized["login"], "<demo-user>")
        self.assertEqual(sanitized["tls_cn"], "<demo-tls-cn>")
        self.assertEqual(sanitized["tls-cn"], "<demo-tls-cn>")
        self.assertEqual(sanitized["tls_common_name"], "<demo-tls-cn>")
        self.assertEqual(sanitized["password"], "<redacted>")
        self.assertEqual(sanitized["root_password"], "<redacted>")
        self.assertEqual(sanitized["nested"][0], "<demo-host>")
        self.assertEqual(sanitized["nested"][1]["token"], "<redacted>")
        self.assertEqual(sanitized["nested"][1]["uid"], "hosts/Server/AVDetector.1")
        self.assertIn("Bearer <redacted>", sanitized["nested"][2])
        self.assertIn("password=<redacted>", sanitized["nested"][2])

    def test_sanitize_text_redacts_identity_values_but_preserves_intrinsic_uids(self) -> None:
        raw = "target root tls Server uid hosts/Server/AVDetector.1 authorization Bearer abc"

        sanitized = self.module.sanitize_evidence(raw, host="demo.internal", username="root", tls_cn="Server")

        self.assertEqual(
            sanitized,
            "target <demo-user> tls <demo-tls-cn> uid hosts/Server/AVDetector.1 authorization Bearer <redacted>",
        )

    def test_mutation_run_also_dispatches_archive_maintenance_noop(self) -> None:
        smoke = object.__new__(self.module.DetectorArchiveSmoke)
        smoke.args = SimpleNamespace(mutation=True, archive_maintenance_noop=False)
        smoke.context = {}
        smoke.tool = mock.Mock()
        smoke.record = mock.Mock(return_value={})
        smoke.detector_uid = mock.Mock(return_value="")
        smoke.vmda_source_ap = mock.Mock(return_value="")
        smoke.archive_policy_target = mock.Mock(return_value="")
        smoke.run_mutation = mock.Mock()
        smoke.run_archive_maintenance_noop = mock.Mock()
        smoke.report = mock.Mock(return_value={"summary": {}})
        smoke.write_report = mock.Mock()

        smoke.run()

        smoke.run_mutation.assert_called_once_with()
        smoke.run_archive_maintenance_noop.assert_called_once_with()

    def test_operator_audit_log_entries_are_appended_across_workflows(self) -> None:
        smoke = object.__new__(self.module.DetectorArchiveSmoke)
        smoke.context = {"operator_audit_log": [{"action": "mutation"}]}
        mutation_registry = mock.Mock()
        mutation_registry.audit_log.return_value = [{"action": "mutation"}, {"action": "rollback"}]
        maintenance_registry = mock.Mock()
        maintenance_registry.audit_log.return_value = [{"action": "archive_format_volume"}]

        smoke.append_operator_audit_log(mutation_registry)
        smoke.append_operator_audit_log(maintenance_registry)

        self.assertEqual(
            smoke.context["operator_audit_log"],
            [{"action": "mutation"}, {"action": "rollback"}, {"action": "archive_format_volume"}],
        )

    def test_write_report_sanitizes_distinct_http_url_host_and_userinfo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            smoke = object.__new__(self.module.DetectorArchiveSmoke)
            smoke.started_at = dt.datetime(2026, 5, 25, tzinfo=dt.UTC)
            smoke.args = SimpleNamespace(
                host="grpc.internal",
                grpc_port=20109,
                http_url="https://root:secret@api.internal:8443/path",
                username="root",
                password="pw",
                tls_cn="Server",
                mutation=False,
                archive_maintenance_noop=False,
                metadata_sample_limit=20,
                metadata_sample_timeout=5.0,
                noop_volume_prefix="codex-nonexistent-",
                report_dir=Path(tmp),
            )
            smoke.context = {}
            smoke.results = []

            with redirect_stdout(io.StringIO()):
                smoke.write_report(smoke.report())

            json_text = (Path(tmp) / "phase-5e-detector-archive-smoke-latest.json").read_text(encoding="utf-8")
            md_text = (Path(tmp) / "phase-5e-detector-archive-smoke-latest.md").read_text(encoding="utf-8")
            payload = json.loads(json_text)

            self.assertNotIn("api.internal", json_text)
            self.assertNotIn("secret", json_text)
            self.assertNotIn("root", json_text)
            self.assertIn("<demo-host>", payload["target"]["http_url"])
            self.assertIn("<redacted-userinfo>", payload["target"]["http_url"])
            self.assertNotIn("api.internal", md_text)
            self.assertNotIn("secret", md_text)
            self.assertNotIn("root", md_text)

    def test_result_status_classifies_warnings_and_unknown_status_as_warn(self) -> None:
        self.assertEqual(self.module.result_status({"status": "warn"}), "WARN")
        self.assertEqual(self.module.result_status({"status": "warning"}), "WARN")
        self.assertEqual(self.module.result_status({"status": "partial"}), "WARN")

    def test_apply_verify_rollback_fails_when_verify_errors(self) -> None:
        smoke = object.__new__(self.module.DetectorArchiveSmoke)
        registry = mock.Mock()
        registry.plan.return_value = {
            "status": "planned",
            "plan_id": "plan-1",
            "confirmation_token": "CONFIRM",
            "rollback_confirmation_token": "ROLLBACK",
        }
        registry.apply.return_value = {"status": "applied"}
        registry.verify.side_effect = [{"status": "error"}, {"status": "verified"}]
        registry.rollback.return_value = {"status": "rolled_back"}

        result = smoke.apply_verify_rollback(registry, "update_detector_parameters", {"uid": "detector"})

        self.assertEqual(result["status"], "error")

    def test_mutate_av_detector_fails_when_attempted_nested_update_errors(self) -> None:
        smoke = object.__new__(self.module.DetectorArchiveSmoke)
        smoke.fixture_needed = self.module.DetectorArchiveSmoke.fixture_needed.__get__(smoke)
        smoke.apply_verify_rollback = mock.Mock(return_value={"status": "error"})

        registry = mock.Mock()
        registry.plan.return_value = {
            "status": "planned",
            "plan_id": "plan-create",
            "confirmation_token": "CONFIRM",
            "rollback_confirmation_token": "ROLLBACK",
        }
        registry.apply.return_value = {"status": "applied", "created_uids": ["hosts/Server/AVDetector.1"]}
        registry.verify.side_effect = [{"status": "verified"}, {"status": "verified"}]
        registry.rollback.return_value = {"status": "rolled_back"}
        registry.ensure_client.return_value.read_unit.return_value = {
            "units": [{"uid": "hosts/Server/AVDetector.1", "properties": [{"id": "enabled", "value_bool": True}]}]
        }

        result = smoke.mutate_av_detector(registry, "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")

        self.assertEqual(result["status"], "error")

    def test_mutate_av_detector_allows_fixture_needed_nested_updates(self) -> None:
        smoke = object.__new__(self.module.DetectorArchiveSmoke)
        smoke.fixture_needed = self.module.DetectorArchiveSmoke.fixture_needed.__get__(smoke)

        registry = mock.Mock()
        registry.plan.return_value = {
            "status": "planned",
            "plan_id": "plan-create",
            "confirmation_token": "CONFIRM",
            "rollback_confirmation_token": "ROLLBACK",
        }
        registry.apply.return_value = {"status": "applied", "created_uids": ["hosts/Server/AVDetector.1"]}
        registry.verify.side_effect = [{"status": "verified"}, {"status": "verified"}]
        registry.rollback.return_value = {"status": "rolled_back"}
        registry.ensure_client.return_value.read_unit.return_value = {
            "units": [{"uid": "hosts/Server/AVDetector.1", "properties": []}]
        }

        result = smoke.mutate_av_detector(registry, "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["scalar_update"]["status"], "fixture-needed")

    def test_archive_maintenance_noop_fails_when_verify_or_rollback_errors(self) -> None:
        for verify_statuses, rollback_status in (
            ([{"status": "error"}, {"status": "verified"}, {"status": "verified"}], {"status": "rolled_back"}),
            ([{"status": "verified"}, {"status": "verified"}, {"status": "verified"}], {"status": "error"}),
        ):
            with self.subTest(verify_statuses=verify_statuses, rollback_status=rollback_status):
                smoke = object.__new__(self.module.DetectorArchiveSmoke)
                smoke.args = SimpleNamespace(archive_access_point="hosts/Server/MultimediaStorage.AliceBlue", noop_volume_prefix="codex-nonexistent-")
                smoke.context = {}
                smoke.fixture_needed = self.module.DetectorArchiveSmoke.fixture_needed.__get__(smoke)
                registry = mock.Mock()
                registry.plan.side_effect = [
                    {"status": "planned", "plan_id": "format", "confirmation_token": "CONFIRM-format"},
                    {"status": "planned", "plan_id": "reindex", "confirmation_token": "CONFIRM-reindex", "rollback_confirmation_token": "ROLLBACK-reindex"},
                    {"status": "planned", "plan_id": "cancel", "confirmation_token": "CONFIRM-cancel"},
                ]
                registry.apply.return_value = {"status": "applied"}
                registry.verify.side_effect = verify_statuses
                registry.rollback.return_value = rollback_status

                result = smoke.archive_maintenance_noop(registry)

                self.assertEqual(result["status"], "error")

    def test_report_paths_use_phase_latest_names(self) -> None:
        paths = self.module.report_paths(Path("/tmp/reports"), stamp="20260525T120000Z")

        self.assertEqual(
            paths["latest_json"],
            Path("/tmp/reports/phase-5e-detector-archive-smoke-latest.json"),
        )
        self.assertEqual(
            paths["latest_md"],
            Path("/tmp/reports/phase-5e-detector-archive-smoke-latest.md"),
        )
        self.assertEqual(
            paths["json"],
            Path("/tmp/reports/phase-5e-detector-archive-smoke-20260525T120000Z.json"),
        )
        self.assertEqual(
            paths["md"],
            Path("/tmp/reports/phase-5e-detector-archive-smoke-20260525T120000Z.md"),
        )


if __name__ == "__main__":
    unittest.main()
