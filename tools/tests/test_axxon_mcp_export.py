from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_export as module


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


class _ArchiveSource:
    def __init__(self, origin: str = "", storages: list[str] | None = None, **kw):
        self.origin = origin
        self.storages = list(storages or [])
        self.kw = kw


class _ArchiveMode:
    Source = _ArchiveSource

    def __init__(self, sources: list[_ArchiveSource] | None = None, start_timestamp: str = "", **kw):
        self.sources = list(sources or [])
        self.start_timestamp = start_timestamp
        self.kw = kw


class _SnapshotType:
    JPEG = 1

    def __init__(self, format: int = 0, **kw):
        self.format = format
        self.kw = kw


class _CommonSetting:
    def __init__(self, file_name: str = "", comment: str = "", **kw):
        self.file_name = file_name
        self.comment = comment
        self.kw = kw


class _Options:
    def __init__(
        self,
        archive=None,
        snapshot=None,
        settings: list[_CommonSetting] | None = None,
        max_file_size: int = 0,
        store_result_by_export_agent: bool = True,
        **kw,
    ):
        self.archive = archive
        self.snapshot = snapshot
        self.settings = list(settings or [])
        self.max_file_size = max_file_size
        self.store_result_by_export_agent = store_result_by_export_agent
        self.kw = kw


class _ExportPb2:
    ArchiveMode = _ArchiveMode
    SnapshotType = _SnapshotType
    CommonSetting = _CommonSetting
    Options = _Options


class _StartSessionRequest:
    def __init__(self, session_options=None, **kw):
        self.session_options = session_options
        self.kw = kw


class _GetSessionStateRequest:
    def __init__(self, session_id: str = "", **kw):
        self.session_id = session_id
        self.kw = kw


class _StopSessionRequest(_GetSessionStateRequest):
    pass


class _DestroySessionRequest(_GetSessionStateRequest):
    pass


class _DownloadFileRequest:
    def __init__(
        self,
        session_id: str = "",
        file_path: str = "",
        chunk_size_kb: int = 0,
        start_from_chunk_index: int = 0,
        **kw,
    ):
        self.session_id = session_id
        self.file_path = file_path
        self.chunk_size_kb = chunk_size_kb
        self.start_from_chunk_index = start_from_chunk_index
        self.kw = kw


class _EState:
    @staticmethod
    def Name(code: int) -> str:
        return {0: "S_NONE", 1: "S_RUNNING", 2: "S_COMPLETED", 3: "S_REMOVED"}.get(int(code), str(code))


class _ServicePb2:
    StartSessionRequest = _StartSessionRequest
    GetSessionStateRequest = _GetSessionStateRequest
    StopSessionRequest = _StopSessionRequest
    DestroySessionRequest = _DestroySessionRequest
    DownloadFileRequest = _DownloadFileRequest
    EState = _EState


class _StartResp:
    def __init__(self, session_id: str):
        self.started_session_id = session_id


class _File:
    def __init__(self, path: str = "file-id-1", size: int = 6, mime_type: str = "image/jpeg"):
        self.path = path
        self.size = size
        self.min_timestamp = "2026-06-12T10:00:00Z"
        self.max_timestamp = "2026-06-12T10:00:01Z"
        self.mime_type = mime_type
        self.cloud_id = "cloud-id"
        self.timezone = 0


class _Result:
    def __init__(self, files: list[_File] | None = None, succeeded: bool = True):
        self.files = list(files or [_File()])
        self.succeeded = succeeded


class _State:
    def __init__(self, state: int = 2, result: _Result | None = None):
        self.state = state
        self.last_frame_timestamp = "2026-06-12T10:00:01Z"
        self.result = result or _Result()


class _StateResp:
    def __init__(self, state: _State | None = None):
        self.session_state = state or _State()


class _Chunk:
    def __init__(self, index: int, data: bytes):
        self.index = index
        self.data = data


