from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_shared_kv as module

_SECRET = "SKV-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _Record:
    def __init__(self, key="codex-k", revision="r1", value=b"hello"):
        self.key = key
        self.revision = revision
        self.value = value


class _RecordInfo:
    def __init__(self, key="codex-k", revision="r2"):
        self.key = key
        self.revision = revision


class _ListResponse:
    def __init__(self, items=None):
        self.items = items if items is not None else [_Record()]


class _CommitResponse:
    def __init__(self, error_code=0, updated=None):
        self.error_code = error_code
        self.updated = updated if updated is not None else [_RecordInfo()]


class _StreamChunk:
    def __init__(self, key="codex-k", total=100, index=0, data=b"x" * 10):
        self.info = _RecordInfo(key=key)
        self.total_size_bytes = total
        self.chunk_index = index
        self.chunk_data = data


class _ESharedKVRecordView:
    ESHKV_FULL = 0
    ESHKV_STRIPPED = 1
    _by_name = {"ESHKV_FULL": 0, "ESHKV_STRIPPED": 1}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _CommitErrorCode:
    _by_num = {0: "EOK", 1: "EConflict"}

    @classmethod
    def Name(cls, number):
        return cls._by_num[number]


class _CommitResponseType:
    EErrorCode = _CommitErrorCode


class _RepeatedRecords(list):
    def add(self, **kwargs):
        item = _Record(**{"key": "", "revision": "", "value": b"", **kwargs})
        self.append(item)
        return item


class _RepeatedInfos(list):
    def add(self, **kwargs):
        item = _RecordInfo(**{"key": "", "revision": "", **kwargs})
        self.append(item)
        return item


class _ListRecordsRequest:
    def __init__(self, prefix="", view=0):
        self.prefix = prefix
        self.view = view


class _BatchGetRecordsRequest:
    def __init__(self, prefix="", view=0):
        self.prefix = prefix
        self.view = view
        self.items = _RepeatedInfos()


class _GetRecordsStreamRequest:
    def __init__(self, prefix="", view=0):
        self.prefix = prefix
        self.view = view
        self.items = _RepeatedInfos()


class _SharedKVCommitRequest:
    def __init__(self, prefix=""):
        self.prefix = prefix
        self.set = _RepeatedRecords()
        self.removed = _RepeatedInfos()


class _Pb2:
    ESharedKVRecordView = _ESharedKVRecordView
    SharedKVCommitResponse = _CommitResponseType
    ListRecordsRequest = _ListRecordsRequest
    BatchGetRecordsRequest = _BatchGetRecordsRequest
    GetRecordsStreamRequest = _GetRecordsStreamRequest
    SharedKVCommitRequest = _SharedKVCommitRequest


class _Stub:
    def __init__(self, rec, list_resp=None, commit_resp=None, stream_count=2):
        self._rec = rec
        self._list = list_resp
        self._commit = commit_resp
        self._stream_count = stream_count

    def ListRecords(self, request, timeout=None):
        self._rec.append(("ListRecords", request.prefix))
        return self._list if self._list is not None else _ListResponse()

    def BatchGetRecords(self, request, timeout=None):
        self._rec.append(("BatchGetRecords", request.prefix, list(request.items)))
        return self._list if self._list is not None else _ListResponse()

    def GetRecordsStream(self, request, timeout=None):
        self._rec.append(("GetRecordsStream", request.prefix))
        for i in range(self._stream_count):
            yield _StreamChunk(index=i)

    def Commit(self, request, timeout=None):
        self._rec.append(("Commit", request.prefix, list(request.set), list(request.removed)))
        return self._commit if self._commit is not None else _CommitResponse()


class FakeClient:
    def __init__(self, config, list_resp=None, commit_resp=None, stream_count=2):
        self.config = config
        self.calls: list = []
        self._list = list_resp
        self._commit = commit_resp
        self._stream_count = stream_count

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._list, self._commit, self._stream_count)

    def import_module(self, name):
        return _Pb2()


