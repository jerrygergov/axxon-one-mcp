from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_filesystem_browser as module

_SECRET = "FS-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _FSError:
    def __init__(self, status=0, message=""):
        self.status = status
        self.message = message


class _FileInfo:
    def __init__(self, path="/srv", name="archive", type=2, perms=3, size_bytes=4096):
        self.path = path
        self.name = name
        self.type = type
        self.perms = perms
        self.size_bytes = size_bytes


class _ListResponse:
    def __init__(self, entries=None, next_page_token="", error_status=0):
        self.entries = entries if entries is not None else [_FileInfo()]
        self.next_page_token = next_page_token
        self.error = _FSError(status=error_status)


class _FileInfoResponse:
    def __init__(self, error_status=0):
        self.file_info = _FileInfo()
        self.parent_path = "/srv"
        self.error = _FSError(status=error_status)


class _SpaceInfo:
    capacity_bytes = 1000000
    free_bytes = 250000


class _SpaceResponse:
    def __init__(self, error_status=0):
        self.space_info = _SpaceInfo()
        self.error = _FSError(status=error_status)


class _EFileType:
    FILE_TYPE_UNSPECIFIED = 0
    REGULAR_FILE = 1
    DIRECTORY = 2
    BLOCK_DEVICE = 3
    _by_name = {"FILE_TYPE_UNSPECIFIED": 0, "REGULAR_FILE": 1, "DIRECTORY": 2, "BLOCK_DEVICE": 3}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]

    @classmethod
    def Name(cls, number):
        return {v: k for k, v in cls._by_name.items()}[number]


class _EFSPermissions:
    _by_num = {0: "NONE", 1: "READ", 2: "WRITE", 3: "READ_WRITE"}

    @classmethod
    def Name(cls, number):
        return cls._by_num[number]


class _FSErrorECode:
    _by_num = {0: "OK", 1: "NOT_FOUND", 2: "PERMISSIONS_ERROR", 10: "NOT_A_DIRECTORY", 11: "INVALID_PATH"}

    @classmethod
    def Name(cls, number):
        return cls._by_num[number]


class _FSErrorType:
    ECode = _FSErrorECode


class _ListDirectoryRequest:
    def __init__(self, node_name="", path="", type=0, name_pattern="", page_size=0, page_token=""):
        self.node_name = node_name
        self.path = path
        self.type = type
        self.name_pattern = name_pattern
        self.page_size = page_size
        self.page_token = page_token


class _GetFileInfoRequest:
    def __init__(self, node_name="", path=""):
        self.node_name = node_name
        self.path = path


class _GetSpaceRequest:
    def __init__(self, node_name="", path=""):
        self.node_name = node_name
        self.path = path


class _Pb2:
    EFileType = _EFileType
    EFSPermissions = _EFSPermissions
    FSError = _FSErrorType
    ListDirectoryRequest = _ListDirectoryRequest
    GetFileInfoRequest = _GetFileInfoRequest
    GetSpaceRequest = _GetSpaceRequest


class _Stub:
    def __init__(self, rec, list_resp=None, info_resp=None, space_resp=None):
        self._rec = rec
        self._list = list_resp
        self._info = info_resp
        self._space = space_resp

    def ListDirectory(self, request, timeout=None):
        self._rec.append(("ListDirectory", request.path, request.page_size))
        return self._list if self._list is not None else _ListResponse()

    def GetFileInfo(self, request, timeout=None):
        self._rec.append(("GetFileInfo", request.path))
        return self._info if self._info is not None else _FileInfoResponse()

    def GetSpace(self, request, timeout=None):
        self._rec.append(("GetSpace", request.path))
        return self._space if self._space is not None else _SpaceResponse()


class FakeClient:
    def __init__(self, config, list_resp=None, info_resp=None, space_resp=None):
        self.config = config
        self.calls: list = []
        self._list = list_resp
        self._info = info_resp
        self._space = space_resp

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._list, self._info, self._space)

    def import_module(self, name):
        return _Pb2()


def _inst(list_resp=None, info_resp=None, space_resp=None):
    inst = module.AxxonMcpFilesystemBrowser(
        client_factory=lambda config: FakeClient(config, list_resp, info_resp, space_resp),
        config_factory=lambda: FakeConfig(),
    )
    inst.filesystem_browser_connect_axxon_profile("env")
    return inst


class ListDirectoryTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().filesystem_browser_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_list_directory_ok(self) -> None:
        out = _inst().list_directory(path="/srv")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "list_directory")
        self.assertEqual(out["count"], 1)
        entry = out["entries"][0]
        self.assertEqual(entry["name"], "archive")
        self.assertEqual(entry["type"], "DIRECTORY")
        self.assertEqual(entry["perms"], "READ_WRITE")

    def test_list_directory_caps_page_size(self) -> None:
        inst = _inst()
        inst.list_directory(path="/srv", page_size=999999)
        _, _, page_size = inst.client.calls[0]
        self.assertLessEqual(page_size, module.MAX_ENTRIES)

    def test_list_directory_fs_error_surfaces(self) -> None:
        out = _inst(list_resp=_ListResponse(error_status=1)).list_directory(path="/nope")
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], "NOT_FOUND")

    def test_invalid_type_filter_returns_gap(self) -> None:
        out = _inst().list_directory(path="/srv", type="BOGUS")
        self.assertEqual(out["status"], "gap")
        self.assertIn("BOGUS", out["message"])


class GetFileInfoTests(unittest.TestCase):
    def test_get_file_info_ok(self) -> None:
        out = _inst().get_file_info(path="/srv/archive")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["file_info"]["name"], "archive")
        self.assertEqual(out["parent_path"], "/srv")

    def test_get_file_info_error(self) -> None:
        out = _inst(info_resp=_FileInfoResponse(error_status=11)).get_file_info(path="??")
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], "INVALID_PATH")


class GetSpaceTests(unittest.TestCase):
    def test_get_space_ok(self) -> None:
        out = _inst().get_space(path="/srv")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["capacity_bytes"], 1000000)
        self.assertEqual(out["free_bytes"], 250000)


class CommonTests(unittest.TestCase):
    def test_no_secret_leak(self) -> None:
        out = _inst().list_directory(path="/srv")
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        for name in ("list_directory", "get_file_info", "get_space"):
            self.assertIn(name, module.FILESYSTEM_BROWSER_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
