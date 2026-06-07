#!/usr/bin/env python3
"""AuthenticationService session tools for Axxon One MCP (Phase 40).

Mint a session token (Authenticate / Authenticate2 / AuthenticateEx), renew the current
session (RenewSession / RenewSession2), and close a session (CloseSession). close_session is
approval-gated (`AXXON_AUTH_SESSIONS_APPROVE=1`) plus a per-call confirmation token, since it
ends a session. None of these tools return raw token values; they report a token_present
boolean and the response code only. Direct gRPC against `AuthenticationService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

AUTH_SESSIONS_APPROVE_ENV = "AXXON_AUTH_SESSIONS_APPROVE"
AUTH_SESSIONS_CONFIRMATION = "CONFIRM-auth-sessions"
AUTH_PB2 = "axxonsoft.bl.auth.Authentication_pb2"
AUTH_GRPC = "axxonsoft.bl.auth.Authentication_pb2_grpc"

AUTHENTICATE_VARIANTS = ("Authenticate", "Authenticate2", "AuthenticateEx")
RENEW_VARIANTS = ("RenewSession", "RenewSession2")

AUTH_SESSIONS_TOOL_NAMES = (
    "auth_sessions_connect_axxon_profile",
    "authenticate",
    "renew_session",
    "close_session",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(AUTH_SESSIONS_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpAuthSessions:
    """Phase 40 AuthenticationService session tools (authenticate/renew reads + gated close)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def auth_sessions_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "approval_env": AUTH_SESSIONS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.auth_sessions_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.auth_sessions_connect_axxon_profile("env")
        return self.client

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {AUTH_SESSIONS_APPROVE_ENV}=1 to enable session close.", "approval_env": AUTH_SESSIONS_APPROVE_ENV}
        if confirmation != AUTH_SESSIONS_CONFIRMATION:
            return {"status": "gap", "message": f"session close requires confirmation={AUTH_SESSIONS_CONFIRMATION}"}
        return None

    def _auth_pb2(self) -> Any:
        client = self.ensure_client()
        client.prepare_grpc()
        return client.pb["auth_pb2"]

    def _unauth_stub(self) -> Any:
        client = self.ensure_client()
        client.prepare_grpc()
        return client.pb["auth_grpc"].AuthenticationServiceStub(client.connect_grpc())

    def _authed_stub(self) -> Any:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.pb["auth_grpc"].AuthenticationServiceStub(client.grpc_channel)

    def authenticate(self, user_name: str = "", password: str = "", variant: str = "Authenticate") -> dict[str, Any]:
        if not user_name or not password:
            return {"status": "error", "tool": "authenticate", "message": "provide a user_name and password"}
        if variant not in AUTHENTICATE_VARIANTS:
            return {"status": "error", "tool": "authenticate", "message": f"variant must be one of {AUTHENTICATE_VARIANTS}"}
        pb2 = self._auth_pb2()
        response = getattr(self._unauth_stub(), variant)(pb2.AuthenticateRequest(user_name=user_name, password=password), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "authenticate",
            "variant": variant,
            "token_present": bool(response.token_value),
            "expires_in": int(getattr(response, "expires_in", 0)),
            "user_id": getattr(response, "user_id", ""),
        }

    def renew_session(self, variant: str = "RenewSession") -> dict[str, Any]:
        if variant not in RENEW_VARIANTS:
            return {"status": "error", "tool": "renew_session", "message": f"variant must be one of {RENEW_VARIANTS}"}
        pb2 = self._auth_pb2()
        response = getattr(self._authed_stub(), variant)(pb2.RenewSessionRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "renew_session",
            "variant": variant,
            "token_present": bool(response.token_value),
            "error_code": int(response.error_code),
        }

    def close_session(self, confirmation: str = "") -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": "close_session", **gated}
        pb2 = self._auth_pb2()
        response = self._authed_stub().CloseSession(pb2.CloseSessionRequest(), timeout=self.ensure_client().config.timeout)
        code = int(response.error_code)
        return {"status": "applied", "tool": "close_session", "error_code": code, "error_name": pb2.CloseSessionResponse.EErrorCode.Name(code)}
