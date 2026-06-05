from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_discovery as module


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


class _Empty:
    pass


class _EmptyPb:
    def Empty(self):
        return _Empty()


class _StreamCall:
    """A fake server-streaming response that supports cancel()."""

    def __init__(self, pages):
        self._pages = pages
        self.cancelled = False

    def __iter__(self):
        return iter(self._pages)

    def cancel(self):
        self.cancelled = True


class _Stub:
    def __init__(self, client):
        self._c = client

    def Discover(self, req, timeout=None):
        self._c.discover_called = True
        return _Empty()

    def GetDiscoveryProgress(self, req, timeout=None):
        call = _StreamCall(self._c.progress_pages)
        self._c.last_stream = call
        return call


def _dev(mac, ip, vendor="Acme", model="cam"):
    return {"driver": "Generic", "vendor": vendor, "model": model, "mac_address": mac,
            "ip_address": ip, "ip_port": 80, "firmware_version": "1.0",
            "categories": ["IP_DEVICE"], "support_mode": "FULL_SUPPORT"}


class FakeDiscoveryClient:
    def __init__(self, config: FakeConfig, pages):
        self.config = config
        self.progress_pages = pages
        self.discover_called = False
        self.last_stream = None

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto, svc):
        assert svc == "DiscoveryService"
        return _Stub(self)

    def import_module(self, name):
        return _EmptyPb()

    def message_to_dict(self, message):
        return message


def _disc(pages):
    inst = module.AxxonMcpDiscovery(
        client_factory=lambda config: FakeDiscoveryClient(config, pages),
        config_factory=lambda: FakeConfig(),
    )
    inst.discovery_connect_axxon_profile("env")
    return inst


class DiscoveryTests(unittest.TestCase):
    def test_discover_aggregates_and_dedupes(self) -> None:
        pages = [
            {"state": "PROGRESS_STATE_RUNNING", "promille": 500,
             "device_description": [_dev("AA", "1.1.1.1"), _dev("BB", "1.1.1.2")]},
            {"state": "PROGRESS_STATE_FINISHED", "promille": 1000,
             "device_description": [_dev("AA", "1.1.1.1"), _dev("CC", "1.1.1.3")]},
        ]
        out = _disc(pages).discover_devices()
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["discover_started"])
        self.assertEqual(out["count"], 3)  # AA, BB, CC (AA de-duped)
        macs = {d["mac_address"] for d in out["devices"]}
        self.assertEqual(macs, {"AA", "BB", "CC"})
        self.assertEqual(out["state"], "PROGRESS_STATE_FINISHED")
        self.assertEqual(out["promille"], 1000)

    def test_device_summary_shape(self) -> None:
        pages = [{"state": "PROGRESS_STATE_FINISHED", "promille": 1000,
                  "device_description": [_dev("AA", "1.1.1.1", vendor="Hik", model="X")]}]
        d = _disc(pages).discover_devices()["devices"][0]
        for key in ("driver", "vendor", "model", "mac_address", "ip_address",
                    "ip_port", "firmware_version", "categories", "support_mode"):
            self.assertIn(key, d)
        self.assertEqual(d["vendor"], "Hik")

    def test_device_cap_enforced_and_stream_cancelled(self) -> None:
        pages = [{"state": "PROGRESS_STATE_RUNNING", "promille": 100,
                  "device_description": [_dev(str(i), f"1.1.1.{i}") for i in range(10)]}]
        inst = _disc(pages)
        out = inst.discover_devices(max_devices=4)
        self.assertEqual(out["count"], 4)
        self.assertEqual(out["caps"]["max_devices"], 4)
        self.assertTrue(inst.client.last_stream.cancelled)

    def test_caps_reported(self) -> None:
        out = _disc([{"state": "PROGRESS_STATE_FINISHED", "promille": 1000, "device_description": []}]).discover_devices(max_seconds=9)
        self.assertEqual(out["caps"]["max_seconds"], 9)
        self.assertEqual(out["count"], 0)


if __name__ == "__main__":
    unittest.main()
