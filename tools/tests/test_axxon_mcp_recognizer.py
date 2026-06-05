from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_recognizer as module


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


class _Req:
    def __init__(self, **kw):
        self.kw = kw


class _Pb2:
    # EListType enum values
    ELT_Any, ELT_Face, ELT_LPR, ELT_Food = 0, 1, 2, 3

    def __getattr__(self, name):
        return _Req


class _Stub:
    def __init__(self, client):
        self._c = client

    def GetLists(self, req, timeout=None):
        self._c.calls.append(("GetLists", req.kw))
        return {"lists": [
            {"id": "L1", "name": "Faces", "type": "ELT_Face", "score": 0.7,
             "item_ids": ["a", "b", "c"]},
        ]}

    def GetListStream(self, req, timeout=None):
        self._c.calls.append(("GetListStream", req.kw))
        yield {"status": "ok", "list": {"id": req.kw.get("list_id"), "name": "Faces"}}

    def GetItems(self, req, timeout=None):
        self._c.calls.append(("GetItems", req.kw))
        # Simulate 4 items streamed one per page; one face, one LPR.
        rows = [
            {"item": {"id": "a", "data_meta": {"name": "Alice", "face_meta": {"full_name": "Alice A"}}}},
            {"item": {"id": "b", "data_meta": {"name": "Bob", "face_meta": {"full_name": "Bob B"}}}},
            {"item": {"id": "c", "data_string": "PLATE-123"}},
            {"item": {"id": "d", "data_meta": {"name": "Dave"}}},
        ]
        for r in rows:
            yield r


class FakeRecognizerClient:
    def __init__(self, config: FakeConfig):
        self.config = config
        self.calls: list[tuple] = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto, svc):
        assert svc == "RealtimeRecognizerService"
        return _Stub(self)

    def import_module(self, name):
        return _Pb2()

    def message_to_dict(self, message):
        return message  # fakes already return dicts


def _rec():
    inst = module.AxxonMcpRecognizer(
        client_factory=lambda config: FakeRecognizerClient(config),
        config_factory=lambda: FakeConfig(),
    )
    inst.recognizer_connect_axxon_profile("env")
    return inst


class RecognizerListsTests(unittest.TestCase):
    def test_list_lists_returns_summary_with_item_count(self) -> None:
        out = _rec().list_recognizer_lists()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 1)
        lst = out["lists"][0]
        self.assertEqual(lst["id"], "L1")
        self.assertEqual(lst["name"], "Faces")
        self.assertEqual(lst["item_count"], 3)

    def test_list_type_maps_to_enum(self) -> None:
        inst = _rec()
        inst.list_recognizer_lists(list_type="face")
        method, kw = inst.client.calls[0]
        self.assertEqual(method, "GetLists")
        self.assertEqual(kw.get("type"), _Pb2.ELT_Face)

    def test_get_list_streams_descriptor(self) -> None:
        out = _rec().get_recognizer_list("L1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["list"]["id"], "L1")

    def test_list_items_metadata_only_no_biometrics(self) -> None:
        out = _rec().list_recognizer_items()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 4)
        # GetItems must be called with empty required_items (no images/vectors).
        self.assertEqual(out["_req"].get("required_items", []), [])
        self.assertFalse(out["_req"].get("load_images"))
        self.assertFalse(out["_req"].get("load_vectors"))
        # GetItemsRequest has no list_ids field; the request must never carry one.
        self.assertNotIn("list_ids", out["_req"])
        items = out["items"]
        self.assertEqual(items[0]["id"], "a")
        self.assertEqual(items[0]["name"], "Alice")
        self.assertEqual(items[0]["full_name"], "Alice A")
        # LPR item surfaces data_string
        lpr = next(i for i in items if i["id"] == "c")
        self.assertEqual(lpr["value"], "PLATE-123")
        # No image/vector keys anywhere
        for it in items:
            self.assertNotIn("images", it)
            self.assertNotIn("vectors", it)
            self.assertNotIn("data_images", it)

    def test_list_items_respects_limit(self) -> None:
        out = _rec().list_recognizer_items(limit=2)
        self.assertEqual(out["count"], 2)
        self.assertTrue(out["truncated"])


if __name__ == "__main__":
    unittest.main()
