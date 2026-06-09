from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_devices_catalog as module

_SECRET = "DEVCAT-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)
_CRED_SECRET = "DEVICE-DEFAULT-PASSWORD-SHOULD-NOT-LEAK"


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


class _UInt32Value:
    def __init__(self, value=80):
        self.value = value


class _ModelCredentials:
    login = "admin"
    password = _CRED_SECRET


class _ModelTraits:
    has_storage = True
    has_text_event_sources = False
    has_motion_detection = True
    video_channels_count = 1

    def __init__(self):
        self.default_credentials = _ModelCredentials()
        self.default_port = _UInt32Value(80)

    def HasField(self, name):
        return name in {"default_port", "traits"}


class _Device:
    def __init__(self, vendor="Axis", model="P1448"):
        self.vendor = vendor
        self.model = model
        self.firmware = ["1.0", "2.0"]
        self.categories = [1]
        self.traits = _ModelTraits()

    def HasField(self, name):
        return name == "traits"


class _EDeviceCategory:
    _by_name = {"DEVICE_CATEGORY_UNSPECIFIED": 0, "IP_DEVICE": 1, "IP_DEVICE_WITH_STORAGE": 2, "TEXT_EVENT_DEVICE": 3, "ACFA_DEVICE": 4}

    @classmethod
    def Value(cls, name):
        return cls._by_name[name]

    @classmethod
    def Name(cls, number):
        return {v: k for k, v in cls._by_name.items()}[number]


class _VendorsResponse:
    def __init__(self, vendors=None, next_page_token=""):
        self.vendors = vendors if vendors is not None else ["Axis", "Hikvision"]
        self.next_page_token = next_page_token


class _DevicesResponse:
    def __init__(self, devices=None, next_page_token=""):
        self.devices = devices if devices is not None else [_Device()]
        self.next_page_token = next_page_token


class _GetDeviceResponse:
    def __init__(self):
        self.device = _Device()

    def HasField(self, name):
        return name == "device"


class _ListVendorsRequest:
    def __init__(self, node_name="", category=0, filter="", page_size=0, page_token=""):
        self.node_name = node_name
        self.category = category
        self.filter = filter
        self.page_size = page_size
        self.page_token = page_token


class _ListDevicesRequest:
    def __init__(self, node_name="", category=0, vendor="", filter="", page_size=0, page_token=""):
        self.node_name = node_name
        self.category = category
        self.vendor = vendor
        self.filter = filter
        self.page_size = page_size
        self.page_token = page_token


class _GetDeviceRequest:
    def __init__(self, node_name="", vendor="", model=""):
        self.node_name = node_name
        self.vendor = vendor
        self.model = model


class _Pb2:
    EDeviceCategory = _EDeviceCategory
    ListVendorsRequest = _ListVendorsRequest
    ListDevicesRequest = _ListDevicesRequest
    GetDeviceRequest = _GetDeviceRequest


class _Stub:
    def __init__(self, rec, vendors=None, devices=None, stream_count=2):
        self._rec = rec
        self._vendors = vendors
        self._devices = devices
        self._stream_count = stream_count

    def ListVendors(self, request, timeout=None):
        self._rec.append(("ListVendors", request.category, request.filter))
        return self._vendors if self._vendors is not None else _VendorsResponse()

    def ListVendorsV2(self, request, timeout=None):
        self._rec.append(("ListVendorsV2",))
        for _ in range(self._stream_count):
            yield self._vendors if self._vendors is not None else _VendorsResponse(vendors=["Axis"])

    def ListDevices(self, request, timeout=None):
        self._rec.append(("ListDevices", request.category, request.vendor))
        return self._devices if self._devices is not None else _DevicesResponse()

    def ListDevicesV2(self, request, timeout=None):
        self._rec.append(("ListDevicesV2",))
        for _ in range(self._stream_count):
            yield self._devices if self._devices is not None else _DevicesResponse()

    def GetDevice(self, request, timeout=None):
        self._rec.append(("GetDevice", request.vendor, request.model))
        return _GetDeviceResponse()


class FakeClient:
    def __init__(self, config, vendors=None, devices=None, stream_count=2):
        self.config = config
        self.calls: list = []
        self._vendors = vendors
        self._devices = devices
        self._stream_count = stream_count

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._vendors, self._devices, self._stream_count)

    def import_module(self, name):
        return _Pb2()


def _inst(vendors=None, devices=None, stream_count=2):
    inst = module.AxxonMcpDevicesCatalog(
        client_factory=lambda config: FakeClient(config, vendors, devices, stream_count),
        config_factory=lambda: FakeConfig(),
    )
    inst.devices_catalog_connect_axxon_profile("env")
    return inst


class ListVendorsTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().devices_catalog_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_list_vendors_ok(self) -> None:
        out = _inst().list_vendors()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["vendors"], ["Axis", "Hikvision"])

    def test_list_vendors_category_filter(self) -> None:
        inst = _inst()
        inst.list_vendors(category="IP_DEVICE")
        _, cat, _ = inst.client.calls[0]
        self.assertEqual(cat, 1)

    def test_list_vendors_invalid_category_gap(self) -> None:
        out = _inst().list_vendors(category="NOPE")
        self.assertEqual(out["status"], "gap")
        self.assertIn("NOPE", out["message"])

    def test_list_vendors_v2_caps(self) -> None:
        out = _inst(stream_count=100).list_vendors_v2(max_pages=2)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["pages_seen"], 2)


class ListDevicesTests(unittest.TestCase):
    def test_list_devices_ok_summarizes_traits(self) -> None:
        out = _inst().list_devices(vendor="Axis")
        self.assertEqual(out["status"], "ok")
        device = out["devices"][0]
        self.assertEqual(device["vendor"], "Axis")
        self.assertEqual(device["model"], "P1448")
        self.assertEqual(device["categories"], ["IP_DEVICE"])
        self.assertTrue(device["traits"]["has_storage"])
        self.assertEqual(device["traits"]["default_port"], 80)

    def test_list_devices_never_leaks_credentials(self) -> None:
        out = _inst().list_devices(vendor="Axis")
        self.assertNotIn(_CRED_SECRET, str(out))
        self.assertNotIn("default_credentials", str(out))

    def test_list_devices_v2_caps(self) -> None:
        out = _inst(stream_count=100).list_devices_v2(max_pages=3)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["pages_seen"], 3)


class GetDeviceTests(unittest.TestCase):
    def test_get_device_ok(self) -> None:
        out = _inst().get_device(vendor="Axis", model="P1448")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["device"]["model"], "P1448")

    def test_get_device_requires_vendor_and_model(self) -> None:
        out = _inst().get_device(vendor="Axis", model="")
        self.assertEqual(out["status"], "gap")
        self.assertIn("model", out["message"])

    def test_get_device_never_leaks_credentials(self) -> None:
        out = _inst().get_device(vendor="Axis", model="P1448")
        self.assertNotIn(_CRED_SECRET, str(out))


class CommonTests(unittest.TestCase):
    def test_no_config_secret_leak(self) -> None:
        out = _inst().list_vendors()
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        for name in ("list_vendors", "list_vendors_v2", "list_devices", "list_devices_v2", "get_device"):
            self.assertIn(name, module.DEVICES_CATALOG_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