class _Stub:
    def __init__(self, rec: list, *, fail_start: bool = False, fail_stop: bool = False):
        self._rec = rec
        self._fail_start = fail_start
        self._fail_stop = fail_stop

    def StartSession(self, request, timeout=None):
        self._rec.append(("StartSession", request, timeout))
        if self._fail_start:
            raise RuntimeError("start failed")
        return _StartResp(f"session-{sum(1 for call in self._rec if call[0] == 'StartSession')}")

    def GetSessionState(self, request, timeout=None):
        self._rec.append(("GetSessionState", request.session_id, timeout))
        return _StateResp()

    def StopSession(self, request, timeout=None):
        self._rec.append(("StopSession", request.session_id, timeout))
        if self._fail_stop:
            raise RuntimeError("stop failed")
        return _StateResp(_State(state=3))

    def DestroySession(self, request, timeout=None):
        self._rec.append(("DestroySession", request.session_id, timeout))
        return object()

    def DownloadFile(self, request, timeout=None):
        self._rec.append(("DownloadFile", request, timeout))
        return iter([_Chunk(0, b"ABC"), _Chunk(1, b"DEF"), _Chunk(2, b"GHI")])


class FakeClient:
    def __init__(self, config, *, fail_start: bool = False, fail_stop: bool = False):
        self.config = config
        self.calls: list = []
        self._fail_start = fail_start
        self._fail_stop = fail_stop

    def authenticate_grpc(self):
        self.calls.append(("authenticate_grpc",))

    def stub_from_proto(self, proto_path, service_name):
        self.calls.append(("stub_from_proto", proto_path, service_name))
        return _Stub(self.calls, fail_start=self._fail_start, fail_stop=self._fail_stop)

    def import_module(self, name):
        if name == module.EXPORT_PB2:
            return _ExportPb2
        if name == module.EXPORT_SERVICE_PB2:
            return _ServicePb2
        raise KeyError(name)


def _inst(**overrides):
    factory_kwargs = {
        "client_factory": lambda config: FakeClient(config),
        "config_factory": lambda: FakeConfig(),
        "enabled": False,
    }
    factory_kwargs.update(overrides)
    return module.AxxonMcpExport(**factory_kwargs)


def _start_owned(inst):
    inst.enabled = True
    return inst.export_start_snapshot(
        camera_access_point="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
        archive_access_point="hosts/Server/MultimediaStorage.1/MultimediaStorage",
        timestamp="2026-06-12T10:00:00Z",
        confirmation=module.EXPORT_CONFIRMATION,
    )


