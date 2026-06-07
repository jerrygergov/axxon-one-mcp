from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_acfa_vmda_control as module


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


class _Prop:
    def __init__(self, id="", type="", value_string="", **kw):
        self.id = id
        self.type = type
        self.value_string = value_string


class _Action:
    def __init__(self, id="", name="", input=None):
        self.id = id
        self.name = name
        self.input = input or []


class _UnitAction:
    def __init__(self, uid="", actions=None):
        self.uid = uid
        self.actions = actions or []


class _ActionsResp:
    def __init__(self, items, more_data=False):
        self.items = items
        self.more_data = more_data


class _PerformResp:
    def __init__(self, error_message="", properties=None):
        self.error_message = error_message
        self.properties = properties or []


class _CleanupResp:
    def __init__(self, result=True):
        self.result = result


class _Unit:
    def __init__(self, uid=""):
        self.uid = uid


class _ListReq:
    def __init__(self, items=None, portion_size=0):
        self.items = items or []
        self.portion_size = portion_size
    Unit = _Unit


class _PerformReq:
    def __init__(self, uid="", id=""):
        self.uid = uid
        self.id = id
        self.properties = []


class _CleanupReq:
    def __init__(self, access_point="", cs_IDs=None):
        self.access_point = access_point
        self.cs_IDs = cs_IDs


class _CS:
    def __init__(self, camera_ID="", schema_ID=""):
        self.camera_ID = camera_ID
        self.schema_ID = schema_ID


class _AcfaPb2:
    PropertyDescriptor = _Prop

    class ListUnitsActionsRequest(_ListReq):
        Unit = _Unit

    PerformActionRequest = _PerformReq


class _VmdaPb2:
    CameraAndSchemaIDs = _CS
    CleanupRequest = _CleanupReq


class _AcfaStub:
    def __init__(self, rec):
        self._rec = rec

    def ListUnitsActions(self, request, timeout=None):
        self._rec.append(("ListUnitsActions", [u.uid for u in request.items]))
        return iter([_ActionsResp([_UnitAction("u-1", [_Action("ARM", "Arm"), _Action("DISARM", "Disarm")])])])

    def PerformAction(self, request, timeout=None):
        self._rec.append(("PerformAction", request.uid, request.id, [(p.id, p.value_string) for p in request.properties]))
        if request.id == "FAIL":
            return _PerformResp(error_message="device refused")
        return _PerformResp(error_message="", properties=[_Prop(id="out", value_string="ok")])


class _VmdaStub:
    def __init__(self, rec):
        self._rec = rec

    def Cleanup(self, request, timeout=None):
        self._rec.append(("Cleanup", request.access_point, request.cs_IDs.camera_ID, request.cs_IDs.schema_ID))
        return _CleanupResp(result=True)


class FakeControlClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        if service_name == "AcfaService":
            return _AcfaStub(self.calls)
        return _VmdaStub(self.calls)

    def import_module(self, name):
        return _AcfaPb2() if name.endswith("AcfaService_pb2") else _VmdaPb2()

    def load_inventory(self):
        return {"components": [{"access_point": "hosts/Server/VMDA_DB.0/Database"}]}


def _inst(**overrides):
    inst = module.AxxonMcpAcfaVmdaControl(
        client_factory=lambda config: FakeControlClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.control_connect_axxon_profile("env")
    return inst


class ListActionsTests(unittest.TestCase):
    def test_list_unit_actions_shape(self) -> None:
        out = _inst().list_unit_actions(uids=["hosts/Server/ACFA.2/EMULATOR_LOOP.17"])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["units"][0]["uid"], "u-1")
        self.assertEqual(out["units"][0]["actions"][0]["id"], "ARM")

    def test_list_unit_actions_empty_is_error_no_wire(self) -> None:
        inst = _inst()
        out = inst.list_unit_actions(uids=[])
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class PerformActionTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.perform_unit_action(uid="u-1", action_id="ARM", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.perform_unit_action(uid="u-1", action_id="ARM", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_missing_args_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.perform_unit_action(uid="", action_id="ARM", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_applied_records_action_and_props(self) -> None:
        inst = _inst(enabled=True)
        out = inst.perform_unit_action(uid="u-1", action_id="ARM", properties=[{"id": "priority", "value": "5"}], confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["error_message"], "")
        call = inst.client.calls[0]
        self.assertEqual(call, ("PerformAction", "u-1", "ARM", [("priority", "5")]))

    def test_action_error_when_device_refuses(self) -> None:
        inst = _inst(enabled=True)
        out = inst.perform_unit_action(uid="u-1", action_id="FAIL", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "action-error")
        self.assertEqual(out["error_message"], "device refused")


class VmdaCleanupTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.vmda_cleanup(camera_id="DeviceIpint.1/SourceEndpoint.video:0:0", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_missing_camera_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.vmda_cleanup(camera_id="", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_applied_discovers_db_and_strips_prefix(self) -> None:
        inst = _inst(enabled=True)
        out = inst.vmda_cleanup(camera_id="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", confirmation=module.CONTROL_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertTrue(out["result"])
        self.assertEqual(out["database"], "hosts/Server/VMDA_DB.0/Database")
        self.assertEqual(out["camera_id"], "DeviceIpint.1/SourceEndpoint.video:0:0")
        call = inst.client.calls[0]
        self.assertEqual(call[0], "Cleanup")
        self.assertEqual(call[2], "DeviceIpint.1/SourceEndpoint.video:0:0")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.vmda_cleanup(camera_id="DeviceIpint.1", confirmation=module.CONTROL_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
