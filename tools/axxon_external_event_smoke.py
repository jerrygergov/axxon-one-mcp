#!/usr/bin/env python3
"""Controlled external detector event injection smoke with isolated fixture."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-external-event-smoke"

EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL = [
    "ConfigurationService.ChangeConfig.add_temp_appdata_detector",
    "ConfigurationService.ChangeConfig.add_temp_detector_ex",
    "ConfigurationService.ChangeConfig.add_temp_realtime_recognizer_external",
    "ExternalDetectorService.RaiseOccasionalEvent.temp_detector",
    "ExternalDetectorService.RaiseOccasionalEvent.explicit_access_point_probe",
    "EventHistoryService.ReadEvents.verify_temp_event",
    "ConfigurationService.ChangeConfig.remove_temp_external_fixture",
]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def temp_event_id() -> str:
    return "codex-external-event-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")


def prop_string(prop_id: str, value: str, *, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": prop_id, "value_string": value}
    if properties is not None:
        out["properties"] = properties
    return out


def prop_bool(prop_id: str, value: bool) -> dict[str, Any]:
    return {"id": prop_id, "value_bool": value}


def realtime_recognizer_external_properties(name: str) -> list[dict[str, Any]]:
    return [
        prop_bool("enabled", False),
        prop_string("display_name", name),
        prop_string("address", "127.0.0.1"),
        prop_string("port", "10111"),
    ]


def detector_ex_properties(name: str) -> list[dict[str, Any]]:
    return [
        prop_string("display_name", name),
        prop_bool("enabled", True),
    ]


def candidate_access_points(unit: dict[str, Any]) -> list[str]:
    uid = unit.get("uid", "")
    access_point = unit.get("access_point", "")
    candidates = []
    for item in [access_point, uid, f"{uid}/EventSupplier" if uid else ""]:
        if item and item not in candidates:
            candidates.append(item)
    return candidates


def unique_strings(items: list[str]) -> list[str]:
    out = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def detector_ex_probe_access_points(args: argparse.Namespace) -> list[str]:
    explicit = getattr(args, "access_point", None) or []
    if explicit:
        return unique_strings([str(item) for item in explicit])
    host = getattr(args, "tls_cn", "Server")
    return unique_strings(
        [
            "DetectorEx.1",
            f"hosts/{host}/DetectorEx.1",
            f"hosts/{host}/DetectorEx.1/EventSupplier",
        ]
    )


def first_added_uid(body: dict[str, Any], stage: str) -> str:
    added = body.get("added") or []
    if not added:
        raise RuntimeError(f"{stage} returned no uid: {body}")
    return str(added[0])


def occasional_http_body(access_point: str, event_type: str, timestamp: str, *, event_id: str | None = None) -> dict[str, Any]:
    event_id = event_id or temp_event_id()
    return {
        "accessPoint": access_point,
        "eventType": event_type,
        "timestamp": timestamp,
        "data": {
            "codex_marker": event_id,
            "source": "axxon_external_event_smoke",
        },
        "eventId": event_id,
        "eventState": "HAPPENED",
    }


class ExternalEventSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.created_uid = ""

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_http_grpc()

    def change_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.http_grpc("axxonsoft.bl.config.ConfigurationService.ChangeConfig", payload)
        if response.get("status") != 200:
            raise RuntimeError(f"ChangeConfig HTTP status {response.get('status')}")
        body = response.get("body") or {}
        if body.get("failed"):
            raise RuntimeError(f"ChangeConfig failed: {self.client.sanitize(body.get('failed_reason', []))}")
        return body

    def add_temp_detector(self) -> dict[str, Any]:
        if self.args.fixture_type == "access_point_probe":
            return self.external_access_point_probe()
        if self.args.fixture_type == "detector_ex":
            return self.add_temp_detector_ex()
        if self.args.fixture_type == "realtime_recognizer_external":
            return self.add_temp_realtime_recognizer_external()
        return self.add_temp_appdata_detector()

    def external_access_point_probe(self) -> dict[str, Any]:
        return {
            "body": {"added": [""]},
            "name": "explicit-access-point-probe",
            "unit_type": "access_point_probe",
            "unit": {},
            "event_supplier": "",
            "candidate_access_points": detector_ex_probe_access_points(self.args),
        }

    def add_temp_detector_ex(self) -> dict[str, Any]:
        name = "codex-temp-detector-ex-" + self.started_at.strftime("%H%M%S")
        body = self.change_config(
            {
                "added": [
                    {
                        "uid": f"hosts/{self.args.tls_cn}",
                        "units": [
                            {
                                "type": "DetectorEx",
                                "properties": detector_ex_properties(name),
                                "units": [],
                            }
                        ],
                    }
                ]
            }
        )
        self.created_uid = first_added_uid(body, "DetectorEx add")
        unit = self.read_unit(self.created_uid)
        return {"body": body, "name": name, "unit_type": "DetectorEx", "unit": unit, "event_supplier": self.event_supplier(), "candidate_access_points": candidate_access_points(unit)}

    def add_temp_appdata_detector(self) -> dict[str, Any]:
        name = "codex-temp-external-appdata-" + self.started_at.strftime("%H%M%S")
        body = self.change_config(
            {
                "added": [
                    {
                        "uid": f"hosts/{self.args.tls_cn}",
                        "units": [
                            {
                                "type": "AppDataDetector",
                                "properties": [
                                    prop_string("display_name", name),
                                    prop_string(
                                        "input",
                                        "TargetList",
                                        properties=[
                                            prop_string("camera_ref", self.args.video_source_ap, properties=[prop_string("streaming_id", self.args.vmda_source_ap)]),
                                            prop_string("detector", self.args.detector_type),
                                        ],
                                    ),
                                    prop_bool("enabled", True),
                                ],
                                "units": [],
                            }
                        ],
                    }
                ]
            }
        )
        self.created_uid = first_added_uid(body, "AppDataDetector add")
        unit = self.read_unit(self.created_uid)
        return {"body": body, "name": name, "unit_type": "AppDataDetector", "unit": unit, "event_supplier": self.event_supplier(), "candidate_access_points": candidate_access_points(unit)}

    def add_temp_realtime_recognizer_external(self) -> dict[str, Any]:
        name = "codex-temp-external-rre-" + self.started_at.strftime("%H%M%S")
        body = self.change_config(
            {
                "added": [
                    {
                        "uid": f"hosts/{self.args.tls_cn}",
                        "units": [
                            {
                                "type": "RealtimeRecognizerExternal",
                                "properties": realtime_recognizer_external_properties(name),
                                "units": [],
                            }
                        ],
                    }
                ]
            }
        )
        self.created_uid = first_added_uid(body, "RealtimeRecognizerExternal add")
        unit = self.read_unit(self.created_uid)
        return {"body": body, "name": name, "unit_type": "RealtimeRecognizerExternal", "unit": unit, "event_supplier": self.event_supplier(), "candidate_access_points": candidate_access_points(unit)}

    def remove_temp_detector(self) -> dict[str, Any]:
        if not self.created_uid:
            return {"skipped": True}
        uid = self.created_uid
        body = self.change_config({"removed": [{"uid": uid}]})
        self.created_uid = ""
        return body

    def event_supplier(self) -> str:
        return f"{self.created_uid}/EventSupplier"

    def read_unit(self, uid: str) -> dict[str, Any]:
        self.client.authenticate_grpc()
        pb2 = self.client.import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        response = self.client.common_stubs()["config"].ListUnits(
            pb2.ListUnitsRequest(unit_uids=[uid], display_mode=0),
            timeout=self.args.timeout,
        )
        data = self.client.message_to_dict(response)
        units = data.get("units", [])
        if not units:
            raise RuntimeError(f"unit not found after add: {uid}")
        return units[0]

    def raise_occasional_event(self, event_supplier: str, event_id: str) -> dict[str, Any]:
        timestamp = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
        body = occasional_http_body(event_supplier, self.args.event_type, timestamp, event_id=event_id)
        response = self.client.http_request("POST", "/v1/detectors/external:raiseOccasionalEvent", body, bearer=True)
        return {
            "status": response.get("status"),
            "body": response.get("body") or {},
            "event_id": event_id,
            "event_type": self.args.event_type,
            "timestamp": timestamp,
        }

    def read_matching_events(self, event_supplier: str, event_id: str) -> dict[str, Any]:
        self.client.authenticate_grpc()
        event_history_pb2 = self.client.import_module("axxonsoft.bl.events.EventHistory_pb2")
        events_pb2 = self.client.import_module("axxonsoft.bl.events.Events_pb2")
        primitive_pb2 = self.client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        stub = self.client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
        end = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=10)
        begin = self.started_at - dt.timedelta(seconds=10)
        request = event_history_pb2.ReadEventsRequest(
            range=primitive_pb2.TimeRange(begin_time=self.axxon_ts(begin), end_time=self.axxon_ts(end)),
            node_descriptions=[event_history_pb2.NodeDescription(node_name=self.args.tls_cn)],
            filters=event_history_pb2.SearchFilterArray(
                filters=[
                    event_history_pb2.SearchFilter(
                        type=int(events_pb2.ET_DetectorEvent),
                        subjects=[event_supplier],
                        values=[event_id],
                        texts=[event_id],
                    )
                ]
            ),
            descending=True,
        )
        pages = 0
        matches = 0
        unreachable: list[str] = []
        samples: list[dict[str, Any]] = []
        for page in stub.ReadEvents(request, timeout=self.args.timeout):
            pages += 1
            data = self.client.message_to_dict(page)
            unreachable.extend(data.get("unreachable_subjects", []))
            for item in data.get("items", []):
                text = json.dumps(item, sort_keys=True)
                if event_id in text:
                    matches += 1
                    if len(samples) < 3:
                        samples.append(self.event_summary(item))
            if pages >= self.args.max_event_pages:
                break
        return {"pages": pages, "matches": matches, "unreachable_subjects": sorted(set(unreachable)), "samples": samples}

    def event_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        event = item.get("event", {})
        detector = event.get("detector", {})
        return {
            "event_type": event.get("event_type"),
            "state": event.get("state"),
            "detector_ref": detector.get("ref") or detector.get("name") or detector.get("access_point"),
            "keys": sorted(event.keys())[:20],
        }

    def run_lifecycle(self) -> tuple[str, dict[str, Any]]:
        added = self.add_temp_detector()
        attempts = []
        verification = {"skipped": "raise response was not OK"}
        status = "WARN"
        accepted = {}
        for event_supplier in added["candidate_access_points"]:
            event_id = temp_event_id()
            raised = self.raise_occasional_event(event_supplier, event_id)
            attempts.append({"access_point": event_supplier, "raise_event": self.client.sanitize(raised)})
            time.sleep(max(0, self.args.event_wait_seconds))
            body = raised.get("body") or {}
            if raised.get("status") == 200 and body.get("error") in (None, 0, "OK", "RaiseEventError.OK"):
                verification = self.read_matching_events(event_supplier, event_id)
                status = "PASS" if verification.get("matches", 0) > 0 else "WARN"
                accepted = {"access_point": event_supplier, "event_id": event_id}
                break
        removed = self.remove_temp_detector()
        return status, {
            "detector_uid": added["body"].get("added", [""])[0],
            "fixture_type": added["unit_type"],
            "candidate_access_points": added["candidate_access_points"],
            "attempts": attempts,
            "accepted": accepted,
            "verification": verification,
            "remove_response_keys": sorted(removed.keys()),
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        if self.created_uid:
            uid = self.created_uid
            try:
                body = self.remove_temp_detector()
                cleanup_results.append({"uid": uid, "status": "detector_removed", "body_keys": sorted(body.keys())})
            except Exception as exc:
                cleanup_results.append({"uid": uid, "status": "detector_cleanup_failed", "error": str(exc)[:400]})
        return cleanup_results

    def run(self) -> dict[str, Any]:
        self.setup()
        start = time.perf_counter()
        try:
            status, details = self.run_lifecycle()
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "FAIL"
        cleanup_results = self.cleanup()
        if cleanup_results:
            details["cleanup"] = cleanup_results
        self.results.append({"group": "external_event_lifecycle", "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details})
        report = self.report()
        self.write_report(report)
        return report

    def axxon_ts(self, value: dt.datetime) -> str:
        return value.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S.%f")[:-3]

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "approval_only_operations": EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL,
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"external-event-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"external-event-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "external-event-smoke-latest.json"
        latest_md = self.args.report_dir / "external-event-smoke-latest.md"
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
            "# Axxon One External Event Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            "",
            "Creates a temporary external-event fixture or probes explicit access points, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes any temporary fixture.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            attempts = details.get("attempts", [])
            raised = attempts[-1].get("raise_event", {}) if attempts else {}
            verification = details.get("verification", {})
            note = f"fixture={details.get('detector_uid')} type={details.get('fixture_type')} attempts={len(attempts)} last_status={raised.get('status')} matches={verification.get('matches')}"
            if details.get("error"):
                note = details["error"]
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:240]} |")
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--video-source-ap", default="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
    parser.add_argument("--vmda-source-ap", default="hosts/Server/AVDetector.1/SourceEndpoint.vmda")
    parser.add_argument("--detector-type", default="MoveInZone")
    parser.add_argument("--fixture-type", choices=["appdata_detector", "access_point_probe", "detector_ex", "realtime_recognizer_external"], default="appdata_detector")
    parser.add_argument("--access-point", action="append", default=[])
    parser.add_argument("--event-type", default="moveInZone")
    parser.add_argument("--event-wait-seconds", type=float, default=1.0)
    parser.add_argument("--max-event-pages", type=int, default=5)
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not mutation_approved(args):
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def main() -> int:
    smoke = ExternalEventSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
