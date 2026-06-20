from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_http_api as module

_SECRET = "HTTP-API-CONFIG-SHOULD-NOT-LEAK-" + ("X" * 64)


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


class FakeDocs:
    http_endpoints = {
        "endpoints": [
            {
                "verb": "GET",
                "path": "/v1/domain/cameras",
                "grpc_method": "axxonsoft.bl.domain.DomainService.ListCameras",
                "safety_class": "read",
                "live_status": "tested-pass",
                "source": "docs/api-audit/http-endpoints-catalog.md",
            },
            {
                "verb": "POST",
                "path": "/v1/notifier/email:send",
                "grpc_method": "axxonsoft.bl.notifications.EMailNotifier.SendEMail",
                "safety_class": "mutating",
                "live_status": "pending",
                "source": "docs/api-audit/http-endpoints-catalog.md",
            },
        ]
    }
    legacy_http_endpoints = {
        "endpoints": [
            {
                "id": "legacy-server-hosts",
                "surface": "legacy_web_http",
                "verb": "GET",
                "path": "/hosts/",
                "name": "Get hosts",
                "safety_class": "read",
                "live_status": "documented",
                "source": "docs/Axxon_One_Integration_APIs.postman_collection.json",
            },
            {
                "id": "client-switch-layout",
                "surface": "client_http_api",
                "verb": "POST",
                "path": "/SwitchLayout",
                "name": "Switch layout",
                "safety_class": "external-client",
                "live_status": "fixture-needed",
                "source": "docs/Axxon_One_Integration_APIs.postman_collection.json",
            },
        ]
    }


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.calls: list = []
        self.http_token = "token"

    def authenticate_http_grpc(self):
        self.calls.append(("authenticate_http_grpc",))
        self.http_token = "token"
        return self.http_token

    def http_request(self, method, path, body=None, **kwargs):
        self.calls.append(("http_request", method, path, body, kwargs))
        return {"status": 200, "content_type": "application/json", "size": 12, "body": {"ok": True}}


def _inst(enabled=False):
    inst = module.AxxonMcpHttpApi(
        docs=FakeDocs(),
        client_factory=lambda config: FakeClient(config),
        config_factory=lambda: FakeConfig(),
        enabled=enabled,
    )
    inst.http_api_connect_axxon_profile("env")
    return inst


class HttpApiTests(unittest.TestCase):
    def test_connect_reports_gate(self) -> None:
        out = _inst(enabled=True).http_api_connect_axxon_profile("env")
        self.assertTrue(out["connected"])
        self.assertEqual(out["mode"], "read+http")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["approval_env"], module.HTTP_API_APPROVE_ENV)
        self.assertNotIn(_SECRET, str(out))

    def test_list_http_api_endpoints_combines_v1_and_legacy(self) -> None:
        out = _inst().list_http_api_endpoints(include_mutating=True)
        paths = {item["path"] for item in out["endpoints"]}
        self.assertIn("/v1/domain/cameras", paths)
        self.assertIn("/hosts/", paths)
        self.assertIn("/SwitchLayout", paths)
        surfaces = {item["surface"] for item in out["endpoints"]}
        self.assertIn("v1_http", surfaces)
        self.assertIn("legacy_web_http", surfaces)
        self.assertIn("client_http_api", surfaces)

    def test_read_http_api_request_executes_allowlisted_route(self) -> None:
        inst = _inst()
        out = inst.http_api_request("GET", "/hosts/", query={"limit": 2}, max_bytes=2048)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["http_status"], 200)
        call = inst.client.calls[-1]
        self.assertEqual(call[0], "http_request")
        self.assertEqual(call[1], "GET")
        self.assertEqual(call[2], "/hosts/")
        self.assertEqual(call[4]["max_bytes"], 2048)
        self.assertEqual(call[4]["query"], "limit=2")

    def test_mutating_http_api_request_requires_gate(self) -> None:
        inst = _inst(enabled=False)
        out = inst.http_api_request("POST", "/v1/notifier/email:send", body={"message": "secret"}, confirmation=module.HTTP_API_CONFIRMATION)
        self.assertEqual(out["status"], "disabled")
        self.assertEqual(out["approval_env"], module.HTTP_API_APPROVE_ENV)
        self.assertFalse(any(call[0] == "http_request" for call in inst.client.calls))

    def test_mutating_http_api_request_dispatches_when_confirmed_without_echoing_body(self) -> None:
        inst = _inst(enabled=True)
        out = inst.http_api_request("POST", "/v1/notifier/email:send", body={"message": "SECRET-BODY"}, confirmation=module.HTTP_API_CONFIRMATION)
        self.assertEqual(out["status"], "ok")
        self.assertNotIn("SECRET-BODY", str(out))
        self.assertEqual(inst.client.calls[-1][1], "POST")

    def test_client_http_api_request_remains_fixture_needed(self) -> None:
        inst = _inst(enabled=True)
        out = inst.http_api_request("POST", "/SwitchLayout", confirmation=module.HTTP_API_CONFIRMATION)
        self.assertEqual(out["status"], "fixture-needed")
        self.assertIn("Client HTTP API", out["message"])
        self.assertFalse(any(call[0] == "http_request" for call in inst.client.calls))

    def test_tool_names_exported(self) -> None:
        self.assertIn("list_http_api_endpoints", module.HTTP_API_TOOL_NAMES)
        self.assertIn("http_api_request", module.HTTP_API_TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
