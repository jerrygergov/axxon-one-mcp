from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_audit as module


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_PASSWORD_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _FakeRequest:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakePb2:
    """Stands in for the generated Audit_pb2 module: every *Request is a recorder."""

    def __getattr__(self, name):
        return _FakeRequest


class _FakeStub:
    def __init__(self, recorder):
        self._recorder = recorder

    def __getattr__(self, method_name):
        def _call(request, timeout=None):
            self._recorder.append((method_name, request.kwargs, timeout))
            return object()  # empty AuditClientResponse
        return _call


class FakeAuditClient:
    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self.injected: list[tuple] = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "AuditEventInjector"
        return _FakeStub(self.injected)

    def import_module(self, name):
        return _FakePb2()


def _audit(**overrides):
    inst = module.AxxonMcpAudit(
        client_factory=lambda config: FakeAuditClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.audit_connect_axxon_profile("env")
    return inst


class AuditEventKindsTests(unittest.TestCase):
    def test_kind_catalog_lists_required_fields(self) -> None:
        inst = module.AxxonMcpAudit()
        cat = inst.list_audit_event_kinds()
        kinds = {k["kind"]: k["required"] for k in cat["kinds"]}
        self.assertEqual(kinds["camera_viewing"], ["camera_ap"])
        self.assertEqual(kinds["ptz_control"], ["camera_ap"])
        self.assertEqual(kinds["archive_viewing"], ["camera_ap", "archive_ap"])
        self.assertEqual(kinds["journal_export"], ["start", "end"])
        self.assertEqual(kinds["client_app_option"], ["group", "setting", "setting_value"])
        self.assertEqual(kinds["ldap_setup"], ["ldap", "group", "setting", "setting_value"])
        self.assertNotIn("mm_export", kinds)


class AuditInjectGatingTests(unittest.TestCase):
    def test_inject_disabled_without_approval(self) -> None:
        inst = _audit(enabled=False)
        out = inst.audit_inject("camera_viewing", {"camera_ap": "hosts/Server/cam"}, "CONFIRM-audit-inject")
        self.assertEqual(out["status"], "disabled")

    def test_inject_rejects_bad_confirmation(self) -> None:
        inst = _audit(enabled=True)
        out = inst.audit_inject("camera_viewing", {"camera_ap": "hosts/Server/cam"}, "WRONG")
        self.assertIn(out["status"], ("gap", "error"))
        self.assertEqual(inst.client.injected, [])

    def test_inject_unknown_kind(self) -> None:
        inst = _audit(enabled=True)
        out = inst.audit_inject("teleport", {}, "CONFIRM-audit-inject")
        self.assertEqual(out["status"], "error")
        self.assertIn("kind", out["message"])
        self.assertEqual(inst.client.injected, [])

    def test_inject_missing_required_param(self) -> None:
        inst = _audit(enabled=True)
        out = inst.audit_inject("archive_viewing", {"camera_ap": "hosts/Server/cam"}, "CONFIRM-audit-inject")
        self.assertEqual(out["status"], "error")
        self.assertIn("archive_ap", out["message"])
        self.assertEqual(inst.client.injected, [])

    def test_inject_success_calls_wire(self) -> None:
        inst = _audit(enabled=True)
        out = inst.audit_inject("camera_viewing", {"camera_ap": "hosts/Server/cam"}, "CONFIRM-audit-inject")
        self.assertEqual(out["status"], "injected")
        self.assertEqual(out["kind"], "camera_viewing")
        self.assertEqual(len(inst.client.injected), 1)
        method, kwargs, _ = inst.client.injected[0]
        self.assertEqual(method, "InjectCameraViewingEvent")
        self.assertEqual(kwargs, {"camera_ap": "hosts/Server/cam"})

    def test_inject_archive_viewing_maps_two_fields(self) -> None:
        inst = _audit(enabled=True)
        out = inst.audit_inject(
            "archive_viewing",
            {"camera_ap": "hosts/Server/cam", "archive_ap": "hosts/Server/arc"},
            "CONFIRM-audit-inject",
        )
        self.assertEqual(out["status"], "injected")
        method, kwargs, _ = inst.client.injected[0]
        self.assertEqual(method, "InjectArchiveViewingEvent")
        self.assertEqual(kwargs, {"camera_ap": "hosts/Server/cam", "archive_ap": "hosts/Server/arc"})


if __name__ == "__main__":
    unittest.main()
