"""One-shot probe: does the stand persist queryable VMDA tracks and events for camera 1?

Reports, for the discovered camera and its VMDA source:
- archive calendar / intervals present now (recording proof)
- EventHistory ReadCount over a recent window
- vmda_query result count over a recent window

Read-only. Credentials come from env. Used to confirm the stand-side fixture state before
and after enabling archiving/recording, to unblock the archived-events + vmda_query gap.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args
from axxon_mcp_operator_smoke import discover_inventory
from axxon_mcp_metadata import AxxonMcpMetadata


def event_count(client: AxxonApiClient, hours: float) -> dict:
    """Total EventHistory ReadCount across the recent window (streamed response)."""
    client.authenticate_grpc()
    ev_pb2 = client.import_module("axxonsoft.bl.events.EventHistory_pb2")
    primitive_pb2 = client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
    stub = client.stub_from_proto("axxonsoft/bl/events/EventHistory.proto", "EventHistoryService")
    now = dt.datetime.utcnow()
    begin = (now - dt.timedelta(hours=hours)).strftime("%Y%m%dT%H%M%S.000000Z")
    end = (now + dt.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S.000000Z")
    rng = primitive_pb2.TimeRange(begin_time=begin, end_time=end)
    req = ev_pb2.ReadCountRequest(range=rng)
    total = 0
    for page in stub.ReadCount(req, timeout=client.config.timeout):
        total += client.message_to_dict(page).get("count", 0)
    return {"total_count": total, "window_hours": hours}


def archive_state(client: AxxonApiClient, source_ap: str, archive_ap: str, hours: float) -> dict:
    """Calendar days plus a bounded interval count for the source/archive pair."""
    cal = client.archive_calendar(source_ap, archive_ap)
    now = dt.datetime.utcnow()
    begin = (now - dt.timedelta(hours=hours)).strftime("%Y%m%dT%H%M%S.000000Z")
    end = (now + dt.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S.000000Z")
    legacy = source_ap.replace("/", "%2F")
    intervals = client.archive_intervals(legacy, begin, end, archive_ap=archive_ap)
    return {
        "calendar_days": len(cal.get("dates", []) or cal.get("days", []) or []),
        "calendar_raw_keys": sorted(cal.keys()),
        "recent_interval_count": len(intervals),
        "window_hours": hours,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser)
    parser.add_argument("--hours", type=float, default=2.0, help="recent window to probe")
    parser.add_argument("--archive-ap", default="", help="archive access point (e.g. hosts/Server/MultimediaStorage.AliceBlue/...)")
    args = parser.parse_args()

    cfg = config_from_args(args)
    api = AxxonApiClient(cfg)
    inv = discover_inventory(api, cfg.tls_cn)

    out: dict = {"inventory": inv, "window_hours": args.hours}

    video_ap = inv.get("video_source_ap") or ""
    if video_ap and args.archive_ap:
        out["archive"] = _safe(lambda: archive_state(api, video_ap, args.archive_ap, args.hours))
    elif video_ap:
        out["archive"] = {"status": "need_archive_ap", "note": "pass --archive-ap to read calendar/intervals"}

    out["events"] = _safe(lambda: event_count(api, args.hours))

    vmda_ap = inv.get("vmda_source_ap") or ""
    if vmda_ap:
        meta = AxxonMcpMetadata(client_factory=lambda: api, config_factory=lambda: cfg)
        out["vmda_query"] = _safe(lambda: _vmda_summary(meta.vmda_query(
            access_point=vmda_ap, query_type="motion_in_area",
            object_types=["human", "vehicle"], behaviours=["moving"], hours=int(args.hours) or 2,
        )))
    else:
        out["vmda_query"] = {"status": "no_vmda_source", "note": "no */SourceEndpoint.vmda found on camera"}

    print(json.dumps(out, indent=2, default=str))
    return 0


def _vmda_summary(result: dict) -> dict:
    return {k: result.get(k) for k in ("status", "interval_count", "object_count", "message")}


def _safe(fn):
    try:
        return fn()
    except Exception as exc:  # probe only: surface the error string instead of crashing the report
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


if __name__ == "__main__":
    sys.exit(main())
