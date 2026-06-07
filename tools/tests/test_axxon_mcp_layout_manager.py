from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_layout_manager as module


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


class _Meta:
    def __init__(self, layout_id="L1", etag="E1"):
        self.layout_id = layout_id
        self.etag = etag


class _Body:
    def __init__(self, display_name="orig"):
        self.display_name = display_name

    def CopyFrom(self, other):
        self.display_name = other.display_name


class _LayoutFull:
    def __init__(self, layout_id="L1", etag="E1", name="orig"):
        self.meta = _Meta(layout_id, etag)
        self.body = _Body(name)


class _ListResp:
    def __init__(self):
        self.items = [_LayoutFull("L1", "E1", "Fire")]


class _BatchResp:
    def __init__(self, items, not_found):
        self.items = items
        self.not_found_items = not_found


class _Locator:
    def __init__(self):
        self.layout_id = ""
        self.etag = ""


class _BatchReq:
    def __init__(self):
        self._items: list = []

    @property
    def items(self):
        return _Rep(self._items, _Locator)


class _OnViewEntry:
    def __init__(self):
        self.layout_id = ""
        self.layout_display_name = ""


class _OnViewReq:
    def __init__(self):
        self._layouts: list = []

    @property
    def layouts(self):
        return _Rep(self._layouts, _OnViewEntry)


class _Tagged:
    def __init__(self):
        self.etag = ""
        self.body = _Body()


class _UpdateReq:
    def __init__(self):
        self._modified: list = []

    @property
    def modified(self):
        return _Rep(self._modified, _Tagged)


class _UpdateResp:
    created_layouts: list = []


class _ListReq:
    def __init__(self, view=0):
        self.view = view


class _Rep:
    def __init__(self, backing, factory):
        self._backing = backing
        self._factory = factory

    def add(self):
        obj = self._factory()
        self._backing.append(obj)
        return obj


class _Pb2:
    VIEW_MODE_FULL = 1
    ListLayoutsRequest = _ListReq
    BatchGetLayoutsRequest = _BatchReq
    LayoutsOnViewRequest = _OnViewReq
    UpdateRequest = _UpdateReq


class _Stub:
    def __init__(self, rec):
        self._rec = rec

    def ListLayouts(self, request, timeout=None):
        self._rec.append(("ListLayouts",))
        return _ListResp()

    def BatchGetLayouts(self, request, timeout=None):
        loc = request._items[0]
        self._rec.append(("BatchGetLayouts", loc.layout_id, loc.etag))
        if loc.layout_id == "bogus":
            return _BatchResp([], ["bogus"])
        return _BatchResp([_LayoutFull(loc.layout_id, "E1", "Fire")], [])

    def LayoutsOnView(self, request, timeout=None):
        self._rec.append(("LayoutsOnView", request._layouts[0].layout_id))
        return object()

    def Update(self, request, timeout=None):
        self._rec.append(("Update", request._modified[0].body.display_name, request._modified[0].etag))
        return _UpdateResp()


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
    inst = module.AxxonMcpLayoutManager(
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
    )
    for key, value in overrides.items():
        setattr(inst, key, value)
    inst.layout_manager_connect_axxon_profile("env")
    return inst


class ReadTests(unittest.TestCase):
    def test_batch_get_layouts_ok(self) -> None:
        out = _inst().batch_get_layouts(layout_id="L1", etag="")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["item_count"], 1)
        self.assertEqual(out["items"][0]["display_name"], "Fire")

    def test_batch_get_layouts_not_found(self) -> None:
        out = _inst().batch_get_layouts(layout_id="bogus", etag="")
        self.assertEqual(out["not_found"], ["bogus"])

    def test_batch_get_empty_id_no_wire(self) -> None:
        inst = _inst()
        out = inst.batch_get_layouts(layout_id="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])

    def test_layouts_on_view_ok(self) -> None:
        inst = _inst()
        out = inst.layouts_on_view(layout_id="L1", display_name="Fire")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(inst.client.calls[0][0], "LayoutsOnView")

    def test_layouts_on_view_empty_id_no_wire(self) -> None:
        inst = _inst()
        out = inst.layouts_on_view(layout_id="")
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class GateTests(unittest.TestCase):
    def test_disabled_when_env_off(self) -> None:
        inst = _inst(enabled=False)
        out = inst.update_layout_name(layout_id="L1", display_name="x", confirmation=module.LAYOUT_MANAGER_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(inst.client.calls, [])

    def test_gap_on_bad_token(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_layout_name(layout_id="L1", display_name="x", confirmation="nope")
        self.assertEqual(out["status"], "gap")
        self.assertEqual(inst.client.calls, [])

    def test_error_on_empty_id_no_wire(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_layout_name(layout_id="", display_name="x", confirmation=module.LAYOUT_MANAGER_CONFIRMATION)
        self.assertEqual(out["status"], "error")
        self.assertEqual(inst.client.calls, [])


class WriteTests(unittest.TestCase):
    def test_update_applied_uses_live_etag(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_layout_name(layout_id="L1", display_name="new", confirmation=module.LAYOUT_MANAGER_CONFIRMATION)
        self.assertEqual(out["status"], "applied")
        names = [c[0] for c in inst.client.calls]
        self.assertEqual(names, ["ListLayouts", "Update"])
        update_call = inst.client.calls[1]
        self.assertEqual(update_call[1], "new")
        self.assertEqual(update_call[2], "E1")

    def test_no_config_secret_leak(self) -> None:
        inst = _inst(enabled=True)
        out = inst.update_layout_name(layout_id="L1", display_name="x", confirmation=module.LAYOUT_MANAGER_CONFIRMATION)
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(out))


if __name__ == "__main__":
    unittest.main()
