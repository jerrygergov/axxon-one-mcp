from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_settings as module


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


class _Dur:
    def __init__(self, seconds=0):
        self.seconds = seconds


class _SysLogs:
    def __init__(self, retention=0, cleanup=0):
        self.retention_period = _Dur(retention)
        self.cleanup_period = _Dur(cleanup)


class _Vmda:
    def __init__(self, retention=0):
        self.retention_period = _Dur(retention)


class _Settings:
    def __init__(self, retention=7776000, cleanup=43200, vmda=432000, etag="ETAG-A"):
        self.system_logs_settings = _SysLogs(retention, cleanup)
        self.vmda_storage_settings = _Vmda(vmda)
        self.etag = etag


class _BookmarkSettings:
    def __init__(self, mandatory_protection=False, max_duration=0, retention=0):
        self.mandatory_protection = mandatory_protection
        self.bookmark_max_duration = _Dur(max_duration)
        self.retention_period = _Dur(retention)


class _BookmarkResp:
    def __init__(self, settings=None, etag="BM-A"):
        self.settings = settings or _BookmarkSettings()
        self.etag = etag


class _GDPRSettings:
    PRIVACY_MASK_TYPE_UNSPECIFIED, MOSAIC, BLACK = 0, 1, 2

    def __init__(self, privacy_mask_type=0):
        self.privacy_mask_type = privacy_mask_type


class _GDPRResp:
    def __init__(self, settings=None, etag="GD-A"):
        self.settings = settings or _GDPRSettings()
        self.etag = etag


class _GetReq:
    def __init__(self, **kw):
        pass


class _UpdReq:
    def __init__(self, data_storage_settings=None, update_mask=None):
        self.data_storage_settings = data_storage_settings
        self.update_mask = update_mask


class _ReqEtag:
    def __init__(self, settings=None, mask=None, etag=""):
        self.settings = settings
        self.mask = mask
        self.etag = etag


class _UpdRespEtag:
    def __init__(self, etag="X"):
        self.etag = etag


class _DSPb2:
    GetDataStorageSettingsRequest = _GetReq
    UpdateDataStorageSettingsRequest = _UpdReq
    GetBookmarkSettingsRequest = _GetReq
    UpdateBookmarkSettingsRequest = _ReqEtag
    GetGDPRSettingsRequest = _GetReq
    UpdateGDPRSettingsRequest = _ReqEtag


class _BookmarkPb2:
    BookmarkSettings = _BookmarkSettings


class _GDPRPb2:
    GDPRSettings = _GDPRSettings


class _DataPb2:
    """DataStorageSettings_pb2 stand-in: settings builders the module uses."""

    DataStorageSettings = _Settings
    SystemLogsSettings = _SysLogs
    VmdaStorageSettings = _Vmda


class _FakeStub:
    def __init__(self, recorder, current, bookmark=None, gdpr=None):
        self._rec = recorder
        self._current = current
        self._bookmark = bookmark or _BookmarkResp()
        self._gdpr = gdpr or _GDPRResp()

    def GetDataStorageSettings(self, request, timeout=None):
        self._rec.append(("Get", request, timeout))
        return self._current

    def UpdateDataStorageSettings(self, request, timeout=None):
        self._rec.append(("Update", request, timeout))
        # echo back a fresh settings object (rotated etag) without mutating the
        # request the test will inspect.
        sent = request.data_storage_settings
        return _Settings(
            retention=sent.system_logs_settings.retention_period.seconds,
            cleanup=sent.system_logs_settings.cleanup_period.seconds,
            vmda=sent.vmda_storage_settings.retention_period.seconds,
            etag="ETAG-B",
        )

    def GetBookmarkSettings(self, request, timeout=None):
        self._rec.append(("GetBookmark", request, timeout))
        return self._bookmark

    def UpdateBookmarkSettings(self, request, timeout=None):
        self._rec.append(("UpdateBookmark", request, timeout))
        return _UpdRespEtag(etag="BM-B")

    def GetGDPRSettings(self, request, timeout=None):
        self._rec.append(("GetGDPR", request, timeout))
        return self._gdpr

    def UpdateGDPRSettings(self, request, timeout=None):
        self._rec.append(("UpdateGDPR", request, timeout))
        return _UpdRespEtag(etag="GD-B")


class FakeSettingsClient:
    def __init__(self, config, current=None):
        self.config = config
        self.calls: list = []
        self._current = current or _Settings()

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        assert service_name == "DomainSettingsService"
        return _FakeStub(self.calls, self._current)

    def import_module(self, name):
        if name.endswith("DataStorageSettings_pb2"):
            return _DataPb2()
        if name.endswith("BookmarkSettings_pb2"):
            return _BookmarkPb2()
        if name.endswith("GDPRSettings_pb2"):
            return _GDPRPb2()
        return _DSPb2()


