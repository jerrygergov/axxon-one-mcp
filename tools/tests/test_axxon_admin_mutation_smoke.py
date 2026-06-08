from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import datetime as dt
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class FakeAdminMutationRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_workflows(self) -> dict:
        self.calls.append(("list_workflows", ()))
        return {
            "status": "ok",
            "workflows": [
                {"name": "security_user_role_lifecycle"},
                {"name": "security_role_permissions_update"},
                {"name": "security_policy_noop_probe"},
                {"name": "security_ldap_temp_lifecycle"},
                {"name": "security_tfa_temp_user_lifecycle"},
            ],
        }

    def plan(self, workflow: str, params: dict | None = None) -> dict:
        self.calls.append(("plan", (workflow, dict(params or {}))))
        return {
            "status": "planned",
            "plan_id": f"admin-{workflow}",
            "workflow": workflow,
            "confirmation_token": f"CONFIRM-admin-{workflow}",
            "rollback_confirmation_token": f"CONFIRM-admin-{workflow}-rollback",
            "role_id": "fixture-role-id",
            "user_id": "fixture-user-id",
        }

    def apply(self, plan_id: str, confirmation: str) -> dict:
        self.calls.append(("apply", (plan_id, confirmation)))
        return {"status": "applied", "plan_id": plan_id, "confirmation": confirmation}

    def verify(self, plan_id: str) -> dict:
        self.calls.append(("verify", (plan_id,)))
        return {"status": "verified", "plan_id": plan_id}

    def rollback(self, plan_id: str, confirmation: str) -> dict:
        self.calls.append(("rollback", (plan_id, confirmation)))
        return {"status": "rolled-back", "plan_id": plan_id, "confirmation": confirmation}

    def audit_log(self) -> list[dict]:
        return [{"action": name, "args": args} for name, args in self.calls]


class AxxonAdminMutationSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_admin_mutation_smoke")

    def args(self, report_dir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            host="demo.internal",
            grpc_port=20109,
            http_url="http://demo.internal",
            username="fixture-admin",
            password="env-password",
            tls_cn="Server",
            ca=Path("/tmp/api.ngp.root-ca.crt"),
            report_dir=report_dir,
            verbose=False,
        )

    def test_parse_rejects_cli_credential_flags_and_requires_env_password(self) -> None:
        with mock.patch.dict(os.environ, {"AXXON_PASSWORD": "env-password"}, clear=False):
            for argv in (["--password", "root"], ["--host", "demo.internal"], ["--pass", "root"]):
                with self.subTest(argv=argv):
                    with redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            self.module.parse_args(
                                ["--i-understand-this-mutates", "--confirm", self.module.CONFIRMATION, *argv]
                            )

        with mock.patch.dict(os.environ, {"AXXON_PASSWORD": ""}, clear=False):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.module.parse_args(["--i-understand-this-mutates", "--confirm", self.module.CONFIRMATION])

    def test_parse_requires_explicit_confirmation(self) -> None:
        with mock.patch.dict(os.environ, {"AXXON_PASSWORD": "env-password"}, clear=False):
            for argv in ([], ["--i-understand-this-mutates"], ["--i-understand-this-mutates", "--confirm", "yes"]):
                with self.subTest(argv=argv):
                    with redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            self.module.parse_args(argv)

            args = self.module.parse_args(["--i-understand-this-mutates", "--confirm", self.module.CONFIRMATION])
            self.assertEqual(args.password, "env-password")

    def test_sanitize_evidence_redacts_sensitive_admin_mutation_fields(self) -> None:
        payload = {
            "target": "demo.internal:20109",
            "username": "fixture-admin",
            "password": "env-password",
            "authorization": "Bearer <fixture-token-value>",
            "ca": "/tmp/api.ngp.root-ca.crt",
            "tls_cn": "Server",
            "role_id": "fixture-role-id",
            "user_id": "fixture-user-id",
            "email": "alice@example.invalid",
            "license_key": "<fixture-license-key>",
            "serial_number": "<fixture-serial-number>",
            "hardware_fingerprint": "<fixture-hardware-fingerprint>",
            "secret_key": "JBSWY3DPEHPK3PXP",
            "verification_code": "123456",
            "message": "demo.internal secret_key=JBSWY3DPEHPK3PXP verification_code=123456 alice@example.invalid",
            "uid": "hosts/Server/DeviceIpint.1",
        }

        clean = self.module.sanitize_evidence(
            payload,
            host="demo.internal",
            username="fixture-admin",
            tls_cn="Server",
            ca_path="/tmp/api.ngp.root-ca.crt",
        )
        text = json.dumps(clean, sort_keys=True)

        for raw in (
            "demo.internal",
            "fixture-admin",
            "env-password",
            "<fixture-token-value>",
            "/tmp/api.ngp.root-ca.crt",
            "fixture-role-id",
            "fixture-user-id",
            "alice@example.invalid",
            "<fixture-license-key>",
            "<fixture-serial-number>",
            "<fixture-hardware-fingerprint>",
            "JBSWY3DPEHPK3PXP",
            "123456",
        ):
            self.assertNotIn(raw, text)
        self.assertIn("<demo-host>", text)
        self.assertIn("<demo-user>", text)
        self.assertIn("<demo-role>", text)
        self.assertIn("Bearer <redacted>", text)
        self.assertIn("hosts/Server/DeviceIpint.1", text)

    def test_fake_run_writes_latest_reports_with_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeAdminMutationRegistry()
            smoke = self.module.AdminMutationSmoke(self.args(Path(tmp)), registry=registry)
            smoke.started_at = dt.datetime(2026, 5, 26, tzinfo=dt.UTC)

            with redirect_stdout(io.StringIO()):
                report = smoke.run()

            json_path = Path(tmp) / "phase-5f-b-admin-mutation-smoke-latest.json"
            md_path = Path(tmp) / "phase-5f-b-admin-mutation-smoke-latest.md"
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            md_text = md_path.read_text(encoding="utf-8")

        self.assertEqual(report["summary"], {"PASS": 7, "WARN": 0, "FAIL": 0})
        self.assertEqual(payload["summary"], {"PASS": 7, "WARN": 0, "FAIL": 0})
        self.assertIn("| PASS | `security_tfa_temp_user_lifecycle` |", md_text)
        self.assertNotIn("demo.internal", json.dumps(payload, sort_keys=True))
        self.assertIn(("list_workflows", ()), registry.calls)
        self.assertIn(("rollback", ("admin-security_tfa_temp_user_lifecycle", "CONFIRM-admin-security_tfa_temp_user_lifecycle-rollback")), registry.calls)


if __name__ == "__main__":
    unittest.main()
