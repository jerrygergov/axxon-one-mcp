from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_global_tracker as module

_SECRET = "GT-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)
_IMAGE_BYTES = b"FACE-IMAGE-BYTES-SHOULD-NOT-LEAK-" + (b"\xff" * 512)


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


class _Images:
    raw = _IMAGE_BYTES


class _Profile:
    def __init__(self, id="guid-1", which="data_string", data_string="PLATE-123"):
        self.id = id
        self.type = 0
        self._which = which
        self.data_string = data_string if which == "data_string" else ""
        self.data_images = _Images()

    def WhichOneof(self, field):
        return self._which


class _GetProfileResponse:
    def __init__(self, profile=None):
        self.profile = profile if profile is not None else _Profile()

    def HasField(self, name):
        return name == "profile"


class _GetProfileRequest:
    def __init__(self, id="", load_images=False):
        self.id = id
        self.load_images = load_images


class _Pb2:
    GetProfileRequest = _GetProfileRequest


class _Stub:
    def __init__(self, rec, profile=None, stream_count=1):
        self._rec = rec
        self._profile = profile
        self._stream_count = stream_count

    def GetProfile(self, request, timeout=None):
        self._rec.append(("GetProfile", request.id, request.load_images))
        for _ in range(self._stream_count):
            yield _GetProfileResponse(self._profile)


class FakeClient:
    def __init__(self, config, profile=None, stream_count=1):
        self.config = config
        self.calls: list = []
        self._profile = profile
        self._stream_count = stream_count

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._profile, self._stream_count)

    def import_module(self, name):
        return _Pb2()


def _inst(profile=None, stream_count=1):
    inst = module.AxxonMcpGlobalTracker(
        client_factory=lambda config: FakeClient(config, profile, stream_count),
        config_factory=lambda: FakeConfig(),
    )
    inst.global_tracker_connect_axxon_profile("env")
    return inst


class GetProfileTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().global_tracker_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_get_profile_requires_id(self) -> None:
        out = _inst().get_profile(profile_id="")
        self.assertEqual(out["status"], "gap")
        self.assertIn("profile_id", out["message"])

    def test_get_profile_ok_summarizes_metadata(self) -> None:
        out = _inst().get_profile(profile_id="guid-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "get_profile")
        self.assertEqual(out["count"], 1)
        prof = out["profiles"][0]
        self.assertEqual(prof["id"], "guid-1")
        self.assertEqual(prof["data_kind"], "data_string")
        self.assertEqual(prof["data_string"], "PLATE-123")

    def test_get_profile_never_loads_or_leaks_images(self) -> None:
        face = _Profile(which="data_images")
        inst = _inst(profile=face)
        out = inst.get_profile(profile_id="guid-2")
        # load_images must be forced False on the wire
        _, _, load_images = inst.client.calls[0]
        self.assertFalse(load_images)
        # image bytes must never appear in output
        self.assertNotIn("FACE-IMAGE-BYTES", str(out))
        self.assertNotIn(b"FACE-IMAGE-BYTES".decode(), str(out))
        prof = out["profiles"][0]
        self.assertEqual(prof["data_kind"], "data_images")
        self.assertNotIn("raw", str(prof))

    def test_get_profile_caps_stream(self) -> None:
        out = _inst(stream_count=100).get_profile(profile_id="guid-1", max_items=5)
        self.assertEqual(out["count"], 5)
        self.assertTrue(out["truncated"])

    def test_no_config_secret_leak(self) -> None:
        out = _inst().get_profile(profile_id="guid-1")
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("get_profile", module.GLOBAL_TRACKER_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