class ExportModuleTests(unittest.TestCase):
    def test_constants_and_tool_names_are_public(self) -> None:
        self.assertEqual(module.EXPORT_APPROVE_ENV, "AXXON_EXPORT_APPROVE")
        self.assertEqual(module.EXPORT_CONFIRMATION, "CONFIRM-export")
        self.assertEqual(
            module.EXPORT_TOOL_NAMES,
            (
                "export_connect_axxon_profile",
                "export_plan_snapshot",
                "export_start_snapshot",
                "export_status",
                "export_download",
                "export_stop",
                "export_destroy",
                "export_cleanup_owned",
            ),
        )

    def test_connect_is_env_only_lazy_and_redacts_secrets(self) -> None:
        created = []
        inst = _inst(client_factory=lambda config: created.append(config) or FakeClient(config))
        self.assertIsNone(inst.client)
        rejected = inst.export_connect_axxon_profile("prod")
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(created, [])

        out = inst.export_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read+export")
        self.assertEqual(out["approval_env"], module.EXPORT_APPROVE_ENV)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))
        self.assertEqual(len(created), 1)

    def test_plan_snapshot_validates_caps_and_does_not_touch_wire(self) -> None:
        inst = _inst()
        missing = inst.export_plan_snapshot(camera_access_point="", archive_access_point="archive", timestamp="ts")
        self.assertEqual(missing["status"], "error")

        out = inst.export_plan_snapshot(
            camera_access_point="camera",
            archive_access_point="archive",
            timestamp="2026-06-12T10:00:00Z",
            max_file_size=module.MAX_EXPORT_FILE_SIZE * 20,
            max_download_bytes=module.MAX_DOWNLOAD_BYTES * 20,
            max_chunks=module.MAX_DOWNLOAD_CHUNKS * 20,
            chunk_size_kb=module.MAX_CHUNK_SIZE_KB * 20,
            timeout_s=module.MAX_EXPORT_TIMEOUT_S * 20,
        )
        self.assertEqual(out["status"], "planned")
        self.assertEqual(out["confirmation"], module.EXPORT_CONFIRMATION)
        self.assertFalse(out["options"]["store_result_by_export_agent"])
        self.assertEqual(out["options"]["max_file_size"], module.MAX_EXPORT_FILE_SIZE)
        self.assertEqual(out["caps"]["max_download_bytes"], module.MAX_DOWNLOAD_BYTES)
        self.assertEqual(out["caps"]["max_chunks"], module.MAX_DOWNLOAD_CHUNKS)
        self.assertEqual(out["caps"]["chunk_size_kb"], module.MAX_CHUNK_SIZE_KB)
        self.assertEqual(out["caps"]["timeout_s"], module.MAX_EXPORT_TIMEOUT_S)
        self.assertIsNone(inst.client)

    def test_start_requires_approval_and_confirmation_before_wire(self) -> None:
        inst = _inst(enabled=False)
        denied = inst.export_start_snapshot("cam", "archive", "ts", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(denied["status"], "disabled")
        self.assertIsNone(inst.client)

        inst.enabled = True
        denied = inst.export_start_snapshot("cam", "archive", "ts", confirmation="wrong")
        self.assertEqual(denied["status"], "gap")
        self.assertIsNone(inst.client)

    def test_start_builds_snapshot_options_and_tracks_owned_session(self) -> None:
        inst = _inst(enabled=True)
        out = _start_owned(inst)
        self.assertEqual(out["status"], "started")
        self.assertEqual(out["session_id"], "session-1")
        self.assertIn("session-1", inst.owned_sessions)
        start_call = next(call for call in inst.client.calls if call[0] == "StartSession")
        options = start_call[1].session_options
        self.assertFalse(options.store_result_by_export_agent)
        self.assertEqual(options.archive.sources[0].origin, "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(options.archive.sources[0].storages, ["hosts/Server/MultimediaStorage.1/MultimediaStorage"])
        self.assertEqual(options.snapshot.format, _SnapshotType.JPEG)
        self.assertTrue(any(setting.file_name.startswith("codex-export-") for setting in options.settings))
        self.assertTrue(any("codex-owned" in setting.comment for setting in options.settings))
        self.assertNotIn("ABC", str(out))

    def test_status_is_owned_only_and_returns_bounded_metadata(self) -> None:
        inst = _inst(enabled=True)
        unknown = inst.export_status("external-session")
        self.assertEqual(unknown["status"], "refused")
        self.assertIsNone(inst.client)

        _start_owned(inst)
        out = inst.export_status("session-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["state"], "S_COMPLETED")
        self.assertEqual(out["file_count"], 1)
        self.assertEqual(out["files"][0]["file_path"], "file-id-1")
        self.assertEqual(out["files"][0]["size"], 6)
        self.assertEqual(out["files"][0]["mime_type"], "image/jpeg")
        self.assertNotIn("data", str(out).lower())

    def test_download_requires_gate_owned_caps_chunks_and_returns_no_raw_bytes(self) -> None:
        inst = _inst(enabled=True)
        _start_owned(inst)
        inst.enabled = False
        denied = inst.export_download("session-1", "file-id-1", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(denied["status"], "disabled")
        self.assertFalse(any(call[0] == "DownloadFile" for call in inst.client.calls))

        inst.enabled = True
        denied = inst.export_download("session-1", "file-id-1", confirmation="wrong")
        self.assertEqual(denied["status"], "gap")
        self.assertFalse(any(call[0] == "DownloadFile" for call in inst.client.calls))

        out = inst.export_download(
            "session-1",
            "file-id-1",
            confirmation=module.EXPORT_CONFIRMATION,
            max_bytes=5,
            max_chunks=10,
            chunk_size_kb=module.MAX_CHUNK_SIZE_KB * 10,
            save=False,
        )
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["bytes_seen"], 5)
        self.assertEqual(out["chunks_seen"], 2)
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["sha256"]), 64)
        self.assertNotIn("ABC", str(out))
        download_call = next(call for call in inst.client.calls if call[0] == "DownloadFile")
        self.assertEqual(download_call[1].chunk_size_kb, module.MAX_CHUNK_SIZE_KB)

    def test_download_saves_under_artifact_root_and_rejects_unsafe_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "exports"
            outside = Path(tmp) / "outside.bin"
            outside.write_bytes(b"outside")
            inst = _inst(enabled=True, artifact_root_factory=lambda: root)
            _start_owned(inst)
            out = inst.export_download(
                "session-1",
                "file-id-1",
                confirmation=module.EXPORT_CONFIRMATION,
                destination_name="clip.bin",
                max_bytes=6,
            )
            self.assertEqual(out["status"], "ok")
            saved_path = Path(out["saved_path"])
            self.assertEqual(saved_path.parent.resolve(), root.resolve())
            self.assertEqual(saved_path.read_bytes(), b"ABCDEF")

            for bad in ("/tmp/x.bin", "../x.bin", "nested/x.bin", r"nested\x.bin"):
                before = sum(1 for call in inst.client.calls if call[0] == "DownloadFile")
                denied = inst.export_download(
                    "session-1",
                    "file-id-1",
                    confirmation=module.EXPORT_CONFIRMATION,
                    destination_name=bad,
                )
                self.assertEqual(denied["status"], "error")
                after = sum(1 for call in inst.client.calls if call[0] == "DownloadFile")
                self.assertEqual(before, after)

            link = root / "link.bin"
            os.symlink(outside, link)
            denied = inst.export_download(
                "session-1",
                "file-id-1",
                confirmation=module.EXPORT_CONFIRMATION,
                destination_name="link.bin",
            )
            self.assertEqual(denied["status"], "error")

    def test_stop_and_destroy_require_gate_and_owned_session(self) -> None:
        inst = _inst(enabled=True)
        denied = inst.export_stop("external-session", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(denied["status"], "refused")
        self.assertIsNone(inst.client)

        _start_owned(inst)
        inst.enabled = False
        denied = inst.export_destroy("session-1", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(denied["status"], "disabled")
        self.assertIn("session-1", inst.owned_sessions)

        inst.enabled = True
        stopped = inst.export_stop("session-1", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(stopped["status"], "stopped")
        destroyed = inst.export_destroy("session-1", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(destroyed["status"], "destroyed")
        self.assertNotIn("session-1", inst.owned_sessions)
        again = inst.export_destroy("session-1", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(again["status"], "refused")

    def test_cleanup_owned_counts_and_removes_destroyed_sessions(self) -> None:
        inst = _inst(enabled=True)
        _start_owned(inst)
        _start_owned(inst)
        out = inst.export_cleanup_owned(confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["attempted"], 2)
        self.assertEqual(out["stopped"], 2)
        self.assertEqual(out["destroyed"], 2)
        self.assertEqual(out["failed"], 0)
        self.assertEqual(out["skipped"], 0)
        self.assertEqual(inst.owned_sessions, {})

    def test_failed_start_and_failed_cleanup_do_not_silently_drop_ownership(self) -> None:
        failing_start = _inst(
            enabled=True,
            client_factory=lambda config: FakeClient(config, fail_start=True),
        )
        out = failing_start.export_start_snapshot("cam", "archive", "ts", confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(failing_start.owned_sessions, {})

        failing_stop = _inst(
            enabled=True,
            client_factory=lambda config: FakeClient(config, fail_stop=True),
        )
        _start_owned(failing_stop)
        out = failing_stop.export_cleanup_owned(confirmation=module.EXPORT_CONFIRMATION)
        self.assertEqual(out["status"], "partial")
        self.assertEqual(out["attempted"], 1)
        self.assertEqual(out["failed"], 1)
        self.assertIn("session-1", failing_stop.owned_sessions)


if __name__ == "__main__":
    unittest.main()
