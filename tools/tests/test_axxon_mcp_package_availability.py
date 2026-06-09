from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_package_availability as module

_SECRET = "PKG-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = _SECRET
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class _OperationSystem:
    Windows = 0
    Linux = 1
    _by_name = {"Windows": 0, "Linux": 1}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _CheckResponse:
    def __init__(self, package_id="pkg-1", product_name="Axxon One", package_version="2026.1", package_size_bytes=123456):
        self.package_id = package_id
        self.product_name = product_name
        self.package_version = package_version
        self.package_size_bytes = package_size_bytes


class _CheckRequest:
    OperationSystem = _OperationSystem

    def __init__(self, system=0, machine=""):
        self.system = system
        self.machine = machine


class _Pb2:
    CheckPackageAvailabilityRequest = _CheckRequest


class _Stub:
    def __init__(self, rec, response=None):
        self._rec = rec
        self._response = response

    def CheckPackageAvailability(self, request, timeout=None):
        self._rec.append(("CheckPackageAvailability", request.system, request.machine))
        return self._response if self._response is not None else _CheckResponse()


class FakeClient:
    def __init__(self, config, response=None):
        self.config = config
        self.calls: list = []
        self._response = response

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._response)

    def import_module(self, name):
        return _Pb2()


def _inst(response=None):
    inst = module.AxxonMcpPackageAvailability(
        client_factory=lambda config: FakeClient(config, response),
        config_factory=lambda: FakeConfig(),
    )
    inst.package_availability_connect_axxon_profile("env")
    return inst


class PackageAvailabilityTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().package_availability_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_check_ok(self) -> None:
        out = _inst().check_package_availability(system="Linux", machine="node-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "check_package_availability")
        self.assertEqual(out["package_id"], "pkg-1")
        self.assertEqual(out["product_name"], "Axxon One")
        self.assertEqual(out["package_version"], "2026.1")
        self.assertEqual(out["package_size_bytes"], 123456)

    def test_passes_system_and_machine(self) -> None:
        inst = _inst()
        inst.check_package_availability(system="Windows", machine="node-2")
        _, system, machine = inst.client.calls[0]
        self.assertEqual(system, 0)
        self.assertEqual(machine, "node-2")

    def test_invalid_system_returns_gap(self) -> None:
        out = _inst().check_package_availability(system="BeOS")
        self.assertEqual(out["status"], "gap")
        self.assertIn("BeOS", out["message"])

    def test_no_secret_leak(self) -> None:
        out = _inst().check_package_availability(system="Linux")
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("check_package_availability", module.PACKAGE_AVAILABILITY_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
