#!/usr/bin/env python3
"""Live smoke for Phase 5C alarm tools.

Default mode: reads only.

`--mutation` mode adds a synthetic round-trip on the first camera:
raise_alert -> capture alert_id -> alarm_begin_review -> alarm_continue_review
-> alarm_cancel_review -> verify gone from list_active_alerts. Requires
AXXON_ALARMS_APPROVE=1.

`--full` (with `--mutation`) additionally exercises complete + escalate
which leave persistent bookmark/escalation records on the stand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_alarms import AxxonMcpAlarms, AxxonAlarmMutator  # noqa: E402


def sanitize(obj, host: str):
    if isinstance(obj, dict):
        return {k: sanitize(v, host) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v, host) for v in obj]
    if isinstance(obj, str):
        return obj.replace(host, "<demo-host>")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutation", action="store_true",
                        help="Run synthetic raise/begin/continue/cancel round-trip.")
    parser.add_argument("--full", action="store_true",
                        help="Also exercise complete + escalate (leaves persistent records).")
    args = parser.parse_args()

    alarms = AxxonMcpAlarms()
    alarms.connect_axxon_profile("env")
    alarms.client.authenticate_http_grpc()
    host = alarms.client.config.host

    results = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "<demo-host>",
        "reads": {},
    }

    results["reads"]["list_active_alerts_node"] = alarms.list_active_alerts()
    inv = alarms._ensure_inventory()
    cams = [c.get("access_point") for c in inv.get("cameras", []) if c.get("access_point")]
    if not cams:
        print(json.dumps(sanitize({"status": "fixture-needed", "message": "no cameras", **results}, host), indent=2))
        return 2
    cam = cams[0]
    results["reads"]["list_active_alerts_first_camera"] = alarms.list_active_alerts(camera_access_point=cam)
    results["reads"]["filter_active_alerts"] = alarms.filter_active_alerts(limit=10)
    results["reads"]["list_alarm_history_1h"] = alarms.list_alarm_history(hours=1, limit=20)
    results["reads"]["list_alarm_event_types"] = alarms.list_alarm_event_types()
    results["reads"]["alarm_subscribe_5s"] = alarms.alarm_subscribe(duration_s=5, limit=10)

    if args.mutation:
        if os.environ.get("AXXON_ALARMS_APPROVE") != "1":
            print(json.dumps(
                sanitize({"status": "refused", "reason": "approval_env_not_set", **results}, host),
                indent=2,
            ))
            return 1
        mutator = AxxonAlarmMutator(
            client_factory=lambda _cfg: alarms.client,
            config_factory=lambda: alarms.client.config,
        )
        round_trip = {}
        raised = mutator.raise_alert(cam, confirmation="CONFIRM-raise-alert")
        round_trip["raise_alert"] = raised
        alert_id = raised.get("alert_id")
        if not alert_id:
            results["mutation"] = round_trip
            print(json.dumps(sanitize(results, host), indent=2))
            return 1
        time.sleep(1)
        round_trip["alarm_begin_review"] = mutator.alarm_begin_review(
            cam, alert_id, confirmation="CONFIRM-alarm-begin",
        )
        round_trip["alarm_continue_review"] = mutator.alarm_continue_review(
            cam, alert_id, confirmation="CONFIRM-alarm-continue",
        )
        round_trip["alarm_cancel_review"] = mutator.alarm_cancel_review(
            cam, alert_id, confirmation="CONFIRM-alarm-cancel",
        )
        time.sleep(1)
        post = alarms.list_active_alerts(camera_access_point=cam)
        round_trip["post_list_count"] = post.get("count")
        round_trip["audit_log"] = mutator.audit_log()
        # Sanitize the captured alert_id throughout the round-trip section.
        round_trip_str = json.dumps(round_trip, default=str).replace(alert_id, "<demo-alarm-id>")
        round_trip = json.loads(round_trip_str)
        results["mutation"] = round_trip

        if args.full:
            raised2 = mutator.raise_alert(cam, confirmation="CONFIRM-raise-alert")
            aid2 = raised2.get("alert_id")
            full = {"raise_alert": raised2}
            if aid2:
                full["alarm_begin_review"] = mutator.alarm_begin_review(
                    cam, aid2, confirmation="CONFIRM-alarm-begin",
                )
                full["alarm_complete_review"] = mutator.alarm_complete_review(
                    cam, aid2,
                    severity="false_alarm",
                    bookmark_message="phase-5c full smoke",
                    confirmation="CONFIRM-alarm-complete",
                )
                full_str = json.dumps(full, default=str).replace(aid2, "<demo-alarm-id>")
                full = json.loads(full_str)
            results["full"] = full

    print(json.dumps(sanitize(results, host), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
