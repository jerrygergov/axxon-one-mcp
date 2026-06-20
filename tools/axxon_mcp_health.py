#!/usr/bin/env python3
"""Standard gRPC health-check tools for Axxon One MCP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary


HEALTH_TOOL_NAMES = (
    "health_connect_axxon_profile",
    "grpc_health_check",
    "grpc_health_watch",
)

DEFAULT_WATCH_ITEMS = 4
MAX_WATCH_ITEMS = 16
DEFAULT_WATCH_TIMEOUT_S = 5.0
MAX_WATCH_TIMEOUT_S = 30.0


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _health_pb2() -> Any:
    from grpc_health.v1 import health_pb2

    return health_pb2


def default_health_stub_factory(channel: Any) -> Any:
    from grpc_health.v1 import health_pb2_grpc

    return health_pb2_grpc.HealthStub(channel)


def _cap_int(value: int | float | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _cap_float(value: int | float | None, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value) if value not in (None, 0) else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _status_name(status: int) -> str:
    try:
        return _health_pb2().HealthCheckResponse.ServingStatus.Name(status)
    except Exception:
        return {
            0: "UNKNOWN",
            1: "SERVING",
            2: "NOT_SERVING",
            3: "SERVICE_UNKNOWN",
        }.get(int(status), f"UNRECOGNIZED_{status}")


@dataclass
class AxxonMcpHealth:
    """Bounded wrappers for grpc.health.v1.Health.Check and Watch."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    health_stub_factory: Callable[[Any], Any] = default_health_stub_factory
    client: Any | None = None
    profile_name: str | None = None

    def health_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.health_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.health_connect_axxon_profile("env")
        return self.client

    def _stub(self) -> Any:
        client = self.ensure_client()
        client.authenticate_grpc()
        return self.health_stub_factory(client.grpc_channel)

    def grpc_health_check(self, service: str = "") -> dict[str, Any]:
        """Run grpc.health.v1.Health.Check for the whole server or one service name."""
        client = self.ensure_client()
        request = _health_pb2().HealthCheckRequest(service=service)
        response = self._stub().Check(request, timeout=client.config.timeout)
        return {
            "status": "ok",
            "tool": "grpc_health_check",
            "service": service,
            "serving_status": _status_name(response.status),
            "serving_status_code": int(response.status),
        }

    def grpc_health_watch(self, service: str = "", max_items: int = DEFAULT_WATCH_ITEMS, timeout_s: float = DEFAULT_WATCH_TIMEOUT_S) -> dict[str, Any]:
        """Sample grpc.health.v1.Health.Watch with item and timeout caps."""
        item_cap = _cap_int(max_items, default=DEFAULT_WATCH_ITEMS, minimum=1, maximum=MAX_WATCH_ITEMS)
        timeout = _cap_float(timeout_s, default=DEFAULT_WATCH_TIMEOUT_S, minimum=1.0, maximum=MAX_WATCH_TIMEOUT_S)
        request = _health_pb2().HealthCheckRequest(service=service)
        items: list[str] = []
        stop_reason = "completed"
        try:
            for response in self._stub().Watch(request, timeout=timeout):
                items.append(_status_name(response.status))
                if len(items) >= item_cap:
                    stop_reason = "item_cap"
                    break
        except Exception as exc:
            if not items:
                return {
                    "status": "error",
                    "tool": "grpc_health_watch",
                    "service": service,
                    "message": str(exc)[:500],
                    "items": [],
                    "items_seen": 0,
                    "truncated": False,
                    "stop_reason": "error",
                }
            stop_reason = "stream_error_after_items"
        return {
            "status": "ok",
            "tool": "grpc_health_watch",
            "service": service,
            "items": items,
            "items_seen": len(items),
            "truncated": stop_reason != "completed",
            "stop_reason": stop_reason,
            "timeout_s": timeout,
        }
