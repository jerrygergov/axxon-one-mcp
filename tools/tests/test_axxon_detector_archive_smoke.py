from __future__ import annotations

from contextlib import redirect_stderr
import importlib
import io
from pathlib import Path
import sys
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
