from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_gdpr_cleanup as module


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


class _CleanupReq:
    def __init__(self, user_ids=None):
        self.user_ids = list(user_ids or [])


class _Empty:
    pass


class _Pb2:
    UserDataCleanupRequest = _CleanupReq


class _FakeStub:
    def __init__(self, recorder, service):
        self._rec = recorder
        self._service = service

    def UserDataCleanup(self, request, timeout=None):
        self._rec.append((self._service, "UserDataCleanup", list(request.user_ids), timeout))
        return _Empty()


class FakeCleanupClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _FakeStub(self.calls, service_name)

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpGdprCleanup(
        client_factory=lambda config: FakeCleanupClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.gdpr_cleanup_connect_axxon_profile("env")
    return inst


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.layout_user_data_cleanup(user_ids=["u-1"], confirmation=module.GDPR_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["tool"], "layout_user_data_cleanup")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.map_user_data_cleanup(user_ids=["u-1"], confirmation="wrong")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_empty_ids(self) -> None:
        inst = _inst(enabled=True)
        out = inst.layout_user_data_cleanup(user_ids=[], confirmation=module.GDPR_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class AppliedTests(unittest.TestCase):
    def test_layout_cleanup_applied_records_rpc(self) -> None:
        inst = _inst(enabled=True)
        out = inst.layout_user_data_cleanup(user_ids=["u-1", "", "u-2"], confirmation=module.GDPR_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["tool"], "layout_user_data_cleanup")
        self.assertEqual(out["user_ids"], ["u-1", "u-2"])
        self.assertEqual(len(inst.client.calls), 1)
        service, method, ids, _ = inst.client.calls[0]
        self.assertEqual(service, "LayoutManager")
        self.assertEqual(method, "UserDataCleanup")
        self.assertEqual(ids, ["u-1", "u-2"])

    def test_map_cleanup_applied_records_rpc(self) -> None:
        inst = _inst(enabled=True)
        out = inst.map_user_data_cleanup(user_ids=["m-1"], confirmation=module.GDPR_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["tool"], "map_user_data_cleanup")
        service, method, ids, _ = inst.client.calls[0]
        self.assertEqual(service, "MapService")
        self.assertEqual(ids, ["m-1"])

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.map_user_data_cleanup(user_ids=["m-1"], confirmation=module.GDPR_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
