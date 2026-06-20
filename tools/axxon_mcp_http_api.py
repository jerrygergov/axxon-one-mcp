#!/usr/bin/env python3
"""Documented HTTP API catalog and bounded executor for Axxon One MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import urllib.parse

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary
from axxon_mcp_docs import AxxonMcpDocs, DEFAULT_CORPUS_DIR


HTTP_API_APPROVE_ENV = "AXXON_HTTP_API_APPROVE"
HTTP_API_CONFIRMATION = "CONFIRM-http-api"

HTTP_API_TOOL_NAMES = (
    "http_api_connect_axxon_profile",
    "list_http_api_endpoints",
    "http_api_request",
)

DEFAULT_HTTP_RESPONSE_BYTES = 256 * 1024
MAX_HTTP_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_HTTP_ITEMS = 5
MAX_HTTP_ITEMS = 100


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def default_docs_factory() -> AxxonMcpDocs:
    return AxxonMcpDocs.from_corpus_dir(DEFAULT_CORPUS_DIR)


def _approval_from_env() -> bool:
    return os.environ.get(HTTP_API_APPROVE_ENV) == "1"


def _cap_int(value: int | float | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _is_read_endpoint(endpoint: dict[str, Any]) -> bool:
    method = str(endpoint.get("verb", "")).upper()
    safety = str(endpoint.get("safety_class", "")).lower()
    return method in {"GET", "HEAD", "OPTIONS"} and safety in {"read", "safe-read", ""}


@dataclass
class AxxonMcpHttpApi:
    """Allowlisted executor for documented HTTP routes."""

    docs: Any | None = None
    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None
    allow_client_api_execution: bool = False

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()
        if self.docs is None:
            self.docs = default_docs_factory()

    def http_api_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+http",
            "approval_env": HTTP_API_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.http_api_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.http_api_connect_axxon_profile("env")
        return self.client

    def _endpoints(self) -> list[dict[str, Any]]:
        docs = self.docs
        endpoints: list[dict[str, Any]] = []
        for item in getattr(docs, "http_endpoints", {}).get("endpoints", []):
            endpoint = dict(item)
            endpoint.setdefault("surface", "v1_http")
            endpoints.append(endpoint)
        for item in getattr(docs, "legacy_http_endpoints", {}).get("endpoints", []):
            endpoint = dict(item)
            endpoint.setdefault("surface", "legacy_web_http")
            endpoints.append(endpoint)
        return endpoints

    def list_http_api_endpoints(self, surface: str = "", include_mutating: bool = False, limit: int = 100) -> dict[str, Any]:
        """List documented HTTP endpoints from the /v1 and legacy/client catalogs."""
        cap = _cap_int(limit, default=100, minimum=1, maximum=1000)
        filtered = []
        for endpoint in self._endpoints():
            if surface and endpoint.get("surface") != surface:
                continue
            if not include_mutating and not _is_read_endpoint(endpoint):
                continue
            filtered.append(endpoint)
            if len(filtered) >= cap:
                break
        return {
            "status": "ok",
            "tool": "list_http_api_endpoints",
            "endpoint_count": len(filtered),
            "endpoints": filtered,
            "truncated": len(filtered) >= cap,
        }

    def _find_endpoint(self, method: str, path: str) -> dict[str, Any] | None:
        method = method.upper()
        for endpoint in self._endpoints():
            if method == str(endpoint.get("verb", "")).upper() and path == endpoint.get("path"):
                return endpoint
        return None

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {HTTP_API_APPROVE_ENV}=1 to enable mutating HTTP routes.", "approval_env": HTTP_API_APPROVE_ENV}
        if confirmation != HTTP_API_CONFIRMATION:
            return {"status": "gap", "message": f"mutating HTTP routes require confirmation={HTTP_API_CONFIRMATION}"}
        return None

    def http_api_request(
        self,
        method: str = "GET",
        path: str = "",
        query: dict[str, Any] | None = None,
        body: Any = None,
        max_bytes: int = DEFAULT_HTTP_RESPONSE_BYTES,
        max_items: int = DEFAULT_HTTP_ITEMS,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Execute one documented HTTP route with method/path allowlist and response caps."""
        method = method.upper()
        endpoint = self._find_endpoint(method, path)
        if endpoint is None:
            return {"status": "gap", "tool": "http_api_request", "message": f"HTTP route is not in the documented allowlist: {method} {path}"}
        if endpoint.get("surface") == "client_http_api" and not self.allow_client_api_execution:
            return {
                "status": "fixture-needed",
                "tool": "http_api_request",
                "message": "Client HTTP API execution requires a reachable local client fixture and explicit approval; catalog/preflight only for now.",
                "endpoint": endpoint,
            }
        if not _is_read_endpoint(endpoint):
            gated = self._write_gate(confirmation)
            if gated is not None:
                return {"tool": "http_api_request", **gated}
        response_cap = _cap_int(max_bytes, default=DEFAULT_HTTP_RESPONSE_BYTES, minimum=1, maximum=MAX_HTTP_RESPONSE_BYTES)
        item_cap = _cap_int(max_items, default=DEFAULT_HTTP_ITEMS, minimum=1, maximum=MAX_HTTP_ITEMS)
        query_string = urllib.parse.urlencode(query or {}, doseq=True)
        client = self.ensure_client()
        if hasattr(client, "authenticate_http_grpc"):
            client.authenticate_http_grpc()
        response = client.http_request(
            method,
            path,
            body,
            bearer=True,
            query=query_string,
            max_bytes=response_cap,
            max_items=item_cap,
        )
        return {
            "status": "ok",
            "tool": "http_api_request",
            "endpoint": endpoint,
            "http_status": response.get("status"),
            "content_type": response.get("content_type"),
            "size": response.get("size"),
            "body": response.get("body"),
            "response_truncated_at": response_cap,
        }
