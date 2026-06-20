from __future__ import annotations

from pathlib import Path
import sys
import unittest
import unittest.mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_config_revisions as module

_SECRET = "CFGREV-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)
_BACKUP_BYTES = b"SECRET-BACKUP-BYTES-SHOULD-NOT-LEAK-" + (b"Z" * 256)


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


class _Revision:
    def __init__(self, number=5, hash="abc123"):
        self.number = number
        self.hash = hash


class _Info:
    def __init__(self, number=5, timestamp="2026-06-09T00:00:00Z", is_current=True, comment="latest"):
        self.revision = _Revision(number=number)
        self.timestamp = timestamp
        self.is_current = is_current
        self.tags = ""
        self.parents = []
        self.comment = comment


class _InfoList:
    def __init__(self, infos=None):
        self.info = infos if infos is not None else [_Info()]


class _RevisionInfoResponse:
    def __init__(self, info_map=None):
        # protobuf map<string, InfoList> behaves like a dict
        self.info = info_map if info_map is not None else {"Server": _InfoList()}


class _EConfigType:
    LOCAL_CONFIG = 0
    SHARED_CONFIG = 1
    _by_name = {"LOCAL_CONFIG": 0, "SHARED_CONFIG": 1}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _EBackupType:
    LOCAL = 0
    SHARED = 1
    LICENSE = 2
    TICKETS = 3
    _by_name = {"LOCAL": 0, "SHARED": 1, "LICENSE": 2, "TICKETS": 3}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]


class _GetRevisionInfoRequest:
    def __init__(self, type=0, nodes=None):
        self.type = type
        self.nodes = list(nodes or [])


class _SetRevisionRequest:
    def __init__(self, type=0, node="", revision=None, comment=""):
        self.type = type
        self.node = node
        self.revision = revision
        self.comment = comment


class _CollectBackupRequest:
    EBackupType = _EBackupType

    def __init__(self, type=None, node="", chunk_size_kb=0):
        self.type = list(type or [])
        self.node = node
        self.chunk_size_kb = chunk_size_kb


class _BackupChunk:
    def __init__(self, total=1024, index=0, data=b""):
        self.total_size_bytes = total
        self.chunk_index = index
        self.chunk_data = data


class _InitialRestoreData:
    def __init__(self, type=None, node="", total_size_bytes=0):
        self.type = list(type or [])
        self.node = node
        self.total_size_bytes = total_size_bytes


class _RestoreBackupRequest:
    class ERestoreType:
        LOCAL = 0
        CLEAN_LOCAL = 1
        SHARED = 2
        CLEAN_SHARED = 3
        LICENSE = 4
        TICKETS = 5
        CLONE = 6
        _by_name = {
            "LOCAL": 0,
            "CLEAN_LOCAL": 1,
            "SHARED": 2,
            "CLEAN_SHARED": 3,
            "LICENSE": 4,
            "TICKETS": 5,
            "CLONE": 6,
        }

        @classmethod
        def Value(cls, name):
            return cls._by_name[name]

    InitialData = _InitialRestoreData

    def __init__(self, initial_data=None, chunk_data=b""):
        self.initial_data = initial_data
        self.chunk_data = chunk_data


class _EmptyResponse:
    pass


class _Pb2:
    EConfigType = _EConfigType
    Revision = _Revision
    GetRevisionInfoRequest = _GetRevisionInfoRequest
    SetRevisionRequest = _SetRevisionRequest
    CollectBackupRequest = _CollectBackupRequest
    RestoreBackupRequest = _RestoreBackupRequest


class _Stub:
    def __init__(self, rec, rev_response=None, chunk_count=3):
        self._rec = rec
        self._rev_response = rev_response
        self._chunk_count = chunk_count

    def GetRevisionInfo(self, request, timeout=None):
        self._rec.append(("GetRevisionInfo", request.type, list(request.nodes)))
        return self._rev_response if self._rev_response is not None else _RevisionInfoResponse()

    def CollectBackup(self, request, timeout=None):
        self._rec.append(("CollectBackup", list(request.type), request.node))
        for i in range(self._chunk_count):
            yield _BackupChunk(total=self._chunk_count * len(_BACKUP_BYTES), index=i, data=_BACKUP_BYTES)

    def SetRevision(self, request, timeout=None):
        self._rec.append(("SetRevision", request.type, request.node, request.revision.number, request.revision.hash, request.comment))
        return _EmptyResponse()

    def RestoreBackup(self, requests, timeout=None):
        summarized = []
        for request in requests:
            if request.initial_data is not None:
                summarized.append(("initial", list(request.initial_data.type), request.initial_data.node, request.initial_data.total_size_bytes))
            else:
                summarized.append(("chunk", len(request.chunk_data)))
        self._rec.append(("RestoreBackup", summarized))
        return _EmptyResponse()


