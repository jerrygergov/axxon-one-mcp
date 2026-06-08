#!/usr/bin/env python3
"""HeatMapService read tools for the Axxon One MCP server (Phase 44).

Wraps `axxonsoft.bl.heatmap.HeatMapService`. Heatmaps are read-only computations over the VMDA
metadata that a tracker / neurotracker has written to the archive, so there is no write gate: a
build aggregates existing object tracks into a density grid, it does not change configuration.

Tools:
- build_heatmap: density map for one camera over a time window using a textual VMDA query
- build_events_heatmap: density map from an event filter array (server-wide)
- build_floor_heatmap: density map projected onto a floor map (or aggregated data sources)
- execute_heatmap_query / execute_heatmap_query_typed: streaming raw heatmap intervals

Every result is metadata only (result flag, heatmap cell count, image byte count, progress). Raw
image bytes are never returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

HEATMAP_PROTO = "axxonsoft/bl/heatmap/HeatMap.proto"
HEATMAP_PB2 = "axxonsoft.bl.heatmap.HeatMap_pb2"
PRIMITIVE_PB2 = "axxonsoft.bl.primitive.Primitives_pb2"
EVENTS_PB2 = "axxonsoft.bl.events.EventHistory_pb2"
VMDA_QUERY_PB2 = "axxonsoft.bl.vmda.Query_pb2"

DEFAULT_BUILDER_AP = "hosts/Server/HeatMapBuilder.0/HeatMapBuilder"
# Bounded VMDA query: object-centroid density over the full normalized frame.
DEFAULT_QUERY = (
    "figure fZone=polygon(0,0,1,0,1,1,0,1); "
    "set r = group[obj=vmda_object] { res = or(fZone((obj.left + obj.right) / 2, obj.bottom)) }; "
    "result = r.res;"
)
MAX_STREAM_RESPONSES = 8

HEATMAP_TOOL_NAMES = (
    "heatmap_connect_axxon_profile",
    "build_heatmap",
    "build_events_heatmap",
    "build_floor_heatmap",
    "execute_heatmap_query",
    "execute_heatmap_query_typed",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpHeatmap:
    """HeatMapService read tools (Phase 44). Metadata-only, no write gate."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def heatmap_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.heatmap_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.heatmap_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        stub = client.stub_from_proto(HEATMAP_PROTO, "HeatMapService")
        return stub, client.import_module(HEATMAP_PB2), client.import_module(PRIMITIVE_PB2)

    def _timeout(self) -> Any:
        return self.ensure_client().config.timeout

    def _image_summary(self, tool: str, response: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        out = {
            "status": "ok",
            "tool": tool,
            "result": bool(response.result),
            "heatmap_cells": len(response.heatmap),
            "image_bytes": len(response.image_data),
        }
        if extra:
            out.update(extra)
        return out

    def build_heatmap(self, camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "",
                      builder_access_point: str = DEFAULT_BUILDER_AP, mask: int = 16, image_width: int = 320,
                      image_height: int = 240) -> dict[str, Any]:
        """Build an object-density heatmap image for one camera over a window via a textual VMDA query."""
        if not camera_id or not start_time or not end_time:
            return {"status": "error", "tool": "build_heatmap", "message": "provide camera_id, start_time, end_time (YYYYMMDDTHHMMSS.ffffff)"}
        stub, pb2, prim = self._stub_and_pb2()
        request = pb2.BuildHeatmapRequest(
            access_point=builder_access_point, camera_ID=camera_id,
            dt_posix_start_time=start_time, dt_posix_end_time=end_time, query=query or DEFAULT_QUERY,
            mask_size=prim.SizeInt(width=int(mask), height=int(mask)), result_type=pb2.RESULT_TYPE_IMAGE,
            image_size=prim.SizeInt(width=int(image_width), height=int(image_height)))
        return self._image_summary("build_heatmap", stub.BuildHeatmap(request, timeout=self._timeout()))

    def build_events_heatmap(self, start_time: str = "", end_time: str = "", builder_access_point: str = DEFAULT_BUILDER_AP,
                             mask: int = 16, image_width: int = 320, image_height: int = 240) -> dict[str, Any]:
        """Build a server-wide event-density heatmap image over a window (empty filter = all events)."""
        if not start_time or not end_time:
            return {"status": "error", "tool": "build_events_heatmap", "message": "provide start_time and end_time"}
        stub, pb2, prim = self._stub_and_pb2()
        events_pb2 = self.ensure_client().import_module(EVENTS_PB2)
        request = pb2.BuildEventsHeatmapRequest(
            access_point=builder_access_point, dt_start_time=start_time, dt_end_time=end_time,
            filters=events_pb2.SearchFilterArray(), mask_size=prim.SizeInt(width=int(mask), height=int(mask)),
            result_type=pb2.RESULT_TYPE_IMAGE, image_size=prim.SizeInt(width=int(image_width), height=int(image_height)))
        return self._image_summary("build_events_heatmap", stub.BuildEventsHeatmap(request, timeout=self._timeout()))

    def build_floor_heatmap(self, camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "",
                            map_guid: str = "", builder_access_point: str = DEFAULT_BUILDER_AP, mask: int = 16,
                            image_width: int = 320, image_height: int = 240) -> dict[str, Any]:
        """Build a floor-projected heatmap from one camera's VMDA data source over a window."""
        if not camera_id or not start_time or not end_time:
            return {"status": "error", "tool": "build_floor_heatmap", "message": "provide camera_id, start_time, end_time"}
        stub, pb2, prim = self._stub_and_pb2()
        data_sources = pb2.DataSourceArray(data_sources=[pb2.DataSource(access_point=camera_id, query=query or DEFAULT_QUERY)])
        request = pb2.BuildFloorHeatmapRequest(
            map_guid=map_guid, access_point=builder_access_point, dt_start_time=start_time, dt_end_time=end_time,
            mask_size=prim.SizeInt(width=int(mask), height=int(mask)), result_type=pb2.RESULT_TYPE_IMAGE,
            image_size=prim.SizeInt(width=int(image_width), height=int(image_height)), data_sources=data_sources)
        return self._image_summary("build_floor_heatmap", stub.BuildFloorHeatmap(request, timeout=self._timeout()),
                                   {"map_guid": map_guid})

    def execute_heatmap_query(self, camera_id: str = "", start_time: str = "", end_time: str = "", query: str = "",
                              max_responses: int = MAX_STREAM_RESPONSES) -> dict[str, Any]:
        """Stream raw heatmap intervals for one camera's VMDA query (bounded response count)."""
        if not camera_id or not start_time or not end_time:
            return {"status": "error", "tool": "execute_heatmap_query", "message": "provide camera_id, start_time, end_time"}
        stub, pb2, _ = self._stub_and_pb2()
        request = pb2.ExecuteHeatmapQueryRequest(camera_ID=camera_id, dt_posix_start_time=start_time,
                                                 dt_posix_end_time=end_time, query=query or DEFAULT_QUERY)
        return self._consume_stream("execute_heatmap_query", stub.ExecuteHeatmapQuery(request, timeout=self._timeout()), max_responses)

    def execute_heatmap_query_typed(self, camera_id: str = "", start_time: str = "", end_time: str = "",
                                    max_responses: int = MAX_STREAM_RESPONSES) -> dict[str, Any]:
        """Stream raw heatmap intervals via a typed motion-in-area query over the full frame (bounded)."""
        if not camera_id or not start_time or not end_time:
            return {"status": "error", "tool": "execute_heatmap_query_typed", "message": "provide camera_id, start_time, end_time"}
        stub, pb2, _ = self._stub_and_pb2()
        vmda = self.ensure_client().import_module(VMDA_QUERY_PB2)
        prim = self.ensure_client().import_module(PRIMITIVE_PB2)
        frame = prim.Polyline(points=[prim.Point(x=0, y=0), prim.Point(x=1, y=0), prim.Point(x=1, y=1), prim.Point(x=0, y=1)])
        description = vmda.QueryDescription(motion_in_area=vmda.MotionInArea(area=frame))
        request = pb2.ExecuteHeatmapQueryTypedRequest(camera_ID=camera_id, dt_posix_start_time=start_time,
                                                      dt_posix_end_time=end_time, query=description)
        return self._consume_stream("execute_heatmap_query_typed", stub.ExecuteHeatmapQueryTyped(request, timeout=self._timeout()), max_responses)

    def _consume_stream(self, tool: str, stream: Any, max_responses: int) -> dict[str, Any]:
        cap = max(1, min(int(max_responses), MAX_STREAM_RESPONSES))
        count = 0
        last_progress = ""
        total_cells = 0
        for response in stream:
            count += 1
            last_progress = response.progress
            total_cells += len(response.heatmap)
            if count >= cap:
                break
        return {"status": "ok", "tool": tool, "responses": count, "last_progress": last_progress, "heatmap_cells": total_cells}