def _settings(current=None, **overrides):
    inst = module.AxxonMcpSettings(
        client_factory=lambda config: FakeSettingsClient(config, current),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.settings_connect_axxon_profile("env")
    return inst


class GetTests(unittest.TestCase):
    def test_get_shape_seconds(self) -> None:
        inst = _settings()
        out = inst.get_data_storage_settings()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["system_logs"]["retention_period_s"], 7776000)
        self.assertEqual(out["system_logs"]["cleanup_period_s"], 43200)
        self.assertEqual(out["vmda"]["retention_period_s"], 432000)
        self.assertEqual(out["etag"], "ETAG-A")


class UpdateGatingTests(unittest.TestCase):
    def test_disabled_without_approval(self) -> None:
        inst = _settings(enabled=False)
        out = inst.update_data_storage_settings(system_logs_cleanup_s=60, confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_bad_token(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_data_storage_settings(system_logs_cleanup_s=60, confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_empty_payload_errors(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_data_storage_settings(confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class UpdateTests(unittest.TestCase):
    def test_masks_only_provided_fields_and_carries_etag(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_data_storage_settings(
            system_logs_cleanup_s=99, vmda_retention_s=111, confirmation=module.SETTINGS_CONFIRMATION
        )
        self.assertEqual(out["status"], "applied")
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["Get", "Update"])  # reads etag then updates
        upd = inst.client.calls[1][1]
        self.assertEqual(set(upd.update_mask.paths), {
            "system_logs_settings.cleanup_period",
            "vmda_storage_settings.retention_period",
        })
        self.assertEqual(upd.data_storage_settings.etag, "ETAG-A")  # carried from Get
        self.assertEqual(upd.data_storage_settings.system_logs_settings.cleanup_period.seconds, 99)
        self.assertEqual(upd.data_storage_settings.vmda_storage_settings.retention_period.seconds, 111)
        self.assertEqual(out["etag"], "ETAG-B")

    def test_single_field_mask(self) -> None:
        inst = _settings(enabled=True)
        inst.update_data_storage_settings(system_logs_retention_s=500, confirmation=module.SETTINGS_CONFIRMATION)
        upd = inst.client.calls[1][1]
        self.assertEqual(list(upd.update_mask.paths), ["system_logs_settings.retention_period"])


class BookmarkTests(unittest.TestCase):
    def test_get_shape(self) -> None:
        inst = _settings()
        out = inst.get_bookmark_settings()
        self.assertEqual(out["status"], "ok")
        self.assertIn("mandatory_protection", out)
        self.assertIn("bookmark_max_duration_s", out)
        self.assertIn("retention_period_s", out)
        self.assertEqual(out["etag"], "BM-A")

    def test_update_disabled_without_approval(self) -> None:
        inst = _settings(enabled=False)
        out = inst.update_bookmark_settings(mandatory_protection=True, confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_update_bad_token(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_bookmark_settings(mandatory_protection=True, confirmation="WRONG")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_update_empty_errors(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_bookmark_settings(confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_update_masks_and_request_etag(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_bookmark_settings(
            mandatory_protection=True, bookmark_max_duration_s=120, confirmation=module.SETTINGS_CONFIRMATION
        )
        self.assertEqual(out["status"], "applied")
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["GetBookmark", "UpdateBookmark"])
        upd = inst.client.calls[1][1]
        self.assertEqual(set(upd.mask.paths), {"mandatory_protection", "bookmark_max_duration"})
        self.assertEqual(upd.etag, "BM-A")  # request-level etag carried from get
        self.assertTrue(upd.settings.mandatory_protection)
        self.assertEqual(upd.settings.bookmark_max_duration.seconds, 120)
        self.assertEqual(out["etag"], "BM-B")


class GDPRTests(unittest.TestCase):
    def test_get_shape(self) -> None:
        inst = _settings()
        out = inst.get_gdpr_settings()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["privacy_mask_type"], "unspecified")
        self.assertEqual(out["etag"], "GD-A")

    def test_update_mask_name_mapping(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_gdpr_settings("black", confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        kinds = [c[0] for c in inst.client.calls]
        self.assertEqual(kinds, ["GetGDPR", "UpdateGDPR"])
        upd = inst.client.calls[1][1]
        self.assertEqual(list(upd.mask.paths), ["privacy_mask_type"])
        self.assertEqual(upd.settings.privacy_mask_type, _GDPRSettings.BLACK)
        self.assertEqual(upd.etag, "GD-A")

    def test_update_unknown_mask_errors(self) -> None:
        inst = _settings(enabled=True)
        out = inst.update_gdpr_settings("rainbow", confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_update_disabled_without_approval(self) -> None:
        inst = _settings(enabled=False)
        out = inst.update_gdpr_settings("mosaic", confirmation=module.SETTINGS_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])


if __name__ == "__main__":
    unittest.main()