class FakeClient:
    def __init__(self, config, rev_response=None, chunk_count=3):
        self.config = config
        self.calls: list = []
        self._rev_response = rev_response
        self._chunk_count = chunk_count

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._rev_response, self._chunk_count)

    def import_module(self, name):
        return _Pb2()


def _inst(rev_response=None, chunk_count=3, enabled=False):
    inst = module.AxxonMcpConfigRevisions(
        client_factory=lambda config: FakeClient(config, rev_response, chunk_count),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.config_revisions_connect_axxon_profile("env")
    return inst


class RevisionInfoTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().config_revisions_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_get_revision_info_ok(self) -> None:
        out = _inst().get_revision_info()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "get_revision_info")
        self.assertIn("Server", out["nodes"])
        rev = out["nodes"]["Server"][0]
        self.assertEqual(rev["number"], 5)
        self.assertTrue(rev["is_current"])

    def test_invalid_config_type_returns_gap(self) -> None:
        out = _inst().get_revision_info(config_type="BOGUS")
        self.assertEqual(out["status"], "gap")
        self.assertIn("BOGUS", out["message"])

    def test_no_secret_leak_revision(self) -> None:
        out = _inst().get_revision_info()
        self.assertNotIn(_SECRET, str(out))


class CollectBackupTests(unittest.TestCase):
    def test_probe_ok_reports_bytes_no_blob(self) -> None:
        out = _inst(chunk_count=3).collect_backup_probe(types=["LOCAL"])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "collect_backup_probe")
        self.assertEqual(out["chunks_seen"], 3)
        self.assertEqual(out["bytes_seen"], 3 * len(_BACKUP_BYTES))
        self.assertFalse(out["truncated"])
        # backup blob bytes must never appear in output
        self.assertNotIn("SECRET-BACKUP-BYTES", str(out))

    def test_chunk_cap_truncates(self) -> None:
        out = _inst(chunk_count=100).collect_backup_probe(types=["LOCAL"], max_chunks=2)
        self.assertEqual(out["chunks_seen"], 2)
        self.assertTrue(out["truncated"])

    def test_byte_cap_truncates(self) -> None:
        out = _inst(chunk_count=100).collect_backup_probe(types=["LOCAL"], max_bytes=len(_BACKUP_BYTES) + 1)
        self.assertTrue(out["truncated"])
        self.assertLessEqual(out["chunks_seen"], 2)

    def test_invalid_backup_type_returns_gap(self) -> None:
        out = _inst().collect_backup_probe(types=["NONSENSE"])
        self.assertEqual(out["status"], "gap")
        self.assertIn("NONSENSE", out["message"])

    def test_passes_types_to_request(self) -> None:
        inst = _inst()
        inst.collect_backup_probe(types=["LOCAL", "SHARED"], node="Server")
        call = [c for c in inst.client.calls if c[0] == "CollectBackup"][0]
        self.assertEqual(call[1], [0, 1])
        self.assertEqual(call[2], "Server")

    def test_chunk_cap_stop_reason(self) -> None:
        out = _inst(chunk_count=100).collect_backup_probe(types=["LOCAL"], max_chunks=2)
        self.assertEqual(out["stop_reason"], "chunk_cap")

    def test_byte_cap_stop_reason(self) -> None:
        out = _inst(chunk_count=100).collect_backup_probe(types=["LOCAL"], max_bytes=len(_BACKUP_BYTES) + 1)
        self.assertEqual(out["stop_reason"], "byte_cap")

    def test_total_size_bytes_reported(self) -> None:
        out = _inst(chunk_count=3).collect_backup_probe(types=["LOCAL"])
        self.assertEqual(out["total_size_bytes"], 3 * len(_BACKUP_BYTES))

    def test_chunk_cap_clamps_to_max(self) -> None:
        over = module.MAX_BACKUP_CHUNKS + 10
        out = _inst(chunk_count=over).collect_backup_probe(types=["LOCAL"], max_chunks=over)
        self.assertLessEqual(out["chunks_seen"], module.MAX_BACKUP_CHUNKS)
        self.assertTrue(out["truncated"])

    def test_time_cap_truncates(self) -> None:
        # Chunk/byte caps set high so only the time cap can trip. monotonic() returns the deadline
        # base first, then a value past the deadline on the per-iteration check.
        times = iter([0.0, 100.0, 100.0, 100.0])
        with unittest.mock.patch.object(module.time, "monotonic", lambda: next(times)):
            out = _inst(chunk_count=100).collect_backup_probe(
                types=["LOCAL"], max_chunks=module.MAX_BACKUP_CHUNKS, max_bytes=module.MAX_BACKUP_BYTES, timeout=1.0
            )
        self.assertTrue(out["truncated"])
        self.assertEqual(out["stop_reason"], "time_cap")

    def test_no_secret_leak_backup(self) -> None:
        out = _inst().collect_backup_probe(types=["LOCAL"])
        self.assertNotIn(_SECRET, str(out))


