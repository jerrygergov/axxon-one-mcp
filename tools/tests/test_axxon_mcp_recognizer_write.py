from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_recognizer_write as module


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


class _Resp:
    def __init__(self, failed_lists=None, failed_items=None):
        self.failed_lists = failed_lists or []
        self.failed_items = failed_items or []


class _FakeList:
    """Stand-in for pb2.List supporting the fields the module sets."""

    def __init__(self, **kw):
        self.id = kw.get("id", "")
        self.name = kw.get("name", "")
        self.description = kw.get("description", "")
        self.score = kw.get("score", 0.0)
        self.type = kw.get("type", 0)
        self.item_ids = list(kw.get("item_ids", []))


class _FakeRemovedItemIds:
    def __init__(self, removed_item_ids=None):
        self.removed_item_ids = list(removed_item_ids or [])


class _FakeItem:
    def __init__(self, **kw):
        self.id = kw.get("id", "")
        self.type = kw.get("type", 0)
        self.data_string = kw.get("data_string", "")
        self._has_images = "data_images" in kw

    def HasField(self, field):
        if field == "data_images":
            return self._has_images
        if field == "data_string":
            return bool(self.data_string)
        raise ValueError(field)


class _FakeChangeItemsRequest:
    def __init__(self, **kw):
        self.status = None
        self.added_item = kw.get("added_item")
        self.removed_item = kw.get("removed_item")


class _FakeChangeListsRequest:
    def __init__(self, **kw):
        self.added_lists = list(kw.get("added_lists", []))
        self.changed_lists = list(kw.get("changed_lists", []))
        self.removed_list_ids = list(kw.get("removed_list_ids", []))


class _FakeListIds:
    def __init__(self, ids=None):
        self.ids = list(ids or [])


class _FakeChangeListsStreamRequest:
    ListIds = _FakeListIds

    def __init__(self, **kw):
        self.status = kw.get("status")
        self.added_list = kw.get("added_list")
        self.changed_list = kw.get("changed_list")
        self.removed_lists = kw.get("removed_lists")


class _FakeClearRequest:
    def __init__(self, **kw):
        self.node_name = kw.get("node_name", "")


class _FakePb2:
    """Faithful-enough stand-in for RealtimeRecognizer_pb2 (no proto compile)."""

    ELT_Any, ELT_Face, ELT_LPR, ELT_Food = 0, 1, 2, 3
    DT_ImageFace, DT_ImagesFood, DT_Plate, DT_Vector = 0, 1, 2, 3
    EPS_SEQUENTIAL, EPS_LAST = 0, 1

    List = _FakeList
    Item = _FakeItem
    RemovedItemIds = _FakeRemovedItemIds
    ChangeItemsRequest = _FakeChangeItemsRequest
    ChangeListsRequest = _FakeChangeListsRequest
    ChangeListsStreamRequest = _FakeChangeListsStreamRequest
    ClearRequest = _FakeClearRequest


class _FakeStub:
    """Records ChangeLists/ChangeItems/Clear calls; returns canned responses."""

    def __init__(self, recorder, failed_lists=None, failed_items=None):
        self._rec = recorder
        self._failed_lists = failed_lists or []
        self._failed_items = failed_items or []

    def ChangeLists(self, request, timeout=None):
        self._rec.append(("ChangeLists", request, timeout))
        return _Resp(failed_lists=self._failed_lists)

    def ChangeItems(self, request_iter, timeout=None):
        packets = list(request_iter)
        self._rec.append(("ChangeItems", packets, timeout))
        # Server returns an empty response stream on success.
        return iter(())

    def ChangeListsStream(self, request_iter, timeout=None):
        packets = list(request_iter)
        self._rec.append(("ChangeListsStream", packets, timeout))
        return iter((_Resp(failed_lists=self._failed_lists),))

    def Clear(self, request, timeout=None):
        self._rec.append(("Clear", request, timeout))
        return object()


class FakeRecogClient:
    """Network-free client; uses a faithful fake pb2 for message shaping."""

    def __init__(self, config, failed_lists=None, failed_items=None):
        self.config = config
        self.calls: list = []
        self._pb2 = _FakePb2()
        self._failed_lists = failed_lists or []
        self._failed_items = failed_items or []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "RealtimeRecognizerService"
        return _FakeStub(self.calls, self._failed_lists, self._failed_items)

    def import_module(self, name):
        return self._pb2


