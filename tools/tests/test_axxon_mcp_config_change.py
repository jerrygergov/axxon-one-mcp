from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_config_change as module


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


class _SimilarUnit:
    def __init__(self, uid="hosts/Server/DeviceIpint.2", type="DeviceIpint"):
        self.uid = uid
        self.type = type
        self.display_name = "cam2"
        self.display_id = "2"


class _SimilarResp:
    def __init__(self, units=None, next_token=""):
        self.similar_units = units or []
        self.next_page_token = next_token


class _FactoryItem:
    def __init__(self, unit_type="DeviceIpint", status=1, ftype=""):
        self.requested = type("R", (), {"unit_type": unit_type})()
        self.status = status
        self.factory = type("F", (), {"type": ftype})()


class _FactoriesResp:
    def __init__(self, items=None):
        self.items = items or []


class _Unit:
    def __init__(self, uid="hosts/Server/DeviceIpint.1"):
        self.uid = uid
        self.type = ""
        self.properties = []


class _ChangeResp:
    def __init__(self, failed=None, added=None):
        self.failed = failed or []
        self.added = added or []


class _Property:
    def __init__(self):
        self.id = ""
        self.value_string = ""


class _UnitMsg:
    def __init__(self):
        self.uid = ""
        self.type = ""
        self._props: list = []

    @property
    def properties(self):
        return self._props


class _ChangeReq:
    def __init__(self):
        self._changed: list = []

    @property
    def changed(self):
        return _RepeatedUnit(self._changed)


class _RepeatedUnit:
    def __init__(self, backing):
        self._backing = backing

    def add(self):
        u = _MutUnit()
        self._backing.append(u)
        return u


class _MutUnit:
    def __init__(self):
        self.uid = ""
        self.type = ""
        self._props: list = []

    @property
    def properties(self):
        return _RepeatedProp(self._props)


class _RepeatedProp:
    def __init__(self, backing):
        self._backing = backing

    def add(self):
        p = _Property()
        self._backing.append(p)
        return p


class _SimReq:
    BY_UNIT_TYPE = 1

    def __init__(self, uid="", node_name="", page_size=0, page_token=""):
        self.uid = uid
        self.node_name = node_name
        self.page_size = page_size
        self.page_token = page_token
        self.search_mode = 0


class _FactReq:
    def __init__(self):
        self._factories: list = []

    @property
    def factories(self):
        return _RepeatedFact(self._factories)


class _RepeatedFact:
    def __init__(self, backing):
        self._backing = backing

    def add(self):
        f = type("F", (), {"unit_type": "", "parent_uid": "", "ignore_possible_limits": False})()
        self._backing.append(f)
        return f


class _Pb2:
    class ListSimilarUnitsRequest(_SimReq):
        BY_UNIT_TYPE = 1

    BatchGetFactoriesRequest = _FactReq
    ChangeConfigRequest = _ChangeReq


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def ListSimilarUnits(self, request, timeout=None):
        self._rec.append(("ListSimilarUnits", request.uid))
        return _SimilarResp(units=[_SimilarUnit()], next_token="tok")

    def BatchGetFactories(self, request, timeout=None):
        self._rec.append(("BatchGetFactories", list(request.factories._backing)))
        return _FactoriesResp(items=[_FactoryItem()])

    def ChangeConfig(self, request, timeout=None):
        self._rec.append(("ChangeConfig", request.changed._backing[0].uid))
        return _ChangeResp(failed=[], added=[])

    def ChangeConfigStream(self, request, timeout=None):
        self._rec.append(("ChangeConfigStream", request.changed._backing[0].uid))
        return iter([_ChangeResp(failed=[], added=[])])


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _Pb2()


def _inst(**overrides):
    inst = module.AxxonMcpConfigChange(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.config_change_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_list_similar_units_ok(self) -> None:
        out = _inst().list_similar_units(uid="hosts/Server/DeviceIpint.1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["unit_count"], 1)
        self.assertEqual(out["next_page_token"], "tok")

    def test_list_similar_units_empty_uid_no_wire(self) -> None:
        inst = _inst()
        out = inst.list_similar_units(uid="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_batch_get_factories_ok(self) -> None:
        out = _inst().batch_get_factories(unit_types=["DeviceIpint"], parent_uid="hosts/Server")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["items"][0]["status"], 1)

    def test_batch_get_factories_empty_no_wire(self) -> None:
        inst = _inst()
        out = inst.batch_get_factories(unit_types=[])
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.change_unit_property(uid="u", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_unit_property(uid="u", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_missing_fields_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_unit_property(uid="", unit_type="DeviceIpint", property_id="display_name", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_stream_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.change_unit_property_stream(uid="u", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_change_unit_property_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_unit_property(uid="hosts/Server/DeviceIpint.1", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["failed"], [])
        self.assertEqual(inst.client.calls[0][0], "ChangeConfig")

    def test_change_unit_property_stream_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_unit_property_stream(uid="hosts/Server/DeviceIpint.1", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(inst.client.calls[0][0], "ChangeConfigStream")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.change_unit_property(uid="u", unit_type="DeviceIpint", property_id="display_name", value_string="x", confirmation=module.CONFIG_CHANGE_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
