from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_license_reads as module

_SECRET_KEY = "LICENSE-KEY-SHOULD-NOT-LEAK-" + ("X" * 200)


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


class _LicenseKeyResp:
    license_key = _SECRET_KEY


class _RestrictionsResp:
    def __init__(self, restrictions=True, available=True):
        self._fields = set()
        if restrictions:
            self._fields.add("restrictions")
        if available:
            self._fields.add("available_restrictions")

    def HasField(self, name):
        return name in self._fields


class _Empty:
    pass


class _Pb2:
    LicenseKeyRequest = _Empty
    RestrictionsRequest = _Empty


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def LicenseKey(self, request, timeout=None):
        self._rec.append(("LicenseKey",))
        return _LicenseKeyResp()

    def Restrictions(self, request, timeout=None):
        self._rec.append(("Restrictions",))
        return _RestrictionsResp()


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpLicenseReads(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.license_reads_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_get_license_key_metadata_only(self) -> None:
        out = _inst().get_license_key()
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["key_present"])
        self.assertEqual(out["key_length"], len(_SECRET_KEY))

    def test_get_license_key_never_leaks_value(self) -> None:
        out = _inst().get_license_key()
        self.assertNotIn(_SECRET_KEY, str(out))
        self.assertNotIn("LICENSE-KEY-SHOULD-NOT-LEAK", str(out))

    def test_get_restrictions_ok(self) -> None:
        out = _inst().get_restrictions()
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["restrictions_present"])
        self.assertTrue(out["available_present"])

    def test_no_config_secret_leak(self) -> None:
        out = _inst().get_restrictions()
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
