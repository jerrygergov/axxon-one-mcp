from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_package_availability as module

_SECRET = "PKG-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)
_INSTALLER_BYTES = b"INSTALLER-BYTES-SHOULD-NOT-LEAK-" + (b"I" * 128)


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


class _DownloadRequest:
    def __init__(self, package_id="", chunk_size_kb=0, start_from_chunk_index=0):
        self.package_id = package_id
        self.chunk_size_kb = chunk_size_kb
        self.start_from_chunk_index = start_from_chunk_index


class _DownloadResponse:
    def __init__(self, index=0, data=b""):
        self.index = index
        self.data = data


class _Pb2:
    CheckPackageAvailabilityRequest = _CheckRequest
    DownloadInstallerPackageRequest = _DownloadRequest


class _Stub:
    def __init__(self, rec, response=None, chunks=3):
        self._rec = rec
        self._response = response
        self._chunks = chunks

    def CheckPackageAvailability(self, request, timeout=None):
        self._rec.append(("CheckPackageAvailability", request.system, request.machine))
        return self._response if self._response is not None else _CheckResponse()

    def DownloadInstallerPackage(self, request, timeout=None):
        self._rec.append(("DownloadInstallerPackage", request.package_id, request.chunk_size_kb, request.start_from_chunk_index))
        start = int(request.start_from_chunk_index)
        for index in range(start, self._chunks):
            yield _DownloadResponse(index=index, data=_INSTALLER_BYTES)


class FakeClient:
    def __init__(self, config, response=None, chunks=3):
        self.config = config
        self.calls: list = []
        self._response = response
        self._chunks = chunks

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._response, self._chunks)

    def import_module(self, name):
        return _Pb2()


def _inst(response=None, chunks=3):
    inst = module.AxxonMcpPackageAvailability(
        client_factory=lambda config: FakeClient(config, response, chunks),
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
        self.assertIn("download_installer_package_probe", module.PACKAGE_AVAILABILITY_TOOL_NAMES)

    def test_download_probe_counts_bytes_without_returning_blob(self) -> None:
        out = _inst(chunks=3).download_installer_package_probe("pkg-1", max_chunks=8, max_bytes=1024 * 1024)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "download_installer_package_probe")
        self.assertEqual(out["chunks_seen"], 3)
        self.assertEqual(out["bytes_seen"], 3 * len(_INSTALLER_BYTES))
        self.assertFalse(out["truncated"])
        self.assertNotIn("INSTALLER-BYTES-SHOULD-NOT-LEAK", str(out))

    def test_download_probe_caps_chunks(self) -> None:
        out = _inst(chunks=100).download_installer_package_probe("pkg-1", max_chunks=2)
        self.assertEqual(out["chunks_seen"], 2)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["stop_reason"], "chunk_cap")

    def test_download_probe_caps_bytes(self) -> None:
        out = _inst(chunks=100).download_installer_package_probe("pkg-1", max_bytes=len(_INSTALLER_BYTES) + 1)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["stop_reason"], "byte_cap")
        self.assertLessEqual(out["chunks_seen"], 2)

    def test_download_probe_passes_request_options(self) -> None:
        inst = _inst(chunks=4)
        inst.download_installer_package_probe("pkg-1", chunk_size_kb=32, start_from_chunk_index=2)
        call = [c for c in inst.client.calls if c[0] == "DownloadInstallerPackage"][0]
        self.assertEqual(call, ("DownloadInstallerPackage", "pkg-1", 32, 2))


if __name__ == "__main__":
    unittest.main()
