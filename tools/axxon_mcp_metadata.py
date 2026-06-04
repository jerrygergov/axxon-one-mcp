#!/usr/bin/env python3
"""Read-only metadata / VMDA object-track search tools for the Axxon One MCP server.

Two capabilities, both reachable on a live stand:
- `live_track_sample`: bounded `MetadataService.PullMetadata` stream of live object tracklets
  from a tracker's `*/SourceEndpoint.vmda` endpoint (id, state, behavior, bbox).
- `vmda_query`: archived forensic search via `VMDAService.ExecuteQueryTyped` (MotionInArea +
  object-type/behaviour constraints), bound with `camera_ID == access_point` (the form the
  server accepts). Returns archived intervals; a stand that does not persist VMDA tracks
  returns zero intervals (status ok), which is correct behavior.

The module never mutates stand config and reads credentials only from the environment.
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig

MAX_SECONDS = 30.0
MAX_TRACKLETS = 200
MAX_INTERVALS = 500
DEFAULT_SECONDS = 5.0
DEFAULT_TRACKLETS = 40
DEFAULT_QUERY_HOURS = 24

OBJECT_TYPE_NAMES = {"face": "FACE", "human": "HUMAN", "group": "GROUP", "vehicle": "VEHICLE"}
BEHAVIOUR_NAMES = {"moving": "MOVING", "abandoned": "ABANDONED"}
QUERY_TYPES = {"motion_in_area"}


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def public_config_summary(config: Any) -> dict[str, Any]:
    return {"host": "<redacted>", "tls_cn": getattr(config, "tls_cn", ""), "mode": "read-only"}


def _redact(value: Any, limit: int = 240) -> str:
    text = str(value)
    for needle in ("password", "token", "Bearer "):
        if needle in text:
            text = text.replace(text, "<redacted>")
            break
    return text[:limit]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _axxon_ts(value: dt.datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S.%f")


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_strings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_flatten_strings(item))
    return out


def _tracklet_summary(tracklet: dict[str, Any]) -> dict[str, Any]:
    rect = tracklet.get("rectangle") or {}
    return {
        "id": tracklet.get("id"),
        "state": tracklet.get("state"),
        "behavior": tracklet.get("behavior"),
        "bbox": {k: rect.get(k) for k in ("x", "y", "w", "h")} if rect else {},
    }


@dataclass
class AxxonMcpMetadata:
    """Read-only metadata / VMDA search tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    MAX_SECONDS = MAX_SECONDS
    MAX_TRACKLETS = MAX_TRACKLETS
    MAX_INTERVALS = MAX_INTERVALS

    def metadata_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read-only"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.metadata_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.metadata_connect_axxon_profile("env")
        return self.client

    def list_vmda_sources(self, limit: int = 64) -> dict[str, Any]:
        """Return the stand's VMDA-capable endpoints (*/SourceEndpoint.vmda)."""
        try:
            client = self.ensure_client()
            inventory = client.load_inventory() if hasattr(client, "load_inventory") else {}
            sources: list[str] = []
            for text in _flatten_strings(inventory):
                if text.endswith("/SourceEndpoint.vmda") and text not in sources:
                    sources.append(text)
            return {"status": "ok", "tool": "list_vmda_sources", "count": len(sources), "sources": sorted(sources)[:max(1, limit)]}
        except Exception as exc:  # noqa: BLE001 - surface transport failures as a clean dict
            return {"status": "error", "tool": "list_vmda_sources", "message": _redact(exc), "sources": []}

    def live_track_sample(self, access_point: str, seconds: float | None = None, limit: int | None = None) -> dict[str, Any]:
        """Stream bounded live tracklets from a VMDA endpoint via MetadataService.PullMetadata."""
        applied_seconds = _clamp(float(seconds if seconds is not None else DEFAULT_SECONDS), 1.0, MAX_SECONDS)
        applied_limit = int(_clamp(float(limit if limit is not None else DEFAULT_TRACKLETS), 1, MAX_TRACKLETS))
        applied = {"seconds": applied_seconds, "limit": applied_limit}
        tracklets: list[dict[str, Any]] = []
        try:
            client = self.ensure_client()
            if hasattr(client, "authenticate_grpc"):
                client.authenticate_grpc()
            meta_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
            media_pb2 = client.import_module("axxonsoft.bl.media.Media_pb2")
            stub = client.stub_from_proto("axxonsoft/bl/metadata/MetadataService.proto", "MetadataService")
            endpoint = media_pb2.EndpointRef(access_point=access_point)
            request = meta_pb2.PullMetadataRequest(count=applied_limit, endpoint=endpoint)
            deadline = time.monotonic() + applied_seconds
            call = stub.PullMetadata(iter([request]), timeout=applied_seconds)
            stopped_clean = False
            try:
                for response in call:
                    if time.monotonic() > deadline or len(tracklets) >= applied_limit:
                        break
                    frame = client.message_to_dict(response)
                    sample = frame.get("sample") if isinstance(frame, dict) else None
                    inner = (sample or {}).get("tracklets", {}) if isinstance(sample, dict) else {}
                    for tracklet in inner.get("tracklets", []) if isinstance(inner, dict) else []:
                        tracklets.append(_tracklet_summary(tracklet))
                        if len(tracklets) >= applied_limit:
                            break
                stopped_clean = True
            finally:
                cancel = getattr(call, "cancel", None)
                if callable(cancel):
                    cancel()
            # A bounded stream we cut short ends with CANCELLED/DEADLINE; that is a clean stop.
            _ = stopped_clean
            return {"status": "ok", "tool": "live_track_sample", "access_point": access_point, "applied": applied, "count": len(tracklets), "tracklets": tracklets[:applied_limit]}
        except Exception as exc:  # noqa: BLE001 - never hang or leak a raw stack to MCP callers
            code = getattr(exc, "code", None)
            code_name = getattr(code(), "name", "") if callable(code) else ""
            if tracklets and code_name in {"CANCELLED", "DEADLINE_EXCEEDED"}:
                return {"status": "ok", "tool": "live_track_sample", "access_point": access_point, "applied": applied, "count": len(tracklets), "tracklets": tracklets[:applied_limit], "stream_stop": code_name.lower()}
            return {"status": "error", "tool": "live_track_sample", "access_point": access_point, "applied": applied, "message": _redact(exc), "count": len(tracklets), "tracklets": tracklets}

    def vmda_query(
        self,
        access_point: str,
        query_type: str = "motion_in_area",
        object_types: list[str] | None = None,
        behaviours: list[str] | None = None,
        begin: str | None = None,
        end: str | None = None,
        hours: int | None = None,
        max_intervals: int | None = None,
    ) -> dict[str, Any]:
        """Archived VMDA forensic search via VMDAService.ExecuteQueryTyped (camera_ID==access_point)."""
        if query_type not in QUERY_TYPES:
            return {"status": "gap", "tool": "vmda_query", "access_point": access_point, "message": f"query_type must be one of {sorted(QUERY_TYPES)}; got {query_type!r}"}
        cap = int(_clamp(float(max_intervals if max_intervals is not None else MAX_INTERVALS), 1, MAX_INTERVALS))
        intervals: list[dict[str, Any]] = []
        object_total = 0
        try:
            client = self.ensure_client()
            if hasattr(client, "authenticate_grpc"):
                client.authenticate_grpc()
            vmda_pb2 = client.import_module("axxonsoft.bl.vmda.VMDA_pb2")
            query_pb2 = client.import_module("axxonsoft.bl.vmda.Query_pb2")
            primitive_pb2 = client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
            stub = client.stub_from_proto("axxonsoft/bl/vmda/VMDA.proto", "VMDAService")

            now = dt.datetime.now()
            window = int(hours if hours is not None else DEFAULT_QUERY_HOURS)
            begin_ts = begin or _axxon_ts(now - dt.timedelta(hours=window))
            end_ts = end or _axxon_ts(now + dt.timedelta(hours=1))

            full_frame = primitive_pb2.Polyline(
                points=[primitive_pb2.Point(x=0.0, y=0.0), primitive_pb2.Point(x=1.0, y=0.0),
                        primitive_pb2.Point(x=1.0, y=1.0), primitive_pb2.Point(x=0.0, y=1.0)],
                closed=True,
            )
            constraint_kwargs: dict[str, Any] = {}
            ot = [getattr(query_pb2, OBJECT_TYPE_NAMES[name]) for name in (object_types or []) if name in OBJECT_TYPE_NAMES]
            bh = [getattr(query_pb2, BEHAVIOUR_NAMES[name]) for name in (behaviours or []) if name in BEHAVIOUR_NAMES]
            if ot:
                constraint_kwargs["object_types"] = ot
            if bh:
                constraint_kwargs["behaviours"] = bh
            description_kwargs: dict[str, Any] = {"motion_in_area": query_pb2.MotionInArea(area=full_frame)}
            if constraint_kwargs:
                description_kwargs["additional_filters"] = query_pb2.Constraints(**constraint_kwargs)
            query = query_pb2.QueryDescription(**description_kwargs)

            request = vmda_pb2.ExecuteQueryTypedRequest(
                access_point=access_point,
                camera_ID=access_point,
                dt_posix_start_time=begin_ts,
                dt_posix_end_time=end_ts,
                query=query,
            )
            for response in stub.ExecuteQueryTyped(request, timeout=MAX_SECONDS):
                for interval in getattr(response, "intervals", []):
                    objects = list(getattr(interval, "objects", []))
                    object_total += len(objects)
                    intervals.append({"object_count": len(objects)})
                    if len(intervals) >= cap:
                        break
                if len(intervals) >= cap:
                    break
            return {"status": "ok", "tool": "vmda_query", "access_point": access_point, "query_type": query_type, "time_range": {"begin": begin_ts, "end": end_ts}, "interval_count": len(intervals), "object_count": object_total, "intervals": intervals[:cap]}
        except Exception as exc:  # noqa: BLE001 - clean error dict for MCP callers
            return {"status": "error", "tool": "vmda_query", "access_point": access_point, "query_type": query_type, "message": _redact(exc), "interval_count": len(intervals), "object_count": object_total, "intervals": intervals}
