from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_domain_topology as module

_SECRET = "TOPO-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class _Domain:
    name = "Domain1"
    display_name = "Main Domain"
    activated = True


class _Node:
    def __init__(self, name="Server", display_name="Server", state=1, endpoints=("1.2.3.4:20109",)):
        self.name = name
        self.display_name = display_name
        self.state = state
        self.grpc_endpoints = list(endpoints)


class _EnumerateResponse:
    def __init__(self, nodes=None, free_nodes=None, other_nodes=None):
        self.domain = _Domain()
        self.nodes = nodes if nodes is not None else [_Node()]
        self.free_nodes = free_nodes if free_nodes is not None else []
        self.other_nodes = other_nodes if other_nodes is not None else []


class _Empty:
    pass


class _Pb2:
    EnumerateNodesRequest = _Empty


class _Stub:
    def __init__(self, rec, response=None):
        self._rec = rec
        self._response = response

    def EnumerateNodes(self, request, timeout=None):
        self._rec.append(("EnumerateNodes",))
        return self._response if self._response is not None else _EnumerateResponse()


class FakeClient:
    def __init__(self, config, response=None):
        self.config = config
        self.calls: list = []
        self._response = response

    def authenticate_grpc(self):
        return None

    def stub_from_proto(self, proto_path, service_name):
        return _Stub(self.calls, self._response)

    def import_module(self, name):
        return _Pb2()


def _inst(response=None):
    inst = module.AxxonMcpDomainTopology(
        client_factory=lambda config: FakeClient(config, response),
        config_factory=lambda: FakeConfig(),
    )
    inst.domain_topology_connect_axxon_profile("env")
    return inst


class DomainTopologyTests(unittest.TestCase):
    def test_connect_read_mode(self) -> None:
        out = _inst().domain_topology_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read")

    def test_enumerate_nodes_ok(self) -> None:
        out = _inst().enumerate_nodes()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["tool"], "enumerate_nodes")
        self.assertEqual(out["domain"]["name"], "Domain1")
        self.assertTrue(out["domain"]["activated"])
        self.assertEqual(out["node_count"], 1)
        self.assertEqual(out["nodes"][0]["name"], "Server")
        self.assertEqual(out["free_node_count"], 0)
        self.assertEqual(out["other_node_count"], 0)

    def test_no_secret_leak(self) -> None:
        out = _inst().enumerate_nodes()
        self.assertNotIn(_SECRET, str(out))

    def test_tool_names_exported(self) -> None:
        self.assertIn("enumerate_nodes", module.DOMAIN_TOPOLOGY_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