def _inst(enabled=True, list_resp=None, commit_resp=None, stream_count=2):
    inst = module.AxxonMcpSharedKv(
        client_factory=lambda config: FakeClient(config, list_resp, commit_resp, stream_count),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.shared_kv_connect_axxon_profile("env")
    return inst


class ConnectTests(unittest.TestCase):
    def test_connect_reports_read_write_mode(self) -> None:
        out = _inst().shared_kv_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read+write")
        self.assertEqual(out["approval_env"], module.SHARED_KV_APPROVE_ENV)


class ReadTests(unittest.TestCase):
    def test_list_records_ok(self) -> None:
        out = _inst().list_records(prefix="codex-")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["records"][0]["key"], "codex-k")
        self.assertEqual(out["records"][0]["value_text"], "hello")

    def test_list_records_invalid_view_gap(self) -> None:
        out = _inst().list_records(view="NOPE")
        self.assertEqual(out["status"], "gap")
        self.assertIn("NOPE", out["message"])

    def test_get_records_ok(self) -> None:
        out = _inst().get_records(keys=["codex-k"], prefix="codex-")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["records"][0]["key"], "codex-k")

    def test_get_records_stream_caps(self) -> None:
        out = _inst(stream_count=100).get_records_stream(prefix="codex-", max_chunks=3)
        self.assertEqual(out["chunks_seen"], 3)
        self.assertTrue(out["truncated"])

    def test_binary_value_summarized_not_decoded(self) -> None:
        rec = _Record(value=b"\xff\xfe\x00binary")
        out = _inst(list_resp=_ListResponse(items=[rec])).list_records(prefix="codex-")
        record = out["records"][0]
        self.assertIsNone(record["value_text"])
        self.assertEqual(record["value_size_bytes"], len(b"\xff\xfe\x00binary"))


class CommitGateTests(unittest.TestCase):
    def test_commit_disabled_without_approve(self) -> None:
        out = _inst(enabled=False).commit_record(prefix="codex-", set_records=[{"key": "codex-k", "value": "v"}], confirmation=module.SHARED_KV_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.SHARED_KV_APPROVE_ENV)

    def test_commit_refuses_without_token(self) -> None:
        out = _inst().commit_record(prefix="codex-", set_records=[{"key": "codex-k", "value": "v"}], confirmation="")
        self.assertEqual(out["status"], "gap")
        self.assertIn(module.SHARED_KV_CONFIRMATION, out["message"])

    def test_commit_refuses_wrong_token(self) -> None:
        out = _inst().commit_record(prefix="codex-", set_records=[{"key": "codex-k", "value": "v"}], confirmation="WRONG")
        self.assertEqual(out["status"], "gap")

    def test_commit_applies_with_token_and_approve(self) -> None:
        inst = _inst()
        out = inst.commit_record(prefix="codex-", set_records=[{"key": "codex-k", "value": "v", "revision": "r1"}], confirmation=module.SHARED_KV_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["error_code"], "EOK")
        self.assertEqual(out["updated"][0]["key"], "codex-k")
        call = [c for c in inst.client.calls if c[0] == "Commit"][0]
        self.assertEqual(call[1], "codex-")
        self.assertEqual(call[2][0].key, "codex-k")

    def test_commit_conflict_surfaces(self) -> None:
        inst = _inst(commit_resp=_CommitResponse(error_code=1))
        out = inst.commit_record(prefix="codex-", removed=[{"key": "codex-k", "revision": "r2"}], confirmation=module.SHARED_KV_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["error_code"], "EConflict")

    def test_commit_removed_only_for_rollback(self) -> None:
        inst = _inst()
        out = inst.commit_record(prefix="codex-", removed=[{"key": "codex-k", "revision": "r2"}], confirmation=module.SHARED_KV_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        call = [c for c in inst.client.calls if c[0] == "Commit"][0]
        self.assertEqual(call[3][0].key, "codex-k")


class CommonTests(unittest.TestCase):
    def test_no_config_secret_leak(self) -> None:
        out = _inst().list_records(prefix="codex-")
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        for name in ("list_records", "get_records", "get_records_stream", "commit_record"):
            self.assertIn(name, module.SHARED_KV_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
