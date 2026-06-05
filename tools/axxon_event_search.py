#!/usr/bin/env python3
"""Search Axxon One event history through direct gRPC.

Credentials are read from environment variables or CLI args. The tool does not
write credentials or bearer tokens to output files.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
from typing import Any

from axxon_api_client import AxxonApiClient, config_from_args
from axxon_api_client import add_common_args


EVENT_TYPE_ALIASES = {
    "detector": "ET_DetectorEvent",
    "integrity": "ET_IntegrityEvent",
    "service": "ET_ServiceStatus",
    "service_status": "ET_ServiceStatus",
    "config": "ET_ConfigChangedEvent",
    "config_changed": "ET_ConfigChangedEvent",
    "host": "ET_HostStatusChangedEvent",
    "host_status": "ET_HostStatusChangedEvent",
    "object": "ET_ObjectActivatedEvent",
    "object_activated": "ET_ObjectActivatedEvent",
    "alert": "ET_Alert",
    "bookmark": "ET_Bookmark",
    "lpr": "ET_DetectorEvent",
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def parse_datetime(value: str) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty datetime")
    formats = (
        "%Y%m%dT%H%M%S.%f",
        "%Y%m%dT%H%M%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(text.replace("Z", "+0000"), fmt)
            break
        except ValueError:
            parsed = None
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"unsupported datetime: {value}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def axxon_ts(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S.%f")


def compact_counter(counter: Counter[str], limit: int = 8) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, count in counter.most_common(limit):
        out[key] = count
    return out


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


class AxxonEventSearch:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.pb: dict[str, Any] = {}
        self.cameras: list[dict[str, Any]] = []
        self.node_name = ""

    def setup(self) -> None:
        self.client.authenticate_grpc()
        modules = {
            "domain_pb2": "axxonsoft.bl.domain.Domain_pb2",
            "event_history_pb2": "axxonsoft.bl.events.EventHistory_pb2",
            "events_pb2": "axxonsoft.bl.events.Events_pb2",
            "primitive_pb2": "axxonsoft.bl.primitive.Primitives_pb2",
            # ExportEvent bodies arrive as Any "body" values; register the type so message_to_dict
            # can decode export-bearing pages instead of raising on the missing descriptor.
            "export_event_pb2": "axxonsoft.bl.mmexport.ExportEvent_pb2",
        }
        for key, module in modules.items():
            self.pb[key] = self.client.import_module(module)

    def msg(self, message) -> dict[str, Any]:
        return self.client.message_to_dict(message)

    def stubs(self) -> tuple[Any, Any]:
        domain = self.client.stub_from_proto("axxonsoft/bl/domain/Domain.proto", "DomainService")
        events = self.client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
        return domain, events

    def load_inventory(self) -> None:
        inventory = self.client.load_inventory()
        nodes = inventory.get("nodes", [])
        self.node_name = self.args.node or (nodes[0].get("node_name") if nodes else self.args.tls_cn)
        self.cameras = inventory.get("cameras", [])

    def time_range(self):
        if self.args.begin or self.args.end:
            if not (self.args.begin and self.args.end):
                raise ValueError("use both --begin and --end, or use --hours")
            begin = parse_datetime(self.args.begin)
            end = parse_datetime(self.args.end)
        else:
            end = utc_now()
            begin = end - dt.timedelta(hours=float(self.args.hours))
        if begin > end:
            raise ValueError("begin must be before end")
        return self.pb["primitive_pb2"].TimeRange(
            begin_time=axxon_ts(begin),
            end_time=axxon_ts(end),
        )

    def event_type_number(self, value: str) -> int:
        raw = str(value or "").strip()
        if not raw:
            return 0
        name = EVENT_TYPE_ALIASES.get(raw.casefold(), raw)
        if name.isdigit():
            return int(name)
        if not name.startswith("ET_") and hasattr(self.pb["events_pb2"], f"ET_{name}"):
            name = f"ET_{name}"
        if not hasattr(self.pb["events_pb2"], name):
            raise ValueError(f"unknown event type: {value}")
        return int(getattr(self.pb["events_pb2"], name))

    def event_type_name(self, number: int) -> str:
        descriptor = self.pb["events_pb2"].EEventType.DESCRIPTOR
        value = descriptor.values_by_number.get(int(number))
        return value.name if value else str(number)

    def resolve_camera_subjects(self) -> list[str]:
        subjects = list(self.args.subject or [])
        subjects.extend(self.args.camera_ap or [])
        if not self.args.camera:
            return unique(subjects)

        indexed: list[tuple[dict[str, Any], set[str]]] = []
        for camera in self.cameras:
            display_id = str(camera.get("display_id") or "").strip()
            display_name = str(camera.get("display_name") or "").strip()
            ap = str(camera.get("access_point") or "").strip()
            labels = {
                display_id.casefold(),
                display_name.casefold(),
                f"{display_id}.{display_name}".casefold(),
                ap.casefold(),
            }
            indexed.append((camera, labels))

        unresolved: list[str] = []
        for raw_query in self.args.camera:
            query = str(raw_query or "").strip()
            key = query.casefold()
            matches = [
                camera
                for camera, labels in indexed
                if key in labels or any(key and key in label for label in labels)
            ]
            if not matches:
                unresolved.append(query)
                continue
            subjects.extend(str(camera.get("access_point") or "") for camera in matches)
        if unresolved:
            raise ValueError(f"camera not found: {', '.join(unresolved)}")
        return unique(subjects)

    def build_search_filters(self) -> list[Any]:
        subjects = self.resolve_camera_subjects()
        subjects.extend(self.args.detector_ap or [])
        subjects = unique(subjects)
        values = unique(list(self.args.value or []))
        texts = unique(list(self.args.text or []))

        event_types = list(self.args.event_type or [])
        for category in self.args.category or []:
            if category.casefold() == "lpr":
                continue
            event_types.append(category)
        event_type_numbers = [self.event_type_number(value) for value in event_types]

        filters = []
        if event_type_numbers:
            for number in event_type_numbers:
                filters.append(
                    self.pb["event_history_pb2"].SearchFilter(
                        type=number,
                        subjects=subjects,
                        values=values,
                        texts=texts,
                    )
                )
        elif subjects or values or texts:
            filters.append(
                self.pb["event_history_pb2"].SearchFilter(
                    subjects=subjects,
                    values=values,
                    texts=texts,
                )
            )
        return filters

    def count_general(self, events, range_pb, filters: list[Any]) -> int:
        request = self.pb["event_history_pb2"].ReadCountRequest(
            range=range_pb,
            node_description=self.pb["event_history_pb2"].NodeDescription(node_name=self.node_name),
        )
        request.filters.filters.extend(filters)
        total = 0
        for page in events.ReadCount(request, timeout=self.args.timeout):
            total += int(self.msg(page).get("count", 0))
        return total

    def read_general(self, events, range_pb, filters: list[Any]) -> list[dict[str, Any]]:
        request = self.pb["event_history_pb2"].ReadEventsRequest(
            range=range_pb,
            limit=max(1, self.args.limit),
            descending=not self.args.ascending,
            node_descriptions=[self.pb["event_history_pb2"].NodeDescription(node_name=self.node_name)],
        )
        request.filters.filters.extend(filters)
        rows: list[dict[str, Any]] = []
        for page in events.ReadEvents(request, timeout=self.args.timeout):
            rows.extend(self.msg(page).get("items", []))
            if len(rows) >= self.args.limit:
                break
        return rows[: self.args.limit]

    def read_lpr(self, events, range_pb) -> list[dict[str, Any]]:
        subjects = self.resolve_camera_subjects()
        values = unique(list(self.args.value or []) + list(self.args.plate or []))
        texts = unique(list(self.args.text or []))
        request = self.pb["event_history_pb2"].ReadLprEventsRequest(
            range=range_pb,
            limit=max(1, self.args.limit),
            descending=not self.args.ascending,
            search_predicate=self.args.predicate or "",
            node_descriptions=[self.pb["event_history_pb2"].NodeDescription(node_name=self.node_name)],
        )
        request.filters.filters.append(
            self.pb["event_history_pb2"].LprSearchFilter(
                subjects=subjects,
                values=values,
                texts=texts,
            )
        )
        rows: list[dict[str, Any]] = []
        for page in events.ReadLprEvents(request, timeout=self.args.timeout):
            rows.extend(self.msg(page).get("items", []))
            if len(rows) >= self.args.limit:
                break
        return rows[: self.args.limit]

    def read_alerts(self, events, range_pb) -> list[dict[str, Any]]:
        request = self.pb["event_history_pb2"].ReadAlertsRequest(
            range=range_pb,
            limit=max(1, self.args.limit),
            descending=not self.args.ascending,
            node_descriptions=[self.pb["event_history_pb2"].NodeDescription(node_name=self.node_name)],
        )
        request.filters.filters.append(
            self.pb["event_history_pb2"].AlertsSearchFilter(
                subjects=self.resolve_camera_subjects(),
                values=unique(list(self.args.value or [])),
                texts=unique(list(self.args.text or [])),
            )
        )
        rows: list[dict[str, Any]] = []
        for page in events.ReadAlerts(request, timeout=self.args.timeout):
            rows.extend(self.msg(page).get("items", []))
            if len(rows) >= self.args.limit:
                break
        return rows[: self.args.limit]

    def run(self) -> dict[str, Any]:
        self.setup()
        _domain, events = self.stubs()
        self.load_inventory()

        range_pb = self.time_range()
        filters = self.build_search_filters()
        mode = self.mode()

        total_count = None
        if mode == "events":
            total_count = self.count_general(events, range_pb, filters)
            rows = self.read_general(events, range_pb, filters)
        elif mode == "lpr":
            rows = self.read_lpr(events, range_pb)
        elif mode == "alerts":
            rows = self.read_alerts(events, range_pb)
        else:
            raise ValueError(f"unsupported mode: {mode}")

        cards = [self.normalize_event(row) for row in rows]
        result = {
            "target": {
                "host": self.args.host,
                "grpc_port": self.args.grpc_port,
                "tls_cn": self.args.tls_cn,
                "node": self.node_name,
            },
            "request": {
                "mode": mode,
                "begin_time": range_pb.begin_time,
                "end_time": range_pb.end_time,
                "limit": self.args.limit,
                "descending": not self.args.ascending,
                "event_types": [self.event_type_name(f.type) for f in filters if f.type],
                "subjects": unique([subject for f in filters for subject in f.subjects]),
                "values": unique([value for f in filters for value in f.values]),
                "texts": unique([text for f in filters for text in f.texts]),
                "lpr_predicate": self.args.predicate or "",
            },
            "summary": self.summarize(cards, total_count),
            "items": cards,
        }
        if self.args.save:
            self.args.save.parent.mkdir(parents=True, exist_ok=True)
            self.args.save.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return result

    def mode(self) -> str:
        categories = {str(value or "").casefold() for value in self.args.category or []}
        if self.args.lpr or self.args.plate or self.args.predicate or "lpr" in categories:
            return "lpr"
        if self.args.alerts or "alert" in categories:
            return "alerts"
        return "events"

    def summarize(self, cards: list[dict[str, Any]], total_count: int | None) -> dict[str, Any]:
        return {
            "total_count": total_count,
            "returned": len(cards),
            "by_event_type": compact_counter(Counter(card.get("event_type", "") for card in cards)),
            "by_category": compact_counter(Counter(card.get("category", "") for card in cards)),
            "by_state": compact_counter(Counter(card.get("state", "") for card in cards)),
            "by_camera": compact_counter(Counter(card.get("camera", "") for card in cards)),
            "by_detector": compact_counter(Counter(card.get("detector", "") for card in cards)),
        }

    def normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        body = event.get("body", {}) or {}
        localization = str(((event.get("localization") or {}).get("text")) or "").strip()
        body_event_type = str(body.get("event_type") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        timestamp = str(body.get("timestamp") or "").strip()
        subjects = [str(value) for value in event.get("subjects", [])]

        origin_ext = body.get("origin_ext") or {}
        detector_ext = body.get("detector_ext") or {}
        camera_ap = str(origin_ext.get("access_point") or body.get("origin_deprecated") or "").strip()
        if not camera_ap:
            camera_ap = next(
                (
                    subject
                    for subject in subjects
                    if "/SourceEndpoint.video" in subject or "/DeviceIpint." in subject
                ),
                "",
            )
        detector_ap = str(detector_ext.get("access_point") or body.get("detector_deprecated") or "").strip()
        camera = str(
            origin_ext.get("friendly_name")
            or origin_ext.get("display_name")
            or self.camera_name(camera_ap)
            or camera_ap
            or "Camera"
        ).strip()
        detector = str(
            detector_ext.get("friendly_name")
            or detector_ext.get("display_name")
            or body.get("detector_deprecated")
            or body_event_type
            or event.get("event_name")
            or ""
        ).strip()
        groups = [str(value) for value in body.get("detectors_group", [])]
        category = self.category_for(event_type, body_event_type, groups, localization)
        plate = self.extract_plate(body, localization)
        return {
            "id": body.get("guid") or event.get("guid"),
            "timestamp": timestamp,
            "event_type": event_type,
            "event_name": event.get("event_name"),
            "category": category,
            "state": body.get("state"),
            "camera": camera,
            "camera_access_point": camera_ap,
            "detector": detector,
            "detector_access_point": detector_ap,
            "detector_event_type": body_event_type,
            "detectors_group": groups,
            "plate": plate,
            "subjects": subjects,
            "text": self.operator_text(localization, body_event_type),
            "localization_text": localization,
            "body_type": body.get("@type"),
        }

    def camera_name(self, access_point: str) -> str:
        if not access_point:
            return ""
        for camera in self.cameras:
            if camera.get("access_point") == access_point:
                display_id = str(camera.get("display_id") or "").strip()
                display_name = str(camera.get("display_name") or "").strip()
                return f"{display_id}.{display_name}".strip(".")
        return ""

    @staticmethod
    def category_for(event_type: str, body_event_type: str, groups: list[str], localization: str) -> str:
        if event_type == "ET_Alert":
            return "alert"
        if event_type == "ET_IntegrityEvent":
            return "integrity"
        if event_type in {"ET_ServiceStatus", "ET_HostStatusChangedEvent"}:
            return "status"
        lowered = f"{body_event_type} {localization}".casefold()
        group_set = set(groups)
        if "DG_LPR_DETECTOR" in group_set or "lpr" in lowered or "plate" in lowered:
            return "lpr"
        if "DG_FACE_DETECTOR" in group_set or "face" in lowered:
            return "face"
        if "DG_VEHICLE_DETECTOR" in group_set or "vehicle" in lowered:
            return "vehicle"
        if "DG_SITUATION_DETECTOR" in group_set:
            return "situation"
        if event_type == "ET_DetectorEvent":
            return "detector"
        return "other"

    @staticmethod
    def operator_text(localization: str, body_event_type: str) -> str:
        text = re.sub(r"\s+", " ", localization).strip()
        match = re.search(r'Event name\s+"([^"]+)"', text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        if text:
            return text[:240]
        return body_event_type

    @staticmethod
    def extract_plate(body: dict[str, Any], localization: str) -> str | None:
        data = body.get("data", {}) or {}
        hypotheses = data.get("Hypotheses") or data.get("hypotheses") or []
        for item in hypotheses:
            if not isinstance(item, dict):
                continue
            plate = item.get("PlateFull") or item.get("plate_full") or item.get("plate")
            if plate:
                return str(plate).strip()
        if data.get("plate"):
            return str(data["plate"]).strip()
        for detail in body.get("details") or []:
            if not isinstance(detail, dict):
                continue
            listed = ((detail.get("listed_item_detected_result") or {}).get("listed_plate_info") or {}).get("plate")
            if listed:
                return str(listed).strip()
            for key in ("auto_recognition_result", "auto_recognition_result_ex"):
                auto = detail.get(key) or {}
                for item in auto.get("hypotheses") or []:
                    if isinstance(item, dict) and (item.get("plate_full") or item.get("plate")):
                        return str(item.get("plate_full") or item.get("plate")).strip()
        match = re.search(r"\bLP\s+\"?([A-Z0-9-]{3,16})\"?", localization, flags=re.IGNORECASE)
        return match.group(1).upper() if match else None


def print_text(result: dict[str, Any], raw: bool = False) -> None:
    target = result["target"]
    request = result["request"]
    summary = result["summary"]
    print(f"Target: {target['host']}:{target['grpc_port']} node={target['node']}")
    print(f"Range: {request['begin_time']} -> {request['end_time']}")
    print(f"Mode: {request['mode']} limit={request['limit']} descending={request['descending']}")
    if request["event_types"]:
        print("Event types:", ", ".join(request["event_types"]))
    if request["subjects"]:
        print("Subjects:", ", ".join(request["subjects"]))
    if request["texts"]:
        print("Texts:", ", ".join(request["texts"]))
    if request["values"]:
        print("Values:", ", ".join(request["values"]))
    if request["lpr_predicate"]:
        print("LPR predicate:", request["lpr_predicate"])
    print("")
    if summary["total_count"] is not None:
        print(f"Total count: {summary['total_count']}")
    print(f"Returned: {summary['returned']}")
    for label in ("by_event_type", "by_category", "by_state", "by_camera", "by_detector"):
        values = summary.get(label) or {}
        if values:
            print(f"{label}: {values}")
    print("")
    for index, item in enumerate(result["items"], 1):
        plate = f" plate={item['plate']}" if item.get("plate") else ""
        print(
            f"{index:02d}. {item.get('timestamp') or '-'} "
            f"{item.get('event_type')} {item.get('category')} {item.get('state') or '-'}{plate}"
        )
        print(f"    camera={item.get('camera') or '-'}")
        if item.get("detector"):
            print(f"    detector={item['detector']}")
        if item.get("text"):
            print(f"    text={item['text']}")
        if raw:
            print("    raw=" + json.dumps(item, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--node", default=os.getenv("AXXON_NODE", ""))
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--begin", help="UTC begin time, e.g. 20260426T120000 or 2026-04-26T12:00:00Z")
    parser.add_argument("--end", help="UTC end time, e.g. 20260426T130000 or 2026-04-26T13:00:00Z")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--ascending", action="store_true")
    parser.add_argument("--event-type", action="append", default=[], help="Event enum name or alias, e.g. ET_DetectorEvent, detector, integrity")
    parser.add_argument("--category", action="append", default=[], help="Alias: detector, integrity, alert, lpr, service, config, host")
    parser.add_argument("--subject", action="append", default=[], help="Subject/access point filter")
    parser.add_argument("--camera", action="append", default=[], help="Camera display name/id/access point to resolve")
    parser.add_argument("--camera-ap", action="append", default=[], help="Camera access point filter")
    parser.add_argument("--detector-ap", action="append", default=[], help="Detector/event supplier access point filter")
    parser.add_argument("--value", action="append", default=[], help="Exact event value filter")
    parser.add_argument("--text", action="append", default=[], help="Partial text filter")
    parser.add_argument("--alerts", action="store_true", help="Use ReadAlerts")
    parser.add_argument("--lpr", action="store_true", help="Use ReadLprEvents")
    parser.add_argument("--plate", action="append", default=[], help="Exact LPR plate value for ReadLprEvents")
    parser.add_argument("--predicate", default="", help="LPR search_predicate, e.g. *82*")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text summary")
    parser.add_argument("--raw", action="store_true", help="Include normalized item JSON in text output")
    parser.add_argument("--save", type=Path, help="Save JSON result to file")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    tool = AxxonEventSearch(args)
    result = tool.run()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result, raw=args.raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
