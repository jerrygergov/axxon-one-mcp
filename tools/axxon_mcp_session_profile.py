#!/usr/bin/env python3
"""Process-memory Axxon connection profile for MCP sessions.

The MCP stdio transport owns stdin/stdout, so the server cannot use terminal
prompts for credentials. Instead, clients call ``configure_axxon_connection``
with values they have asked the user for. The resulting config is held only in
this Python process and is forgotten when the MCP server exits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from axxon_api_client import AxxonApiClient, AxxonClientConfig


REQUIRED_CONNECTION_FIELDS = ["host", "grpc_port", "http_port", "username", "password"]
DISALLOWED_CONNECTION_ENV = {
    "AXXON_HOST",
    "AXXON_HTTP_URL",
    "AXXON_HTTP_PORT",
    "AXXON_GRPC_PORT",
    "AXXON_USERNAME",
    "AXXON_PASSWORD",
}


class AxxonConnectionProfileRequired(RuntimeError):
    """Raised when a connection-backed tool is called before runtime config exists."""

    def __init__(self) -> None:
        super().__init__(
            "Axxon connection profile is not configured. Ask the user for host, "
            "gRPC port, HTTP port, username, and password, then call "
            "configure_axxon_connection."
        )


class ConnectionProfileWrapper:
    """Convert missing-profile exceptions from a capability object to MCP data."""

    def __init__(self, wrapped: Any, profile: "AxxonSessionConnectionProfile") -> None:
        object.__setattr__(self, "_wrapped", wrapped)
        object.__setattr__(self, "_profile", profile)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped, name)
        if not callable(attr):
            return attr

        def call_with_profile_guard(*args: Any, **kwargs: Any) -> Any:
            try:
                return attr(*args, **kwargs)
            except AxxonConnectionProfileRequired:
                return self._profile.required_response(tool=name)

        return call_with_profile_guard

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._wrapped, name, value)


class AxxonSessionConnectionProfile:
    """One process-memory Axxon profile shared by MCP capability groups."""

    def __init__(self, *, repo_root: Path | None = None, environ: Mapping[str, str] | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self.environ = dict(environ or {})
        self._config: AxxonClientConfig | None = None
        self._bound_capabilities: list[Any] = []

    def wrap(self, capability: Any) -> ConnectionProfileWrapper:
        self._bound_capabilities.append(capability)
        return ConnectionProfileWrapper(capability, self)

    def config_factory(self) -> AxxonClientConfig:
        if self._config is None:
            raise AxxonConnectionProfileRequired()
        return self._config

    def client_factory(self, config: AxxonClientConfig | None = None) -> AxxonApiClient:
        return AxxonApiClient(config or self.config_factory())

    def lazy_client_factory(self, wrapper: Callable[[AxxonApiClient], Any]) -> Callable[[], Any]:
        return lambda: wrapper(AxxonApiClient(self.config_factory()))

    def host_uid(self) -> str:
        config = self.config_factory()
        return f"hosts/{config.tls_cn or config.host}"

    def required_response(self, *, tool: str | None = None) -> dict[str, Any]:
        response = self.request_axxon_connection()
        if tool:
            response["tool"] = tool
        return response

    def get_axxon_connection_status(self) -> dict[str, Any]:
        if self._config is None:
            return self._missing_profile_status()
        return {
            "configured": True,
            "status": "configured",
            "storage": "process-memory-only",
            "profile": self._public_config_summary(self._config),
        }

    def request_axxon_connection(self) -> dict[str, Any]:
        status = self._missing_profile_status()
        status.update(
            {
                "message": (
                    "Ask the user for host/IP address, gRPC port, HTTP port, username, "
                    "and password, then call configure_axxon_connection. Values are "
                    "kept only in this MCP server process memory."
                ),
                "configure_tool": "configure_axxon_connection",
            }
        )
        return status

    def configure_axxon_connection(
        self,
        host: str,
        grpc_port: int | str,
        http_port: int | str,
        username: str,
        password: str,
        tls_cn: str = "",
        http_scheme: str = "http",
        http_url: str = "",
        timeout: float | str | None = None,
    ) -> dict[str, Any]:
        missing = [
            field
            for field, value in (
                ("host", host),
                ("username", username),
                ("password", password),
            )
            if not str(value or "").strip()
        ]
        converted_ports: dict[str, int] = {}
        invalid = []
        for field, value in (("grpc_port", grpc_port), ("http_port", http_port)):
            try:
                converted = int(value)
            except (TypeError, ValueError):
                invalid.append(field)
                continue
            if not 1 <= converted <= 65535:
                invalid.append(field)
                continue
            converted_ports[field] = converted
        if missing or invalid:
            return {
                "configured": False,
                "status": "invalid",
                "missing_fields": missing,
                "invalid_fields": invalid,
                "required_fields": list(REQUIRED_CONNECTION_FIELDS),
                "message": "Connection profile was not stored; fix the listed fields and call configure_axxon_connection again.",
            }

        scheme = str(http_scheme or "http").strip().lower()
        if scheme not in {"http", "https"}:
            return {
                "configured": False,
                "status": "invalid",
                "missing_fields": [],
                "invalid_fields": ["http_scheme"],
                "required_fields": list(REQUIRED_CONNECTION_FIELDS),
                "message": "http_scheme must be either 'http' or 'https'.",
            }

        resolved_host = str(host).strip()
        resolved_http_url = str(http_url or "").strip() or f"{scheme}://{resolved_host}:{converted_ports['http_port']}"
        resolved_timeout = self._resolve_timeout(timeout)
        self._config = AxxonClientConfig(
            host=resolved_host,
            grpc_port=converted_ports["grpc_port"],
            http_port=converted_ports["http_port"],
            http_url=resolved_http_url,
            username=str(username).strip(),
            password=str(password),
            tls_cn=str(tls_cn or resolved_host).strip(),
            ca=Path(self.environ.get("AXXON_CA", str(self.repo_root / "docs/grpc-proto-files/api.ngp.root-ca.crt"))),
            proto_dir=Path(self.environ.get("AXXON_PROTO_DIR", str(self.repo_root / "docs/grpc-proto-files"))),
            stubs_dir=Path(self.environ.get("AXXON_GRPC_STUBS", "/tmp/axxon-grpc-py")),
            timeout=resolved_timeout,
        )
        return self.get_axxon_connection_status()

    def clear_axxon_connection(self) -> dict[str, Any]:
        self._config = None
        self._reset_bound_capabilities()
        return {
            "configured": False,
            "status": "cleared",
            "storage": "process-memory-only",
            "message": "In-memory Axxon connection profile cleared.",
        }

    def _missing_profile_status(self) -> dict[str, Any]:
        return {
            "configured": False,
            "status": "needs_connection_profile",
            "storage": "process-memory-only",
            "required_fields": list(REQUIRED_CONNECTION_FIELDS),
        }

    def _resolve_timeout(self, timeout: float | str | None) -> float:
        if timeout is not None and str(timeout).strip():
            return float(timeout)
        return float(self.environ.get("AXXON_TIMEOUT", "10.0"))

    def _reset_bound_capabilities(self) -> None:
        visited: set[int] = set()
        for capability in self._bound_capabilities:
            self._reset_capability(capability, visited)

    def _reset_capability(self, capability: Any, visited: set[int]) -> None:
        marker = id(capability)
        if marker in visited:
            return
        visited.add(marker)
        for attr in ("client", "_client", "_inventory", "profile_name"):
            if hasattr(capability, attr):
                try:
                    setattr(capability, attr, None)
                except Exception:
                    pass
        values = getattr(capability, "__dict__", {})
        if not isinstance(values, dict):
            return
        for child in values.values():
            if child is capability or isinstance(child, (str, bytes, int, float, bool, type(None))):
                continue
            module = getattr(child.__class__, "__module__", "")
            if module.startswith("axxon_mcp_"):
                self._reset_capability(child, visited)

    @staticmethod
    def _public_config_summary(config: AxxonClientConfig) -> dict[str, Any]:
        return {
            "host": config.host,
            "grpc_port": config.grpc_port,
            "http_port": config.http_port,
            "http_url": config.http_url,
            "username": config.username,
            "password_present": bool(config.password),
            "tls_cn": config.tls_cn,
            "ca": str(config.ca),
            "timeout": config.timeout,
        }
