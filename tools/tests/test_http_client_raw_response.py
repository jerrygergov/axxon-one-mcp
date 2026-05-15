from __future__ import annotations

from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class HttpClientRawResponseTests(unittest.TestCase):
    def test_http_request_accepts_raw_body_flag(self) -> None:
        config = AxxonClientConfig.from_env(repo_root=Path("arm64-docker"))
        config = AxxonClientConfig(
            host=config.host,
            grpc_port=config.grpc_port,
            http_port=config.http_port,
            http_url="http://example.invalid",
            username="root",
            password="pw",
            tls_cn=config.tls_cn,
            ca=config.ca,
            proto_dir=config.proto_dir,
            stubs_dir=config.stubs_dir,
            timeout=config.timeout,
        )
        _client = AxxonApiClient(config)
        self.assertIn("raw_body", AxxonApiClient.http_request.__code__.co_varnames)
        self.assertIn("max_bytes", AxxonApiClient.http_request.__code__.co_varnames)