class ExportTests(unittest.TestCase):
    def test_tool_names_exported(self) -> None:
        self.assertIn("get_revision_info", module.CONFIG_REVISIONS_TOOL_NAMES)
        self.assertIn("collect_backup_probe", module.CONFIG_REVISIONS_TOOL_NAMES)
        self.assertIn("set_revision", module.CONFIG_REVISIONS_TOOL_NAMES)
        self.assertIn("restore_backup", module.CONFIG_REVISIONS_TOOL_NAMES)


class ConfigMaintenanceMutationTests(unittest.TestCase):
    def test_connect_reports_gate(self) -> None:
        out = _inst(enabled=True).config_revisions_connect_axxon_profile("env")
        self.assertEqual(out["mode"], "read+maintenance")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["approval_env"], module.CONFIG_REVISIONS_APPROVE_ENV)

    def test_set_revision_requires_approval(self) -> None:
        inst = _inst(enabled=False)
        out = inst.set_revision("LOCAL_CONFIG", "Server", 5, "abc", "rollback", module.SET_REVISION_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.CONFIG_REVISIONS_APPROVE_ENV)
        self.assertFalse(any(call[0] == "SetRevision" for call in inst.client.calls))

    def test_set_revision_requires_confirmation(self) -> None:
        inst = _inst(enabled=True)
        out = inst.set_revision("LOCAL_CONFIG", "Server", 5, "abc", "rollback", "wrong")
        self.assertEqual(out["status"], "gap")
        self.assertIn(module.SET_REVISION_CONFIRMATION, out["message"])
        self.assertFalse(any(call[0] == "SetRevision" for call in inst.client.calls))

    def test_set_revision_dispatches_when_confirmed(self) -> None:
        inst = _inst(enabled=True)
        out = inst.set_revision("SHARED_CONFIG", "Server", 7, "hash-7", "codex rollback", module.SET_REVISION_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["tool"], "set_revision")
        call = [c for c in inst.client.calls if c[0] == "SetRevision"][0]
        self.assertEqual(call, ("SetRevision", 1, "Server", 7, "hash-7", "codex rollback"))

    def test_restore_backup_requires_approval(self) -> None:
        inst = _inst(enabled=False)
        out = inst.restore_backup(["LOCAL"], "Server", backup_hex=_BACKUP_BYTES.hex(), confirmation=module.RESTORE_BACKUP_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.CONFIG_REVISIONS_APPROVE_ENV)
        self.assertFalse(any(call[0] == "RestoreBackup" for call in inst.client.calls))

    def test_restore_backup_sends_initial_and_chunks_without_returning_blob(self) -> None:
        inst = _inst(enabled=True)
        out = inst.restore_backup(
            ["LOCAL", "SHARED"],
            "Server",
            backup_hex=_BACKUP_BYTES.hex(),
            chunk_size_kb=1,
            max_bytes=len(_BACKUP_BYTES),
            confirmation=module.RESTORE_BACKUP_CONFIRMATION,
        )
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["tool"], "restore_backup")
        self.assertEqual(out["bytes_sent"], len(_BACKUP_BYTES))
        self.assertGreaterEqual(out["chunks_sent"], 1)
        self.assertNotIn("SECRET-BACKUP-BYTES", str(out))
        call = [c for c in inst.client.calls if c[0] == "RestoreBackup"][0]
        sent = call[1]
        self.assertEqual(sent[0], ("initial", [0, 2], "Server", len(_BACKUP_BYTES)))
        self.assertEqual(sum(item[1] for item in sent[1:]), len(_BACKUP_BYTES))


if __name__ == "__main__":
    unittest.main()
