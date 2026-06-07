from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_bookmark_extras as module


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


class _ExportedTime:
    def __init__(self):
        self.value = None

    def FromDatetime(self, dt):
        self.value = dt


class _Bookmark:
    def __init__(self, bid="bk-1", message="orig"):
        self.id = bid
        self.message = message

    def HasField(self, name):
        return name == "boundary"


class _GetResp:
    def __init__(self, bid="bk-1"):
        self.bookmark = _Bookmark(bid)


class _UpdateResp:
    def __init__(self, bookmark):
        self.bookmark = bookmark


class _RenderResp:
    def __init__(self, bid="bk-1"):
        self.bookmark = _Bookmark(bid)


class _GetReq:
    def __init__(self, id=""):
        self.id = id


class _UpdateReq:
    def __init__(self, bookmark=None):
        self.bookmark = bookmark


class _SetExportedReq:
    def __init__(self, id=""):
        self.id = id
        self.exported_time = _ExportedTime()


class _RenderReq:
    def __init__(self, bookmark=None):
        self.bookmark = bookmark


class _Pb2:
    GetBookmarkRequest = _GetReq
    UpdateBookmarkRequest = _UpdateReq
    SetExportedTimeRequest = _SetExportedReq
    RenderTrackRequest = _RenderReq


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def GetBookmark(self, request, timeout=None):
        self._rec.append(("GetBookmark", request.id))
        return _GetResp(request.id or "bk-1")

    def UpdateBookmark(self, request, timeout=None):
        self._rec.append(("UpdateBookmark", request.bookmark.id, request.bookmark.message))
        return _UpdateResp(request.bookmark)

    def SetExportedTime(self, request, timeout=None):
        self._rec.append(("SetExportedTime", request.id))
        return object()

    def RenderTrack(self, request, timeout=None):
        self._rec.append(("RenderTrack", request.bookmark.id))
        return _RenderResp(request.bookmark.id)


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
    inst = module.AxxonMcpBookmarkExtras(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.bookmark_extras_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_render_track_ok(self) -> None:
        out = _inst().render_bookmark_track(bookmark_id="bk-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["bookmark_id"], "bk-1")
        self.assertTrue(out["has_boundary"])

    def test_render_track_empty_id_no_wire(self) -> None:
        inst = _inst()
        out = inst.render_bookmark_track(bookmark_id="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_update_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.update_bookmark(bookmark_id="bk-1", message="x", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_update_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_bookmark(bookmark_id="bk-1", message="x", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_update_error_on_empty_id_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_bookmark(bookmark_id="", message="x", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_set_exported_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.set_bookmark_exported_time(bookmark_id="bk-1", exported_time="2026-06-07T07:00:00", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_set_exported_error_on_missing_time_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.set_bookmark_exported_time(bookmark_id="bk-1", exported_time="", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_update_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_bookmark(bookmark_id="bk-1", message="new", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["message"], "new")
        names = [c[0] for c in inst.client.calls]
        self.assertEqual(names, ["GetBookmark", "UpdateBookmark"])

    def test_set_exported_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.set_bookmark_exported_time(bookmark_id="bk-1", exported_time="2026-06-07T07:00:00", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(inst.client.calls[0][0], "SetExportedTime")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_bookmark(bookmark_id="bk-1", message="x", confirmation=module.BOOKMARK_EXTRAS_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
