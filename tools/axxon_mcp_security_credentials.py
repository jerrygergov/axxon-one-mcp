#!/usr/bin/env python3
"""SecurityService credential tools for Axxon One MCP (Phase 39).

Pre-check a password's uniqueness/policy (CheckPassword, read-only) and change the
connected session user's own password (ChangePassword) and login (ChangeLogin). The two
writes are approval-gated (`AXXON_SECURITY_CREDENTIALS_APPROVE=1`) plus a per-call
confirmation token, mirroring the bookmark-extras idiom. They act on the authenticated
session's OWN user, not an arbitrary user_id. Direct gRPC against `SecurityService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

SECURITY_CREDENTIALS_APPROVE_ENV = "AXXON_SECURITY_CREDENTIALS_APPROVE"
SECURITY_CREDENTIALS_CONFIRMATION = "CONFIRM-security-credentials"
SECURITY_PROTO = "axxonsoft/bl/security/SecurityService.proto"
SECURITY_PB2 = "axxonsoft.bl.security.SecurityService_pb2"

SECURITY_CREDENTIALS_TOOL_NAMES = (
    "security_credentials_connect_axxon_profile",
    "check_password",
    "change_my_password",
    "change_my_login",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(SECURITY_CREDENTIALS_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpSecurityCredentials:
    """Phase 39 SecurityService credential tools (password check + gated self password/login changes)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def security_credentials_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": SECURITY_CREDENTIALS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.security_credentials_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.security_credentials_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(SECURITY_PROTO, "SecurityService"), client.import_module(SECURITY_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {SECURITY_CREDENTIALS_APPROVE_ENV}=1 to enable credential changes.", "approval_env": SECURITY_CREDENTIALS_APPROVE_ENV}
        if confirmation != SECURITY_CREDENTIALS_CONFIRMATION:
            return {"status": "gap", "message": f"credential changes require confirmation={SECURITY_CREDENTIALS_CONFIRMATION}"}
        return None

    def check_password(self, user_id: str = "", password: str = "") -> dict[str, Any]:
        if not user_id or not password:
            return {"status": "error", "tool": "check_password", "message": "provide a user_id and a password to pre-check"}
        stub, pb2 = self._stub_and_pb2()
        response = stub.CheckPassword(pb2.CheckPasswordRequest(user_id=user_id, password=password), timeout=self.ensure_client().config.timeout)
        code = int(response.result)
        return {"status": "ok", "tool": "check_password", "result": code, "result_name": pb2.CheckPasswordResponse.EResult.Name(code)}

    def change_my_password(self, password: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "change_my_password", **gated}
        if not password:
            return {"status": "error", "tool": "change_my_password", "message": "provide a new password"}
        stub, pb2 = self._stub_and_pb2()
        response = stub.ChangePassword(pb2.ChangePasswordRequest(password=password), timeout=self.ensure_client().config.timeout)
        code = int(response.result)
        return {"status": "applied", "tool": "change_my_password", "result": code, "result_name": pb2.ChangePasswordResponse.EResult.Name(code)}

    def change_my_login(self, login: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "change_my_login", **gated}
        if not login:
            return {"status": "error", "tool": "change_my_login", "message": "provide a new login"}
        stub, pb2 = self._stub_and_pb2()
        response = stub.ChangeLogin(pb2.ChangeLoginRequest(login=login), timeout=self.ensure_client().config.timeout)
        code = int(response.result)
        return {"status": "applied", "tool": "change_my_login", "result": code, "result_name": pb2.ChangeLoginResponse.EResult.Name(code)}
