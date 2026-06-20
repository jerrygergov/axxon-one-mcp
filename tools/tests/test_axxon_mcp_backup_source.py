from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_backup_source as module

_SECRET = "BACKUP-SOURCE-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _BackupTimeInterval:
    def __init__(self, beginTime=0, endTime=0):
        self.beginTime = beginTime
        self.endTime = endTime


class _BundleBackupRequest:
    def __init__(self, access_points=None, intervals=None, report_timeout_sec=0):
        self.access_points = list(access_points or [])
        self.intervals = list(intervals or [])
        self.report_timeout_sec = report_timeout_sec


class _MakeBackupRequest:
    def __init__(self, access_point="", intervals=None):
        self.access_point = access_point
        self.intervals = list(intervals or [])


class _CancelBackupRequest:
    def __init__(self, access_point="", task_id=""):
        self.access_point = access_point
        self.task_id = task_id


class _BundleResponse:
    def __init__(self, remainder_ms=0, status=0):
        self.remainder_ms = remainder_ms
        self.status = status


class _MakeResponse:
    task_id = "task-1"
    worker_id = "worker-1"


class _CancelResponse:
    pass


class _Pb2:
    BackupTimeInterval = _BackupTimeInterval
    BundleBackupRequest = _BundleBackupRequest
    MakeBackupRequest = _MakeBackupRequest
    CancelBackupRequest = _CancelBackupRequest


class _Stub:
    def __init__(self, rec, bundle_count=3):
        self._rec = rec
        self._bundle_count = bundle_count

    def BundleBackup(self, request, timeout=None):
        self._rec.append(("BundleBackup", list(request.access_points), [(i.beginTime, i.endTime) for i in request.intervals], request.report_timeout_sec))
        for index in range(self._bundle_count):
            yield _BundleResponse(remainder_ms=100 - index, status=0 if index < self._bundle_count - 1 else 1)

    def MakeBackup(self, request, timeout=None):
        self._rec.append(("MakeBackup", request.access_point, [(i.beginTime, i.endTime) for i in request.intervals]))
        return _MakeResponse()

    def CancelBackup(self, request, timeout=None):
        self._rec.append(("CancelBackup", request.access_point, request.task_id))
        return _CancelResponse()


class FakeClient:
    def __init__(self, config, bundle_count=3):
        self.config = config
        self.calls: list = []
        self._bundle_count = bundle_count

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._bundle_count)

    def import_module(self, name):
        return _Pb2()


def _inst(bundle_count=3, enabled=False):
    inst = module.AxxonMcpBackupSource(
        client_factory=lambda config: FakeClient(config, bundle_count),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.backup_source_connect_axxon_profile("env")
    return inst


class BackupSourceTests(unittest.TestCase):
    def test_connect_reports_gate(self) -> None:
        out = _inst(enabled=True).backup_source_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read+backup-control")
        self.assertTrue(out["enabled"])
        self.assertNotIn(_SECRET, str(out))

    def test_bundle_backup_is_bounded(self) -> None:
        inst = _inst(bundle_count=5)
        out = inst.bundle_backup(["ap-1"], [{"begin_time": 10, "end_time": 20}], report_timeout_sec=1, max_items=2)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "bundle_backup")
        self.assertEqual(out["items_seen"], 2)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["stop_reason"], "item_cap")
        self.assertEqual(out["items"][0]["status"], "BUSY")
        call = inst.client.calls[0]
        self.assertEqual(call, ("BundleBackup", ["ap-1"], [(10, 20)], 1))

    def test_make_backup_requires_gate(self) -> None:
        inst = _inst(enabled=False)
        out = inst.make_backup("ap-1", [{"begin_time": 10, "end_time": 20}], module.BACKUP_SOURCE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.BACKUP_SOURCE_APPROVE_ENV)
        self.assertFalse(any(call[0] == "MakeBackup" for call in inst.client.calls))

    def test_make_backup_dispatches_when_confirmed(self) -> None:
        inst = _inst(enabled=True)
        out = inst.make_backup("ap-1", [{"begin_time": 10, "end_time": 20}], module.BACKUP_SOURCE_CONFIRMATION)
        self.assertEqual(out["status"], "started")
        self.assertEqual(out["task_id"], "task-1")
        self.assertEqual(out["worker_id"], "worker-1")
        self.assertIn(("MakeBackup", "ap-1", [(10, 20)]), inst.client.calls)

    def test_cancel_backup_dispatches_when_confirmed(self) -> None:
        inst = _inst(enabled=True)
        out = inst.cancel_backup("ap-1", "task-1", module.BACKUP_SOURCE_CONFIRMATION)
        self.assertEqual(out["status"], "cancelled")
        self.assertIn(("CancelBackup", "ap-1", "task-1"), inst.client.calls)

    def test_tool_names_exported(self) -> None:
        self.assertIn("bundle_backup", module.BACKUP_SOURCE_TOOL_NAMES)
        self.assertIn("make_backup", module.BACKUP_SOURCE_TOOL_NAMES)
        self.assertIn("cancel_backup", module.BACKUP_SOURCE_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
