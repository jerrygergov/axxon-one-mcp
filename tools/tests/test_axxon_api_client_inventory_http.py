from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig

DOMAIN_SVC = "axxonsoft.bl.domain.DomainService"


def _cfg() -> AxxonClientConfig:
    return AxxonClientConfig(
        host="example.local",
        grpc_port=20109,
        http_port=80,
        http_url="http://example.local",
        username="fixture-admin",
        password="secret",
        tls_cn="Server",
        ca=Path("/tmp/ca.crt"),
        proto_dir=Path("/tmp"),
        stubs_dir=Path("/tmp"),
        timeout=5.0,
    )


class _HttpInventoryFake(AxxonApiClient):
    """Fake whose http_grpc returns event-stream/unary inventory responses."""

    def __init__(self) -> None:
        super().__init__(_cfg())
        self.http_token = "fake-token"
        self.calls: list[str] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append(fqmn)
        if fqmn.endswith(".GetVersion"):
            return {"status": 200, "body": {"Version": "3.0.0.46"}}
        if fqmn.endswith(".GetHostPlatformInfo"):
            return {"status": 200, "body": {"platform": "linux"}}
        if fqmn.endswith(".ListNodes"):
            return {"status": 200, "body": {"nodes": [{"node_name": "Server"}]}}
        if fqmn.endswith(".ListCameras"):
            return {
                "status": 200,
                "body": {
                    "event_stream_items": [
                        {"items": [{"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "display_name": "Tracker"}]},
                        {"items": [], "next_page_token": ""},
                    ],
                    "event_stream_count": 2,
                },
            }
        if fqmn.endswith(".ListArchives"):
            return {
                "status": 200,
                "body": {
                    "event_stream_items": [
                        {"items": [{"access_point": "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage", "display_name": "Archive AliceBlue"}]},
                    ],
                    "event_stream_count": 1,
                },
            }
        if fqmn.endswith(".ListComponents"):
            return {
                "status": 200,
                "body": {
                    "event_stream_items": [
                        {"items": [{"access_point": "hosts/Server/MultimediaStorage.AliceBlue/Sources/src.1"}]},
                    ],
                    "event_stream_count": 1,
                },
            }
        return {"status": 200, "body": {}}


class HttpInventoryLoaderTests(unittest.TestCase):
    def test_load_inventory_http_builds_full_shape(self) -> None:
        c = _HttpInventoryFake()
        inv = c.load_inventory_http()
        self.assertEqual(inv["version"], {"Version": "3.0.0.46"})
        self.assertEqual([n["node_name"] for n in inv["nodes"]], ["Server"])
        self.assertEqual(len(inv["cameras"]), 1)
        self.assertEqual(inv["cameras"][0]["display_name"], "Tracker")
        self.assertEqual(len(inv["archives"]), 1)
        self.assertEqual(len(inv["components"]), 1)
        self.assertIn("host_unit", inv)

    def test_load_inventory_http_caches_on_client(self) -> None:
        c = _HttpInventoryFake()
        inv = c.load_inventory_http()
        self.assertIs(c.inventory, inv)

    def test_archive_access_point_resolves_from_http_inventory(self) -> None:
        c = _HttpInventoryFake()
        c.load_inventory_http()
        self.assertIn("AliceBlue", c.archive_access_point())

    def test_load_inventory_falls_back_to_http_on_grpc_failure(self) -> None:
        class _GrpcBrokenFake(_HttpInventoryFake):
            def common_stubs(self):
                raise FileNotFoundError(2, "No such file or directory")

        c = _GrpcBrokenFake()
        inv = c.load_inventory()
        self.assertEqual(len(inv["cameras"]), 1)
        self.assertEqual(inv["cameras"][0]["display_name"], "Tracker")


if __name__ == "__main__":
    unittest.main()
