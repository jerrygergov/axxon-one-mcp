from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_event_taxonomy as module

_SECRET = "EVTAX-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _FieldDescriptor:
    def __init__(self, id="event_type", name="Event type", type="string"):
        self.id = id
        self.name = name
        self.type = type


class _EventDescriptor:
    def __init__(self, fields=None):
        self.fields = fields if fields is not None else [_FieldDescriptor()]


class _TagsResponse:
    def __init__(self, fields=None):
        self.tags = _EventDescriptor(fields)


class _GetTagsRequest:
    def __init__(self):
        self.condition = None


class _Pb2:
    GetEventGroupingTagsRequest = _GetTagsRequest


class _Stub:
    def __init__(self, rec, response=None):
        self._rec = rec
        self._response = response

    def GetEventGroupingTags(self, request, timeout=None):
        self._rec.append(("GetEventGroupingTags",))
        return self._response if self._response is not None else _TagsResponse()


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
    inst = module.AxxonMcpEventTaxonomy(
        client_factory=lambda config: FakeClient(config, response),
        config_factory=lambda: FakeConfig(),
    )
    inst.event_taxonomy_connect_axxon_profile("env")
    return inst


class EventTaxonomyTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().event_taxonomy_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_get_event_grouping_tags_ok(self) -> None:
        out = _inst().get_event_grouping_tags()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "get_event_grouping_tags")
        self.assertEqual(out["count"], 1)
        field = out["fields"][0]
        self.assertEqual(field["id"], "event_type")
        self.assertEqual(field["name"], "Event type")
        self.assertEqual(field["type"], "string")

    def test_empty_tags(self) -> None:
        out = _inst(response=_TagsResponse(fields=[])).get_event_grouping_tags()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 0)

    def test_no_secret_leak(self) -> None:
        out = _inst().get_event_grouping_tags()
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("get_event_grouping_tags", module.EVENT_TAXONOMY_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
