#!/usr/bin/env python3
"""ServerSettings tools for Axxon One MCP (Phase 20).

Read and set the server log level and drop server log history. The two writes
(`SetLogLevel`, `DropLogs`) are approval-gated (`AXXON_SERVER_APPROVE=1`) plus a
per-call confirmation token, mirroring the audit-injector idiom. ServerSettings
carries no etag, so the writes are plain builds. DropLogs permanently deletes log
history. Direct gRPC against `ServerSettings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

SERVER_APPROVE_ENV = "AXXON_SERVER_APPROVE"
SERVER_CONFIRMATION = "CONFIRM-server-set"
SERVER_PROTO = "axxonsoft/bl/config/ServerSettings.proto"
SERVER_PB2 = "axxonsoft.bl.config.ServerSettings_pb2"

SERVER_TOOL_NAMES = (
    "server_connect_axxon_profile",
    "get_log_level",
    "set_log_level",
    "drop_logs",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(SERVER_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpServerSettings:
    """Phase 20 ServerSettings tools (log-level read + gated set/drop)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def server_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+write",
            "approval_env": SERVER_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.server_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.server_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(SERVER_PROTO, "ServerSettings"), client.import_module(SERVER_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {SERVER_APPROVE_ENV}=1 to enable server writes.", "approval_env": SERVER_APPROVE_ENV}
        if confirmation != SERVER_CONFIRMATION:
            return {"status": "gap", "message": f"server writes require confirmation={SERVER_CONFIRMATION}"}
        return None

    @staticmethod
    def _levels_map(pb2: Any, resp: Any) -> dict[str, str]:
        return {node: pb2.LogLevel.Name(level) for node, level in dict(resp.node_log_level).items()}

    def get_log_level(self, nodes: list[str] | None = None) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        resp = stub.GetLogLevel(pb2.GetLogLevelRequest(nodes=list(nodes or [])), timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "node_log_level": self._levels_map(pb2, resp), "failed_nodes": list(resp.failed_nodes)}

    def set_log_level(self, level: str = "", nodes: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        if not level:
            return {"status": "error", "message": "level is required"}
        stub, pb2 = self._stub_and_pb2()
        valid = list(pb2.LogLevel.keys())
        if level not in valid:
            return {"status": "error", "message": f"unknown level {level}", "valid_levels": valid}
        timeout = self.ensure_client().config.timeout
        resp = stub.SetLogLevel(pb2.SetLogLevelRequest(nodes=list(nodes or []), log_level=pb2.LogLevel.Value(level)), timeout=timeout)
        current = stub.GetLogLevel(pb2.GetLogLevelRequest(nodes=list(nodes or [])), timeout=timeout)
        return {"status": "applied", "node_log_level": self._levels_map(pb2, current), "failed_nodes": list(resp.failed_nodes)}

    def drop_logs(self, nodes: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return gated
        stub, pb2 = self._stub_and_pb2()
        resp = stub.DropLogs(pb2.DropLogsRequest(nodes=list(nodes or [])), timeout=self.ensure_client().config.timeout)
        return {"status": "applied", "failed_nodes": list(resp.failed_nodes)}
