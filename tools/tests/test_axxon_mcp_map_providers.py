from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_map_providers as module


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


class _StringValue:
    def __init__(self, value=""):
        self.value = value

    def CopyFrom(self, other):
        self.value = other.value


class _MapProvider:
    def __init__(self, id="", name="", etag=""):
        self.id = id
        self.name = name
        self.etag = etag
        self.api_key = _StringValue()
        self.copyright = _StringValue()
        self.map_types = {}


class _ConfigureReq:
    def __init__(self, removed=None):
        self.removed = list(removed or [])
        self.changed = []


class _GetReq:
    def __init__(self, id=""):
        self.id = id


class _ConfigureResp:
    def __init__(self, etags=None):
        self.etags = etags or {}


class _GetResp:
    def __init__(self, provider):
        self.map_provider = provider


class _MapsPb2:
    ConfigureMapProvidersRequest = _ConfigureReq
    GetMapProviderRequest = _GetReq


class _ProviderPb2:
    MapProvider = _MapProvider


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def ConfigureMapProviders(self, request, timeout=None):
        self._rec.append(("ConfigureMapProviders", [p.id for p in request.changed], list(request.removed)))
        return _ConfigureResp(etags={p.id: "etag-" + p.id for p in request.changed})

    def GetMapProvider(self, request, timeout=None):
        self._rec.append(("GetMapProvider", request.id))
        return _GetResp(_MapProvider(id=request.id, name="demo", etag="e1"))


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls)

    def import_module(self, name):
        return _ProviderPb2() if name.endswith("MapProvider_pb2") else _MapsPb2()


def _inst(**overrides):
    inst = module.AxxonMcpMapProviders(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.map_providers_connect_axxon_profile("env")
    return inst


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.configure_map_providers(changed=[{"id": "p1", "name": "x"}], confirmation=module.MAP_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.configure_map_providers(changed=[{"id": "p1", "name": "x"}], confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_empty_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.configure_map_providers(changed=[], removed=[], confirmation=module.MAP_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class ConfigureTests(unittest.TestCase):
    def test_create_applied_records_provider(self) -> None:
        inst = _inst(enabled=True)
        out = inst.configure_map_providers(changed=[{"id": "p1", "name": "Demo", "api_key": "k", "copyright": "c"}], confirmation=module.MAP_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["changed_ids"], ["P1"])
        self.assertEqual(out["etags"], {"P1": "etag-P1"})
        call = inst.client.calls[0]
        self.assertEqual(call, ("ConfigureMapProviders", ["P1"], []))

    def test_remove_applied(self) -> None:
        inst = _inst(enabled=True)
        out = inst.configure_map_providers(removed=["p9"], confirmation=module.MAP_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["removed_ids"], ["P9"])
        self.assertEqual(inst.client.calls[0], ("ConfigureMapProviders", [], ["P9"]))

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.configure_map_providers(removed=["p9"], confirmation=module.MAP_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


class GetTests(unittest.TestCase):
    def test_get_map_provider_shape(self) -> None:
        inst = _inst()
        out = inst.get_map_provider(provider_id="p1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["provider"]["id"], "P1")
        self.assertEqual(out["provider"]["name"], "demo")

    def test_get_missing_id_is_error_no_wire(self) -> None:
        inst = _inst()
        out = inst.get_map_provider(provider_id="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


if __name__ == "__main__":
    unittest.main()
