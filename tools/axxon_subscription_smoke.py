#!/usr/bin/env python3
"""Bounded smoke checks for legacy WebSocket and gRPC event subscriptions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


def subscription_modes() -> list[str]:
    return ["websocket_camera_events", "websocket_camera_track", "grpc_event_subscription"]


EVENT_TYPE_ALIASES = {
    "detector": "ET_DetectorEvent",
    "camera": "ET_CameraChangedEvent",
    "config": "ET_ConfigChangedEvent",
    "object": "ET_ObjectActivatedEvent",
    "alert": "ET_Alert",
    "bookmark": "ET_Bookmark",
    "macro": "ET_MacroEvent",
    "service": "ET_ServiceStatus",
}


def event_type_number(events_pb2: Any, value: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    if raw.isdigit():
        return int(raw)
    name = EVENT_TYPE_ALIASES.get(raw.casefold(), raw)
    if not name.startswith("ET_"):
        name = f"ET_{name}"
    if not hasattr(events_pb2, name):
        raise ValueError(f"unknown event type: {value}")
    return int(getattr(events_pb2, name))


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


def build_pull_event_filters(
    notify_pb2: Any,
    events_pb2: Any,
    *,
    subjects: list[str],
    event_types: list[str],
    current_node_events_only: bool = False,
) -> Any:
    include = []
    clean_subjects = unique(subjects)
    type_numbers = [event_type_number(events_pb2, value) for value in unique(event_types)]
    if not type_numbers and clean_subjects:
        type_numbers = [0]
    if type_numbers:
        for number in type_numbers:
            if clean_subjects:
                for subject in clean_subjects:
                    include.append(
                        notify_pb2.EventFilter(
                            event_type=number,
                            subject=subject,
                            current_node_events_only=current_node_events_only,
                        )
                    )
            else:
                include.append(
                    notify_pb2.EventFilter(
                        event_type=number,
                        current_node_events_only=current_node_events_only,
                    )
                )
    return notify_pb2.EventFilters(include=include)


def build_websocket_url(http_url: str, username: str, password: str, *, schema: str = "") -> str:
    parts = urlsplit(http_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}"
    netloc = f"{userinfo}@{parts.hostname or parts.netloc}"
    if parts.port:
        netloc = f"{userinfo}@{parts.hostname}:{parts.port}"
    path = (parts.path.rstrip("/") if parts.path else "") + "/events"
    query = f"schema={quote(schema, safe='')}" if schema else ""
    return urlunsplit((scheme, netloc, path, query, ""))


def camera_device_ap(camera_source_ap: str) -> str:
    marker = "/SourceEndpoint."
    if marker in camera_source_ap:
        return camera_source_ap.split(marker, 1)[0]
    return camera_source_ap


class SubscriptionSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.fixtures: dict[str, str] = {}
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        inventory = self.client.load_inventory()
        camera = next((item for item in inventory.get("cameras", []) if item.get("access_point")), {})
        subjects = unique(list(self.args.subject or []))
        if self.args.use_camera_fixture and camera.get("access_point"):
            subjects.append(camera["access_point"])
            subjects = unique(subjects)
        camera_ap = camera.get("access_point", "")
        self.fixtures = {"camera_ap": camera_ap, "camera_device_ap": camera_device_ap(camera_ap), "subjects": subjects}

    def selected_modes(self) -> list[str]:
        if not self.args.mode:
            return subscription_modes()
        wanted = set(self.args.mode)
        return [mode for mode in subscription_modes() if mode in wanted]

    def run_websocket_command(self, command: dict[str, Any]) -> dict[str, Any]:
        if not self.fixtures.get("camera_ap"):
            return {"status": "WARN", "details": {"reason": "missing camera fixture"}}
        try:
            import websocket
        except Exception as exc:
            return {
                "status": "SKIP",
                "details": {
                    "reason": "websocket-client is not installed",
                    "error_type": exc.__class__.__name__,
                },
            }

        ws_url = build_websocket_url(self.args.http_url, self.args.username, self.args.password, schema=self.args.websocket_schema)
        ws = None
        received = 0
        first_shape: Any = None
        stage = "connect"
        try:
            ws = websocket.create_connection(
                ws_url,
                timeout=self.args.duration,
            )
            stage = "send"
            ws.send(json.dumps(command))
            stage = "receive"
            deadline = time.monotonic() + self.args.duration
            while received < self.args.max_events and time.monotonic() < deadline:
                ws.settimeout(max(0.2, deadline - time.monotonic()))
                message = ws.recv()
                if not message:
                    continue
                received += 1
                if first_shape is None:
                    try:
                        first_shape = self.client.shape(json.loads(message))
                    except json.JSONDecodeError:
                        first_shape = {"type": "str", "present": True}
            return {
                "status": "PASS" if received else "WARN",
                "details": {"events": received, "first_shape": first_shape, "stage": stage, "schema": self.args.websocket_schema},
            }
        except Exception as exc:
            error_text = str(exc)
            code_name = ""
            try:
                code_name = exc.code().name
            except Exception:
                code_name = ""
            if code_name == "DEADLINE_EXCEEDED" or "DEADLINE_EXCEEDED" in error_text or "Deadline Exceeded" in error_text:
                return {
                    "status": "WARN",
                    "details": {"reason": "no events before deadline", "events": received, "stage": stage, "schema": self.args.websocket_schema},
                }
            return {
                "status": "WARN",
                "details": {"error_type": exc.__class__.__name__, "error": error_text[:800], "stage": stage, "schema": self.args.websocket_schema},
            }
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    def run_websocket_camera_events(self) -> dict[str, Any]:
        include = self.fixtures.get("subjects") or [self.fixtures["camera_ap"]]
        return self.run_websocket_command({"include": include, "exclude": []})

    def run_websocket_camera_track(self) -> dict[str, Any]:
        subject = self.fixtures.get("camera_device_ap") or self.fixtures.get("camera_ap", "")
        return self.run_websocket_command({"track": [subject]})

    def run_grpc_event_subscription(self) -> dict[str, Any]:
        subscription_id = f"codex-{uuid.uuid4()}"
        received = 0
        first_shape: Any = None
        try:
            self.client.authenticate_grpc()
            notify_pb2 = self.client.import_module("axxonsoft.bl.events.Notification_pb2")
            events_pb2 = self.client.import_module("axxonsoft.bl.events.Events_pb2")
            notify = self.client.stub_from_proto("axxonsoft/bl/events/Notification.proto", "DomainNotifier")
            filters = build_pull_event_filters(
                notify_pb2,
                events_pb2,
                subjects=list(self.fixtures.get("subjects", [])),
                event_types=list(self.args.event_type or []),
                current_node_events_only=self.args.current_node_events_only,
            )
            request = notify_pb2.PullEventsRequest(subscription_id=subscription_id, filters=filters)
            try:
                for event_page in notify.PullEvents(request, timeout=self.args.duration):
                    data = self.client.message_to_dict(event_page)
                    page_count = len(data.get("items", []))
                    received += page_count
                    if first_shape is None:
                        first_shape = self.client.shape(data)
                    if received >= self.args.max_events:
                        break
            finally:
                try:
                    notify.DisconnectEventChannel(
                        notify_pb2.DisconnectEventChannelRequest(subscription_id=subscription_id),
                        timeout=2,
                    )
                except Exception:
                    pass
            return {
                "status": "PASS" if received else "WARN",
                "details": {
                    "events": received,
                    "first_shape": first_shape,
                    "subjects": list(self.fixtures.get("subjects", [])),
                    "event_types": list(self.args.event_type or []),
                },
            }
        except Exception as exc:
            error_text = str(exc)
            code_name = ""
            try:
                code_name = exc.code().name
            except Exception:
                code_name = ""
            if code_name == "DEADLINE_EXCEEDED" or "DEADLINE_EXCEEDED" in error_text or "Deadline Exceeded" in error_text:
                return {
                    "status": "WARN",
                    "details": {"reason": "no events before deadline", "events": received},
                }
            return {
                "status": "WARN",
                "details": {"error_type": exc.__class__.__name__, "error": error_text[:800]},
            }

    def invoke(self, mode: str) -> dict[str, Any]:
        start = time.perf_counter()
        if mode == "websocket_camera_events":
            outcome = self.run_websocket_camera_events()
        elif mode == "websocket_camera_track":
            outcome = self.run_websocket_camera_track()
        elif mode == "grpc_event_subscription":
            outcome = self.run_grpc_event_subscription()
        else:
            outcome = {"status": "WARN", "details": {"reason": "unknown mode"}}
        return {
            "mode": mode,
            "status": outcome["status"],
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": outcome.get("details", {}),
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        for mode in self.selected_modes():
            self.results.append(self.invoke(mode))
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "SKIP": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "http_url": self.args.http_url,
                "grpc_target": f"{self.args.host}:{self.args.grpc_port}",
                "username": self.args.username,
                "password": "<redacted>",
            },
            "selection": {
                "modes": self.selected_modes(),
                "duration_seconds": self.args.duration,
                "max_events": self.args.max_events,
                "subjects": list(self.fixtures.get("subjects", [])),
                "event_types": list(self.args.event_type or []),
                "current_node_events_only": self.args.current_node_events_only,
            },
            "fixtures": self.fixtures,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"subscription-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"subscription-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "subscription-smoke-latest.json"
        latest_md = self.args.report_dir / "subscription-smoke-latest.md"
        json_text = json.dumps(self.client.sanitize(report), indent=2, ensure_ascii=True) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        latest_json.write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(report)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Subscription Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Mode | ms | Notes |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = details.get("reason") or details.get("error") or f"events={details.get('events', 0)}"
            if details.get("stage"):
                note = f"{note}; stage={details.get('stage')}; schema={details.get('schema', '')}"
            note_text = " ".join(str(note).split())[:180].replace("|", "\\|")
            lines.append(f"| {result['status']} | `{result['mode']}` | {result['elapsed_ms']} | {note_text} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--mode", action="append", choices=subscription_modes())
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--max-events", type=int, default=5)
    parser.add_argument("--subject", action="append", default=[], help="Event subject/access point filter.")
    parser.add_argument("--event-type", action="append", default=[], help="gRPC event type name, number, or alias.")
    parser.add_argument("--use-camera-fixture", action="store_true", help="Add the first inventory camera as a subject filter.")
    parser.add_argument("--current-node-events-only", action="store_true", help="Set current_node_events_only in filters.")
    parser.add_argument("--websocket-schema", default="proto", help="Optional /events schema query parameter; PDF examples use proto.")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    smoke = SubscriptionSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