def _writer(failed_lists=None, failed_items=None, **overrides):
    inst = module.AxxonMcpRecognizerWrite(
        client_factory=lambda config: FakeRecogClient(config, failed_lists, failed_items),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.recognizer_write_connect_axxon_profile("env")
    return inst


class GatingTests(unittest.TestCase):
    def test_change_lists_disabled_without_approval(self) -> None:
        inst = _writer(enabled=False)
        out = inst.recognizer_change_lists(added=[{"name": "x", "type": "lpr"}], confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_change_lists_rejects_bad_confirmation(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists(added=[{"name": "x", "type": "lpr"}], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_change_items_disabled_without_approval(self) -> None:
        inst = _writer(enabled=False)
        out = inst.recognizer_change_items(list_id="L", added=[{"data_string": "A1"}], confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")

    def test_clear_disabled_without_approval(self) -> None:
        inst = _writer(enabled=False)
        out = inst.recognizer_clear(confirmation=module.WRITE_CONFIRMATION, clear_ack=module.CLEAR_ACK)
        self.assertEqual(out["status"], "disabled")


class ChangeListsTests(unittest.TestCase):
    def test_added_changed_removed_shaped(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists(
            added=[{"id": "a1", "name": "new", "type": "lpr", "score": 0.9, "item_ids": ["i1"]}],
            changed=[{"id": "c1", "name": "ren", "type": "face"}],
            removed_ids=["r1", "r2"],
            confirmation=module.WRITE_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed_lists"], [])
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "ChangeLists")
        self.assertEqual([l.id for l in req.added_lists], ["a1"])
        self.assertEqual(req.added_lists[0].name, "new")
        self.assertEqual(req.added_lists[0].type, inst.client._pb2.ELT_LPR)
        self.assertAlmostEqual(req.added_lists[0].score, 0.9)
        self.assertEqual(list(req.added_lists[0].item_ids), ["i1"])
        self.assertEqual([l.id for l in req.changed_lists], ["c1"])
        self.assertEqual(req.changed_lists[0].type, inst.client._pb2.ELT_Face)
        self.assertEqual(list(req.removed_list_ids), ["r1", "r2"])

    def test_failed_lists_passthrough(self) -> None:
        inst = _writer(enabled=True, failed_lists=["bad"])
        out = inst.recognizer_change_lists(removed_ids=["bad"], confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed_lists"], ["bad"])

    def test_empty_payload_errors(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists(confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class ChangeItemsTests(unittest.TestCase):
    def test_add_and_remove_packets_with_eps_last(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_items(
            list_id="L",
            added=[{"data_string": "A123BC"}, {"data_string": "B456CD"}],
            removed_item_ids=["old1"],
            confirmation=module.WRITE_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        (name, packets, _), = inst.client.calls
        self.assertEqual(name, "ChangeItems")
        pb2 = inst.client._pb2
        # 2 adds + 1 remove = 3 packets; last carries EPS_LAST
        self.assertEqual(len(packets), 3)
        self.assertEqual(packets[-1].status, pb2.EPS_LAST)
        self.assertEqual(packets[0].added_item.data_string, "A123BC")
        self.assertEqual(packets[0].added_item.type, pb2.DT_Plate)
        self.assertEqual(list(packets[2].removed_item.removed_item_ids), ["old1"])

    def test_no_image_or_vector_bytes_in_any_request(self) -> None:
        inst = _writer(enabled=True)
        inst.recognizer_change_items(list_id="L", added=[{"data_string": "A1"}], confirmation=module.WRITE_CONFIRMATION)
        (_, packets, _), = inst.client.calls
        for p in packets:
            self.assertFalse(p.added_item.HasField("data_images"))
            self.assertEqual(p.added_item.data_string, "A1")

    def test_empty_payload_errors(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_items(list_id="L", confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class ClearTests(unittest.TestCase):
    def test_clear_requires_second_ack(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_clear(confirmation=module.WRITE_CONFIRMATION, clear_ack="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_clear_requires_primary_confirmation(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_clear(confirmation="WRONG", clear_ack=module.CLEAR_ACK)
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_clear_fires_with_both_tokens(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_clear(node_name="Server", confirmation=module.WRITE_CONFIRMATION, clear_ack=module.CLEAR_ACK)
        self.assertEqual(out["status"], "cleared")
        self.assertEqual(out["node_name"], "Server")
        (name, req, _), = inst.client.calls
        self.assertEqual(name, "Clear")
        self.assertEqual(req.node_name, "Server")


class ChangeListsStreamTests(unittest.TestCase):
    def test_disabled_without_approval(self) -> None:
        inst = _writer(enabled=False)
        out = inst.recognizer_change_lists_stream(added=[{"name": "x", "type": "lpr"}], confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_rejects_bad_confirmation(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists_stream(added=[{"name": "x", "type": "lpr"}], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_no_edit_errors_without_wire_call(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists_stream(confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_packet_sequence_and_last_status(self) -> None:
        inst = _writer(enabled=True)
        out = inst.recognizer_change_lists_stream(
            added=[{"id": "a1", "name": "new", "type": "lpr"}],
            changed=[{"id": "c1", "name": "ren", "type": "face"}],
            removed_ids=["r1", "r2"],
            confirmation=module.WRITE_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed_lists"], [])
        (name, packets, _), = inst.client.calls
        self.assertEqual(name, "ChangeListsStream")
        # add + change + one removed_lists packet
        self.assertEqual(len(packets), 3)
        self.assertEqual(packets[0].added_list.id, "a1")
        self.assertEqual(packets[0].added_list.type, inst.client._pb2.ELT_LPR)
        self.assertEqual(packets[1].changed_list.id, "c1")
        self.assertEqual(list(packets[2].removed_lists.ids), ["r1", "r2"])
        # EPS_LAST only on the final packet
        self.assertNotEqual(packets[0].status, inst.client._pb2.EPS_LAST)
        self.assertNotEqual(packets[1].status, inst.client._pb2.EPS_LAST)
        self.assertEqual(packets[2].status, inst.client._pb2.EPS_LAST)

    def test_failed_lists_passthrough(self) -> None:
        inst = _writer(enabled=True, failed_lists=["bad"])
        out = inst.recognizer_change_lists_stream(removed_ids=["bad"], confirmation=module.WRITE_CONFIRMATION)
        self.assertEqual(out["failed_lists"], ["bad"])


if __name__ == "__main__":
    unittest.main()
