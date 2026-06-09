#!/usr/bin/env python3
"""StatisticService read tool for Axxon One MCP (Phase A, step 1).

Read live server and stream statistics (GetStatistics): CPU/memory/disk usage, live and archive
FPS/bitrate, replication and volume health, etc. A single unary `read` RPC, so there is no
approval gate. Direct gRPC against `StatisticService`. No secret value is ever returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

STATISTICS_PROTO = "axxonsoft/bl/statistics/Statistics.proto"
STATISTICS_PB2 = "axxonsoft.bl.statistics.Statistics_pb2"

STATISTICS_TOOL_NAMES = (
    "statistics_connect_axxon_profile",
    "get_statistics",
)

_VALUE_FIELDS = ("value_int32", "value_uint32", "value_int64", "value_uint64", "value_double")


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpStatistics:
    """Phase A StatisticService read tool (server + stream statistics, metadata only)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def statistics_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.statistics_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.statistics_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(STATISTICS_PROTO, "StatisticService"), client.import_module(STATISTICS_PB2)

    def get_statistics(self, keys: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Read statistics for the given stat-point keys, or all available points if none.

        Args:
            keys (list, optional): Stat-point selectors, each {"type": StatPointType name, "name": str}.

        Returns:
            (dict): {"status": "ok", "tool": "get_statistics", "count": int, "stats": [...], "fails": [...]}.
        """
        stub, pb2 = self._stub_and_pb2()
        request = pb2.StatsRequest()
        for key in keys or []:
            type_name = key.get("type", "")
            try:
                type_value = pb2.StatPointType.Value(type_name)
            except (KeyError, ValueError):
                return {"status": "gap", "tool": "get_statistics", "message": f"Unknown stat-point type: {type_name!r}."}
            request.keys.add(type=type_value, name=key.get("name", ""))
        response = stub.GetStatistics(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "tool": "get_statistics",
            "count": len(response.stats),
            "stats": [self._summarize_point(pb2, point) for point in response.stats],
            "fails": [self._summarize_key(pb2, key) for key in response.fails],
        }

    @staticmethod
    def _summarize_key(pb2: Any, key: Any) -> dict[str, Any]:
        return {"type": pb2.StatPointType.Name(key.type), "name": key.name}

    def _summarize_point(self, pb2: Any, point: Any) -> dict[str, Any]:
        which = point.WhichOneof("value")
        return {
            "type": pb2.StatPointType.Name(point.key.type),
            "name": point.key.name,
            "value": getattr(point, which) if which else None,
        }
