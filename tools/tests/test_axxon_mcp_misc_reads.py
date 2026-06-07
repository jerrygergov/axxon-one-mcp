from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_misc_reads as module


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


class _AcquireResp:
    def __init__(self):
        self.status = 0
        self.properties = []


class _AcquireReq:
    def __init__(self, uid=""):
        self.uid = uid


class _ProbeResp:
    class EProbeResultCode:
        @staticmethod
        def Name(code):
            return {0: "OK", 1: "NOT_A_VOLUME"}.get(code, str(code))

    def __init__(self):
        self.status_code = 1
        self.error_details = "not implemented"


class _ProbeReq:
    def __init__(self, volume_type="", node_name=""):
        self.volume_type = volume_type
        self.node_name = node_name
        self.connection_params = {}


class _PingReq:
    def __init__(self, timeoutMs=0):
        self.timeoutMs = timeoutMs


class _SettingsInfo:
    def __init__(self, context="", revision="rev-1"):
        self.context = context
        self.revision = revision


class _Settings:
    def __init__(self):
        self.info = _SettingsInfo()
        self.values = {}


class _GetResp:
    def __init__(self):
        self.settings = _Settings()
        self.settings.values = {"k": "v"}
        self.settings.info.revision = "rev-1"


class _SaveResp:
    class _Updated:
        revision = "rev-2"

    def __init__(self):
        self.result = 1
        self.updated = self._Updated()


class _GetReq:
    def __init__(self, context="", scope=0):
        self.context = context
        self.scope = scope


class _SaveReq:
    def __init__(self, settings=None, scope=0):
        self.settings = settings
        self.scope = scope


class _RemoveReq:
    def __init__(self, to_remove=None, scope=0):
        self.to_remove = to_remove
        self.scope = scope


class _SettingsPb2:
    class EModificationResult:
        @staticmethod
        def Name(code):
            return {1: "MODIFICATION_RESULT_OK"}.get(code, str(code))

    GetSettingsRequest = _GetReq
    SaveSettingsRequest = _SaveReq
    RemoveSettingsRequest = _RemoveReq


class _SettingsMsgPb2:
    Settings = _Settings


class _InfoPb2:
    SettingsInfo = _SettingsInfo


class _DynPb2:
    AcquireDynamicParametersRequest = _AcquireReq
    AcquireDeviceAdditionalDataRequest = _AcquireReq


class _VolPb2:
    ProbeVolumeRequest = _ProbeReq
    ProbeVolumeResponse = _ProbeResp


class _NotifyPb2:
    PingRequest = _PingReq


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def AcquireDynamicParameters(self, request, timeout=None):
        self._rec.append(("AcquireDynamicParameters", request.uid))
        return _AcquireResp()

    def AcquireDeviceAdditionalData(self, request, timeout=None):
        self._rec.append(("AcquireDeviceAdditionalData", request.uid))
        return _AcquireResp()

    def ProbeVolume(self, request, timeout=None):
        self._rec.append(("ProbeVolume", request.volume_type))
        return _ProbeResp()

    def Ping(self, request, timeout=None):
        self._rec.append(("Ping",))
        return iter([object()])

    def GetSettings(self, request, timeout=None):
        self._rec.append(("GetSettings", request.context))
        return _GetResp()

    def SaveSettings(self, request, timeout=None):
        self._rec.append(("SaveSettings",))
        return _SaveResp()

    def RemoveSettings(self, request, timeout=None):
        self._rec.append(("RemoveSettings", request.to_remove.context))
        return object()


_PB2_BY_NAME = {
    module.DYNPARAM_PB2: _DynPb2,
    module.VOLUME_PB2: _VolPb2,
    module.NOTIFY_PB2: _NotifyPb2,
    module.SETTINGS_PB2: _SettingsPb2,
    module.SETTINGS_MSG_PB2: _SettingsMsgPb2,
    module.SETTINGS_INFO_PB2: _InfoPb2,
}


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _PB2_BY_NAME[name]()


def _inst(**overrides):
    inst = module.AxxonMcpMiscReads(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.misc_reads_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_acquire_dynamic_parameters_ok(self) -> None:
        out = _inst().acquire_dynamic_parameters(uid="hosts/Server/DeviceIpint.1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["result"], 0)

    def test_acquire_empty_uid_no_wire(self) -> None:
        inst = _inst()
        out = inst.acquire_device_additional_data(uid="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_probe_volume_ok(self) -> None:
        out = _inst().probe_volume(volume_type="LOCAL", connection_params={"path": "/x"})
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["status_name"], "NOT_A_VOLUME")

    def test_probe_volume_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.probe_volume(volume_type="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_ping_node_ok(self) -> None:
        out = _inst().ping_node(timeout_ms=500)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["responses"], 1)

    def test_get_generic_settings_ok(self) -> None:
        out = _inst().get_generic_settings(context="ctx-guid")
        self.assertEqual(out["value_count"], 1)
        self.assertEqual(out["revision"], "rev-1")

    def test_get_generic_settings_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.get_generic_settings(context="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_save_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.save_generic_settings(context="ctx", values={"k": "v"}, confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_save_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.save_generic_settings(context="ctx", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_save_error_on_empty_context_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.save_generic_settings(context="", confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_remove_error_on_missing_revision_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.remove_generic_settings(context="ctx", revision="", confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_save_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.save_generic_settings(context="ctx", values={"k": "v"}, confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["result_name"], "MODIFICATION_RESULT_OK")
        self.assertEqual(inst.client.calls[0][0], "SaveSettings")

    def test_remove_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.remove_generic_settings(context="ctx", revision="rev-1", confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(inst.client.calls[0][0], "RemoveSettings")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.save_generic_settings(context="ctx", values={"k": "v"}, confirmation=module.MISC_WRITE_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
