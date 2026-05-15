#!/usr/bin/env python3
"""Read-only live inspection helpers for the Axxon One MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def includes(text: str, needle: str | None) -> bool:
    return not needle or needle.lower() in text.lower()


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def flatten_dicts(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        for item in value.values():
            out.extend(flatten_dicts(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_dicts(item))
    return out


def flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(flatten_strings(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_strings(item))
    return out


def public_config_summary(config: Any) -> dict[str, Any]:
    return {
        "host": getattr(config, "host", ""),
        "grpc_port": getattr(config, "grpc_port", None),
        "http_port": getattr(config, "http_port", None),
        "http_url": getattr(config, "http_url", ""),
        "username": getattr(config, "username", ""),
        "password_present": bool(getattr(config, "password", "")),
        "tls_cn": getattr(config, "tls_cn", ""),
        "ca": str(getattr(config, "ca", "")),
        "timeout": getattr(config, "timeout", None),
    }


def summarize_unit(item: dict[str, Any], sanitizer: Callable[[Any], Any]) -> dict[str, Any]:
    summary = {
        "access_point": first_present(item, "access_point", "accessPoint", "uid"),
        "uid": first_present(item, "uid", "id"),
        "display_name": first_present(item, "display_name", "displayName", "name"),
        "type": item.get("type"),
        "enabled": item.get("enabled"),
        "model": item.get("model"),
        "vendor": item.get("vendor"),
    }
    return {key: value for key, value in sanitizer(summary).items() if value not in (None, "", [], {})}


@dataclass
class AxxonMcpLive:
    """Read-only live API view for MCP tools.

    Credentials stay inside the constructed AxxonApiClient. Public methods return
    only summaries and sanitized access point strings.
    """

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = None

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported in this local MCP prototype.",
                "profile_name": profile,
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        self._inventory = None
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read-only",
        }

    def ensure_client(self) -> Any:
        if self.client is None:
            self.connect_axxon_profile("env")
        return self.client

    def inventory(self) -> dict[str, Any]:
        if self._inventory is None:
            self._inventory = self.ensure_client().load_inventory()
        return self._inventory

    def sanitize(self, value: Any) -> Any:
        client = self.ensure_client()
        if hasattr(client, "sanitize"):
            return client.sanitize(value)
        return value

    def list_cameras(self, filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        return self._summarize_collection("cameras", filter_text, limit)

    def list_archives(self, filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        return self._summarize_collection("archives", filter_text, limit)

    def list_config_units(self, filter_text: str | None = None, limit: int = 100) -> dict[str, Any]:
        units = [item for item in flatten_dicts(self.inventory().get("host_unit", {})) if item.get("uid") or item.get("type")]
        return self._summarize_items("config_units", units, filter_text, limit)

    def list_detectors(self, camera_or_host: str | None = None, limit: int = 100) -> dict[str, Any]:
        items = self._detector_items("AVDetector", camera_or_host)
        return self._summarize_items("detectors", items, None, limit)

    def list_appdata_detectors(self, camera_or_host: str | None = None, limit: int = 100) -> dict[str, Any]:
        items = self._detector_items("AppDataDetector", camera_or_host)
        return self._summarize_items("appdata_detectors", items, None, limit)

    def find_event_suppliers(self, camera_or_detector: str | None = None, limit: int = 100) -> dict[str, Any]:
        values = [
            value
            for value in flatten_strings(self.inventory())
            if "EventSupplier" in value and includes(value, camera_or_detector)
        ]
        return {"kind": "event_suppliers", "count": len(unique_strings(values)), "items": unique_strings(values)[:limit]}

    def find_metadata_endpoints(self, camera_or_detector: str | None = None, limit: int = 100) -> dict[str, Any]:
        values = [
            value
            for value in flatten_strings(self.inventory())
            if re.search(r"SourceEndpoint\.(vmda|metadata)", value) and includes(value, camera_or_detector)
        ]
        return {"kind": "metadata_endpoints", "count": len(unique_strings(values)), "items": unique_strings(values)[:limit]}

    def get_archive_intervals(
        self,
        camera: str,
        hours: float = 1.0,
        max_count: int = 32,
        min_gap_ms: int = 1000,
    ) -> dict[str, Any]:
        """Return bounded archive intervals for the given camera access point.

        Wraps ``ArchiveService.GetHistory2`` through ``AxxonApiClient.get_archive_history``.
        ``camera`` may be either a camera ``SourceEndpoint.video:N:N`` access point or a
        storage source ``/Sources/src.N`` access point. Camera APs are translated to the
        first matching storage source from the connected inventory. Unknown APs return
        ``status: gap``.
        """
        access_points = {
            str(item.get("access_point") or "")
            for item in flatten_dicts(self.inventory())
            if item.get("access_point")
        }
        if camera not in access_points:
            return {
                "status": "gap",
                "message": f"access point not in current inventory: {camera}",
                "camera": camera,
            }
        # Translate camera SourceEndpoint -> a matching storage source AP.
        # GetHistory2 expects an archive storage source ("/Sources/src.*"), not a
        # camera SourceEndpoint. Prefer a MultimediaStorage archive source because
        # device-embedded storage APs can appear in inventory yet fail to resolve.
        source_ap = camera
        if "/SourceEndpoint." in camera:
            multimedia_sources = sorted(
                [ap for ap in access_points if "/MultimediaStorage." in ap and "/Sources/src." in ap]
            )
            if multimedia_sources:
                source_ap = multimedia_sources[0]
            else:
                any_source = sorted([ap for ap in access_points if "/Sources/src." in ap])
                if not any_source:
                    return {
                        "status": "gap",
                        "message": f"no archive storage source available for {camera}",
                        "camera": camera,
                    }
                source_ap = any_source[0]

        hours = max(0.05, min(float(hours), 24.0))
        max_count = max(1, min(int(max_count), 200))
        min_gap_ms = max(0, int(min_gap_ms))
        epoch_1900_ms = 2208988800000
        import datetime as _dt
        now = _dt.datetime.now(_dt.UTC)
        begin = int((now - _dt.timedelta(hours=hours)).timestamp() * 1000) + epoch_1900_ms
        end = int(now.timestamp() * 1000) + epoch_1900_ms

        client = self.ensure_client()
        payload = client.get_archive_history(
            access_point=source_ap,
            begin_time=begin,
            end_time=end,
            max_count=max_count,
            min_gap_ms=min_gap_ms,
        )
        intervals = payload.get("intervals", []) if isinstance(payload, dict) else []
        return {
            "status": "ok",
            "camera": camera,
            "source_access_point": source_ap,
            "hours": hours,
            "max_count": max_count,
            "count": len(intervals),
            "intervals": intervals[:max_count],
        }

    def subscribe_events_bounded(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout: float = 5.0,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Bounded ``DomainNotifier.PullEvents`` subscription with hard caps.

        Caps: ``timeout`` clamped to [1.0, 30.0] seconds, ``limit`` clamped to [1, 500] events.
        Returns shaped event summaries only; raw protobuf payloads are not exposed.
        """
        timeout = max(1.0, min(float(timeout), 30.0))
        limit = max(1, min(int(limit), 500))
        subjects = list(subjects or [])
        event_types = list(event_types or [])

        client = self.ensure_client()
        events = client.pull_events_bounded(
            subjects=subjects,
            event_types=event_types,
            timeout=timeout,
            max_events=limit,
        )
        return {
            "status": "ok",
            "subjects": subjects,
            "event_types": event_types,
            "timeout": timeout,
            "limit": limit,
            "count": len(events),
            "events": list(events)[:limit],
        }

    def list_event_types(self) -> dict[str, Any]:
        """Return the full EEventType enum (name + numeric value) from the live proto."""
        client = self.ensure_client()
        client.authenticate_grpc()
        events_pb2 = client.import_module("axxonsoft.bl.events.Events_pb2")
        enum = events_pb2.EEventType.DESCRIPTOR
        items = [{"name": v.name, "value": v.number} for v in enum.values]
        return {"kind": "event_types", "count": len(items), "items": items}

    def list_detector_kinds(self) -> dict[str, Any]:
        """Return detector kinds discovered from live AVDetector / AppDataDetector descriptors.

        Scans up to 50 candidate detectors per type and harvests the union of the
        ``detector`` enum constraints found in their ``input`` properties. Stands
        with a fresh DB may have detectors that omit the enum; the union dedupes
        across whatever is exposed.
        """
        client = self.ensure_client()
        client.authenticate_grpc()
        pb_d = client.import_module("axxonsoft.bl.domain.Domain_pb2")
        pb_c = client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        domain = client.common_stubs()["domain"]
        config_stub = client.common_stubs()["config"]

        # Collect up to 50 candidate UIDs per detector type.
        candidates: dict[str, list[str]] = {"AVDetector": [], "AppDataDetector": []}
        for page in domain.ListComponents(pb_d.ListComponentsRequest(page_size=500), timeout=client.config.timeout):
            for c in client.message_to_dict(page).get("items", []):
                ap = c.get("access_point", "")
                for kind in candidates:
                    if f"/{kind}." in ap and len(candidates[kind]) < 50:
                        uid = ap.split("/EventSupplier")[0].split("/SourceEndpoint")[0]
                        if uid not in candidates[kind]:
                            candidates[kind].append(uid)

        # Known detector kinds documented in the PDF / verified via mutation smokes.
        # The live enum_constraint lookup below augments these whenever the descriptor
        # is present in a deployed unit. Returned as a union so callers always get a
        # usable list even on stands whose detector units omit the descriptor catalog.
        known: dict[str, set[str]] = {
            "AVDetector": {"MotionDetection", "SceneDescription", "NeuroTracker"},
            "AppDataDetector": {"MoveInZone", "OneLineCrossing", "LongInZone", "LostObject", "AbandonedObject"},
        }
        for label, uids in candidates.items():
            for uid in uids[:10]:
                resp = config_stub.ListUnits(pb_c.ListUnitsRequest(unit_uids=[uid]), timeout=client.config.timeout)
                for u in client.message_to_dict(resp).get("units") or []:
                    for prop in u.get("properties") or []:
                        if prop.get("id") in ("input", "Input"):
                            for sub in prop.get("properties") or []:
                                if sub.get("id") == "detector":
                                    for e in sub.get("enum_constraint", {}).get("items", []):
                                        v = e.get("value_string", "")
                                        if v:
                                            known.setdefault(label, set()).add(v)
                                    actual = sub.get("value_string", "")
                                    if actual:
                                        known.setdefault(label, set()).add(actual)
        return {
            "kind": "detector_kinds",
            "by_unit_type": {k: sorted(v) for k, v in known.items()},
            "source": "documented kinds union with live enum_constraint and live detector property values",
        }

    def search_events(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        hours: float = 1.0,
        limit: int = 100,
        descending: bool = True,
    ) -> dict[str, Any]:
        """Search persisted events via ``EventHistoryService.ReadEvents``.

        Caps: ``hours`` clamped to [0.05, 168.0], ``limit`` clamped to [1, 1000]. Returns
        sanitized event summaries only.
        """
        hours = max(0.05, min(float(hours), 168.0))
        limit = max(1, min(int(limit), 1000))
        subjects = list(subjects or [])
        event_types = list(event_types or [])

        client = self.ensure_client()
        client.authenticate_grpc()
        events_pb2 = client.import_module("axxonsoft.bl.events.Events_pb2")
        history_pb2 = client.import_module("axxonsoft.bl.events.EventHistory_pb2")
        primitive_pb2 = client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        stub = client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
        client.authenticate_grpc()

        import datetime as _dt
        epoch_1900_ms = 2208988800000
        now = _dt.datetime.now(_dt.UTC)
        begin_ms = int((now - _dt.timedelta(hours=hours)).timestamp() * 1000) + epoch_1900_ms
        end_ms = int(now.timestamp() * 1000) + epoch_1900_ms

        type_enum = events_pb2.EEventType
        resolved_types: list[int] = []
        for t in event_types:
            if isinstance(t, int):
                resolved_types.append(t)
                continue
            name = t if t.startswith("ET_") or t == "EEventType_UNSPECIFIED" else f"ET_{t}"
            if name in type_enum.DESCRIPTOR.values_by_name:
                resolved_types.append(type_enum.DESCRIPTOR.values_by_name[name].number)

        filters: list[Any] = []
        if resolved_types or subjects:
            for type_value in resolved_types or [0]:
                f = history_pb2.SearchFilter(type=type_value)
                if subjects:
                    f.subjects.extend(subjects)
                filters.append(f)
        request = history_pb2.ReadEventsRequest(
            range=primitive_pb2.TimeRange(begin_time=str(begin_ms), end_time=str(end_ms)),
            filters=history_pb2.SearchFilterArray(filters=filters) if filters else history_pb2.SearchFilterArray(),
            descending=descending,
        )
        collected: list[dict[str, Any]] = []
        for response in stub.ReadEvents(request, timeout=client.config.timeout):
            for item in client.message_to_dict(response).get("items", []):
                if len(collected) >= limit:
                    break
                collected.append(client.sanitize(item))
            if len(collected) >= limit:
                break
        return {
            "status": "ok",
            "subjects": subjects,
            "event_types": event_types,
            "hours": hours,
            "limit": limit,
            "count": len(collected),
            "events": collected,
        }

    def pull_metadata_bounded(
        self,
        access_point: str,
        timeout: float = 5.0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Bounded ``MetadataService.PullMetadata`` for a vmda / metadata source endpoint.

        Caps: ``timeout`` clamped to [1.0, 30.0] seconds, ``limit`` clamped to [1, 500] frames.
        """
        timeout = max(1.0, min(float(timeout), 30.0))
        limit = max(1, min(int(limit), 500))

        client = self.ensure_client()
        client.authenticate_grpc()
        meta_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
        media_pb2 = client.import_module("axxonsoft.bl.media.Media_pb2")
        stub = client.stub_from_proto("axxonsoft/bl/metadata/MetadataService.proto", "MetadataService")
        endpoint = media_pb2.EndpointRef(access_point=access_point)
        request = meta_pb2.PullMetadataRequest(count=limit, endpoint=endpoint)
        import time as _time
        deadline = _time.monotonic() + timeout
        frames: list[dict[str, Any]] = []
        try:
            iterator = stub.PullMetadata(iter([request]), timeout=timeout)
            for response in iterator:
                if _time.monotonic() > deadline or len(frames) >= limit:
                    break
                frames.append(client.sanitize(client.message_to_dict(response)))
        except Exception as exc:  # noqa: BLE001 — surface transport-layer failure to caller
            return {
                "status": "error",
                "access_point": access_point,
                "message": str(exc)[:240],
                "count": len(frames),
                "frames": frames,
            }
        return {
            "status": "ok",
            "access_point": access_point,
            "timeout": timeout,
            "limit": limit,
            "count": len(frames),
            "frames": frames[:limit],
        }

    def preflight_task(self, task: str) -> dict[str, Any]:
        normalized = task.lower()
        available: list[str] = []
        missing: list[str] = []

        if self.find_event_suppliers()["count"]:
            available.append("event_supplier")
        if self.find_metadata_endpoints()["count"]:
            available.append("metadata_endpoint")
        if self.list_cameras()["count"]:
            available.append("camera")
        if self.list_archives()["count"]:
            available.append("archive")
        if self.list_appdata_detectors()["count"]:
            available.append("appdata_detector")

        all_strings = "\n".join(flatten_strings(self.inventory()))
        if "ptz" in normalized or "tag" in normalized or "track" in normalized:
            if re.search(r"Telemetry|PTZ|TagAndTrack", all_strings, flags=re.IGNORECASE):
                available.append("ptz")
            else:
                missing.append("ptz")
        if "event" in normalized and "event_supplier" not in available:
            missing.append("event_supplier")
        if "metadata" in normalized and "metadata_endpoint" not in available:
            missing.append("metadata_endpoint")

        return {
            "task": task,
            "status": "blocked" if missing else "ready",
            "available": available,
            "missing": unique_strings(missing),
            "mode": "read-only-preflight",
        }

    def _summarize_collection(self, key: str, filter_text: str | None, limit: int) -> dict[str, Any]:
        return self._summarize_items(key, list(self.inventory().get(key, [])), filter_text, limit)

    def _summarize_items(
        self,
        kind: str,
        items: list[dict[str, Any]],
        filter_text: str | None,
        limit: int,
    ) -> dict[str, Any]:
        summaries = [summarize_unit(item, self.sanitize) for item in items]
        if filter_text:
            summaries = [item for item in summaries if includes(" ".join(map(str, item.values())), filter_text)]
        return {"kind": kind, "count": len(summaries), "items": summaries[:limit]}

    def _detector_items(self, detector_type: str, filter_text: str | None) -> list[dict[str, Any]]:
        items = []
        seen: set[str] = set()
        for item in flatten_dicts(self.inventory()):
            identity = str(first_present(item, "access_point", "accessPoint", "uid") or "")
            item_type = str(item.get("type", ""))
            if not identity and item_type != detector_type:
                continue
            haystack = " ".join([identity, item_type, str(item.get("display_name", "")), str(item.get("displayName", ""))])
            item_type = str(item.get("type", ""))
            if detector_type not in haystack and item_type != detector_type:
                continue
            if detector_type == "AVDetector" and "SourceEndpoint." in identity:
                continue
            if not includes(haystack, filter_text):
                continue
            dedupe_key = identity or f"{item_type}:{item.get('display_name', '')}:{len(items)}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(item)
        return items
