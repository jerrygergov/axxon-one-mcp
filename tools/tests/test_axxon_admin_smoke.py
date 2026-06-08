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


class FakeAdminTool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def admin_connect_axxon_profile(self, profile: str = "env") -> dict:
        self.calls.append(("connect", {"profile": profile}))
        return {"status": "ok", "connected": True, "profile_name": profile}

    def security_inventory(self) -> dict:
        self.calls.append(("security_inventory", {}))
        return {
            "status": "ok",
            "tool": "security_inventory",
            "roles": {"items": [{"id": "role-a", "name": "admin"}]},
        }

    def security_policy_summary(self) -> dict:
        self.calls.append(("security_policy_summary", {}))
        return {"status": "ok", "tool": "security_policy_summary"}

    def role_permissions(self, role_id: str, page_size: int = 50) -> dict:
        self.calls.append(("role_permissions", {"role_id": role_id, "page_size": page_size}))
        return {"status": "ok", "tool": "role_permissions", "role_id": role_id, "page_size": page_size}

    def current_user_security(self) -> dict:
        self.calls.append(("current_user_security", {}))
        return {"status": "ok", "tool": "current_user_security"}

    def license_status(self) -> dict:
        self.calls.append(("license_status", {}))
        return {"status": "ok", "tool": "license_status"}

    def time_status(self) -> dict:
        self.calls.append(("time_status", {}))
        return {"status": "ok", "tool": "time_status"}

    def system_health(self) -> dict:
        self.calls.append(("system_health", {}))
        return {"status": "ok", "tool": "system_health"}

    def domain_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict:
        self.calls.append(
            (
                "domain_event_subscribe",
                {
                    "subjects": list(subjects or []),
                    "event_types": list(event_types or []),
                    "timeout_s": timeout_s,
                    "limit": limit,
                    "detailed": detailed,
                },
            )
        )
        return {"status": "ok", "tool": "domain_event_subscribe", "count": 0}

    def node_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict:
        self.calls.append(
            (
                "node_event_subscribe",
                {
                    "subjects": list(subjects or []),
                    "event_types": list(event_types or []),
                    "timeout_s": timeout_s,
                    "limit": limit,
                    "detailed": detailed,
                },
            )
        )
        return {"status": "ok", "tool": "node_event_subscribe", "count": 0}

    def schedule_descriptor_get(self, uid: str) -> dict:
        self.calls.append(("schedule_descriptor_get", {"uid": uid}))
        return {"status": "ok", "tool": "schedule_descriptor_get", "target": uid}


class AxxonAdminSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("axxon_admin_smoke")

    def args(self, report_dir: Path, *, include_node_notifier: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            host="demo.internal",
            grpc_port=20109,
            http_url="http://demo.internal",
            username="root",
            password="secret",
            tls_cn="Server",
            ca=Path("/tmp/api.ngp.root-ca.crt"),
            report_dir=report_dir,
            notifier_timeout=3.0,
            notifier_limit=7,
            notifier_subjects=["hosts/Server"],
            notifier_event_types=["config"],
            notifier_detailed=True,
            include_node_notifier=include_node_notifier,
            role_page_size=25,
            schedule_uid="hosts/Server/DeviceIpint.1",
            verbose=False,
        )

    def test_cli_defaults_are_bounded_and_domain_only(self) -> None:
        args = self.module.parse_args([])

        self.assertEqual(args.notifier_timeout, 5.0)
        self.assertEqual(args.notifier_limit, 25)
        self.assertEqual(args.role_page_size, 50)
        self.assertFalse(args.include_node_notifier)
        self.assertEqual(args.schedule_uid, "")

    def test_cli_caps_are_clamped(self) -> None:
        high = self.module.parse_args(["--notifier-timeout", "99", "--notifier-limit", "999", "--role-page-size", "999"])
        low = self.module.parse_args(["--notifier-timeout", "0", "--notifier-limit", "0", "--role-page-size", "0"])

        self.assertEqual(high.notifier_timeout, 30.0)
        self.assertEqual(high.notifier_limit, 100)
        self.assertEqual(high.role_page_size, 100)
        self.assertEqual(low.notifier_timeout, 1.0)
        self.assertEqual(low.notifier_limit, 1)
        self.assertEqual(low.role_page_size, 1)

    def test_rejects_cli_connection_and_abbreviated_credential_flags(self) -> None:
        for argv in (["--password", "root"], ["--host", "demo.internal"], ["--pass", "root"], ["--user", "root"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        self.module.parse_args(argv)

    def test_include_node_notifier_dispatches_optional_node_pull(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = FakeAdminTool()
            smoke = self.module.AdminSmoke(self.args(Path(tmp), include_node_notifier=True), tool=tool)

            with redirect_stdout(io.StringIO()):
                report = smoke.run()

        call_names = [name for name, _params in tool.calls]
        self.assertIn("domain_event_subscribe", call_names)
        self.assertIn("node_event_subscribe", call_names)
        self.assertEqual(report["summary"]["FAIL"], 0)

    def test_default_run_skips_node_notifier_and_uses_discovered_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = FakeAdminTool()
            smoke = self.module.AdminSmoke(self.args(Path(tmp)), tool=tool)

            with redirect_stdout(io.StringIO()):
                smoke.run()

        self.assertNotIn("node_event_subscribe", [name for name, _params in tool.calls])
        self.assertIn(("role_permissions", {"role_id": "role-a", "page_size": 25}), tool.calls)
        self.assertIn(("schedule_descriptor_get", {"uid": "hosts/Server/DeviceIpint.1"}), tool.calls)

    def test_write_report_sanitizes_host_user_ca_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            smoke = object.__new__(self.module.AdminSmoke)
            smoke.started_at = dt.datetime(2026, 5, 26, tzinfo=dt.UTC)
            smoke.args = self.args(Path(tmp))
            smoke.context = {}
            smoke.results = [
                {
                    "group": "license_status",
                    "status": "PASS",
                    "elapsed_ms": 1,
                    "evidence": {
                        "url": "http://demo.internal/api",
                        "username": "fixture-admin",
                        "user_id": "fixture-user-123",
                        "role_id": "fixture-role-123",
                        "role_ids": ["fixture-role-456"],
                        "name": "Alice Example",
                        "email": "alice@example.invalid",
                        "password": "secret",
                        "ca": "/tmp/api.ngp.root-ca.crt",
                        "authorization": "Bearer live-token",
                        "message": "certificate path /tmp/api.ngp.root-ca.crt owned by bob@example.invalid",
                        "uid": "hosts/Server/DeviceIpint.1",
                    },
                }
            ]

            with redirect_stdout(io.StringIO()):
                smoke.write_report(smoke.report())

            json_text = (Path(tmp) / "phase-5f-admin-smoke-latest.json").read_text(encoding="utf-8")
            md_text = (Path(tmp) / "phase-5f-admin-smoke-latest.md").read_text(encoding="utf-8")
            payload = json.loads(json_text)

        self.assertNotIn("demo.internal", json_text)
        self.assertNotIn("root", json_text)
        self.assertNotIn("fixture-user-123", json_text)
        self.assertNotIn("fixture-role-123", json_text)
        self.assertNotIn("fixture-role-456", json_text)
        self.assertNotIn("Alice Example", json_text)
        self.assertNotIn("alice@example.invalid", json_text)
        self.assertNotIn("bob@example.invalid", json_text)
        self.assertNotIn("secret", json_text)
        self.assertNotIn("live-token", json_text)
        self.assertNotIn("/tmp/api.ngp.root-ca.crt", json_text)
        self.assertIn("<demo-host>", payload["target"]["grpc_target"])
        self.assertIn("Bearer <redacted>", json_text)
        self.assertIn("hosts/Server/DeviceIpint.1", json_text)
        self.assertNotIn("demo.internal", md_text)
        self.assertNotIn("secret", md_text)


if __name__ == "__main__":
    unittest.main()
