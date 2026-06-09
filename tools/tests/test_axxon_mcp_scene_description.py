from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_scene_description as module

_SECRET = "SCENE-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _SceneDescription:
    def __init__(self, access_point="hosts/Server/Scene.1", camera_access_point="hosts/Server/Camera.1", scene_description_class=3):
        self.access_point = access_point
        self.camera_access_point = camera_access_point
        self.scene_description_class = scene_description_class


class _SceneResponse:
    def __init__(self, scenes=None, next_page_token=""):
        self.scene_descriptions = scenes if scenes is not None else [_SceneDescription()]
        self.next_page_token = next_page_token


class _SceneRequest:
    def __init__(self, page_token="", page_size=0):
        self.page_token = page_token
        self.page_size = page_size


class _Pb2:
    ListSceneDescriptionRequest = _SceneRequest


class _Stub:
    def __init__(self, rec, response=None):
        self._rec = rec
        self._response = response

    def ListSceneDescription(self, request, timeout=None):
        self._rec.append(("ListSceneDescription", request.page_token, request.page_size))
        return self._response if self._response is not None else _SceneResponse()


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
    inst = module.AxxonMcpSceneDescription(
        client_factory=lambda config: FakeClient(config, response),
        config_factory=lambda: FakeConfig(),
    )
    inst.scene_description_connect_axxon_profile("env")
    return inst


class SceneDescriptionTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().scene_description_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_list_scene_description_ok(self) -> None:
        out = _inst().list_scene_description()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "list_scene_description")
        self.assertEqual(out["count"], 1)
        scene = out["scenes"][0]
        self.assertEqual(scene["camera_access_point"], "hosts/Server/Camera.1")
        self.assertEqual(scene["scene_description_class"], 3)

    def test_passes_paging_args(self) -> None:
        inst = _inst()
        inst.list_scene_description(page_token="abc", page_size=50)
        _, token, size = inst.client.calls[0]
        self.assertEqual(token, "abc")
        self.assertEqual(size, 50)

    def test_next_page_token_returned(self) -> None:
        out = _inst(response=_SceneResponse(next_page_token="more")).list_scene_description()
        self.assertEqual(out["next_page_token"], "more")

    def test_no_secret_leak(self) -> None:
        out = _inst().list_scene_description()
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("list_scene_description", module.SCENE_DESCRIPTION_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
