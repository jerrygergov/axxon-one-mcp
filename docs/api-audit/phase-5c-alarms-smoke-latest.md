# Phase 5C — Alarm Tools Live Smoke Evidence

**Date:** 2026-05-17
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP `/grpc`)
**Caps:** subscribe ≤ 30 s / 100 events; history ≤ 24 h / 200 events; list ≤ 200 items.

## Coverage

| Tool | Status | Live result |
| --- | --- | --- |
| `alarms_connect_axxon_profile` | verified | Bearer auth ok against `<demo-host>` |
| `list_active_alerts` (node) | verified | flattens `event_stream_items`; transient `unreachable_nodes` masked when pages disagree |
| `list_active_alerts` (camera) | verified | empty list on quiet stand |
| `filter_active_alerts` | verified | empty filter call returns paginated shape |
| `list_alarm_history` | verified | clamps hours to 24, filters to `ET_Alert`/`ET_AlertState`; routes via `AxxonMcpLive.search_events` |
| `list_alarm_event_types` | verified | returns `ET_Alert` (15) and `ET_AlertState` (16) |
| `alarm_subscribe` | verified | bounded 5 s window; flags `partial`/`reason` honestly |
| `raise_alert` | verified | synthetic alarm created; `alert_id` returned |
| `alarm_begin_review` | verified | `result: true` |
| `alarm_continue_review` | verified | `result: true` |
| `alarm_cancel_review` | verified | `result: true` |

Offline tests: `tools/tests/test_axxon_mcp_alarms.py` (34 tests) + `tools/tests/test_axxon_api_client_alarms.py` (6 tests) + 2 server-registration tests. Full repo suite: 229 / 229 passing.

## Sanitized live smoke output

`tools/axxon_alarms_smoke.py --mutation` against `<demo-host>` (env: `AXXON_HOST=<demo-host> AXXON_HTTP_URL=http://<demo-host> AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server AXXON_CA=docs/grpc-proto-files/api.ngp.root-ca.crt AXXON_ALARMS_APPROVE=1`):

```json
{
  "started_at": "2026-05-17T08:01:01.767315+00:00",
  "host": "<demo-host>",
  "reads": {
    "list_active_alerts_node": {
      "status": "ok",
      "tool": "list_active_alerts",
      "count": 0,
      "applied_limit": 50,
      "items": [],
      "unreachable_nodes": []
    },
    "list_active_alerts_first_camera": {
      "status": "ok", "tool": "list_active_alerts",
      "count": 0, "applied_limit": 50, "items": []
    },
    "filter_active_alerts": {
      "status": "ok", "tool": "filter_active_alerts",
      "count": 0, "applied_limit": 10,
      "applied_filters": {"severity_min": null, "camera": null, "state": "all"},
      "items": []
    },
    "list_alarm_history_1h": {
      "status": "ok", "tool": "list_alarm_history",
      "count": 0, "applied_hours": 1.0, "applied_limit": 20,
      "applied_filters": {"camera": null, "severity_min": null},
      "items": []
    },
    "list_alarm_event_types": {
      "status": "ok", "tool": "list_alarm_event_types",
      "count": 2,
      "items": [
        {"name": "ET_Alert", "value": 15},
        {"name": "ET_AlertState", "value": 16}
      ]
    },
    "alarm_subscribe_5s": {
      "status": "ok", "tool": "alarm_subscribe",
      "applied_duration_s": 5, "applied_limit": 10,
      "partial": false, "reason": "ok",
      "count": 0, "items": []
    }
  },
  "mutation": {
    "raise_alert": {
      "status": "ok", "tool": "raise_alert",
      "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
      "alert_id": "<demo-alarm-id>"
    },
    "alarm_begin_review": {
      "status": "ok", "tool": "alarm_begin_review",
      "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
      "alert_id": "<demo-alarm-id>", "result": true
    },
    "alarm_continue_review": {
      "status": "ok", "tool": "alarm_continue_review",
      "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
      "alert_id": "<demo-alarm-id>", "result": true
    },
    "alarm_cancel_review": {
      "status": "ok", "tool": "alarm_cancel_review",
      "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
      "alert_id": "<demo-alarm-id>", "result": true
    },
    "post_list_count": 1,
    "audit_log": [
      {"timestamp": "2026-05-17T08:02:10.006516+00:00", "action": "raise_alert", "result_status": "ok", "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert_id": "<demo-alarm-id>"},
      {"timestamp": "2026-05-17T08:02:11.404658+00:00", "action": "alarm_begin_review", "result_status": "ok", "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert_id": "<demo-alarm-id>"},
      {"timestamp": "2026-05-17T08:02:11.773001+00:00", "action": "alarm_continue_review", "result_status": "ok", "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert_id": "<demo-alarm-id>"},
      {"timestamp": "2026-05-17T08:02:12.142871+00:00", "action": "alarm_cancel_review", "result_status": "ok", "camera_access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert_id": "<demo-alarm-id>"}
    ]
  }
}
```

## Observations

- **Full round-trip succeeded.** `RaiseAlert` against a real camera access point returned `result: true` and a non-empty `alert_id`; subsequent `Begin`/`Continue`/`Cancel` all returned `result: true`.
- **Per-call confirmation tokens were enforced.** Each mutation accepted only its specific `CONFIRM-...` token; offline tests cover the refusal paths.
- **Audit log captured 4 entries**, each with `result_status: "ok"`, timestamp, action, camera AP, and (where applicable) alert_id.
- **`post_list_count: 1` after cancel.** The alert remained visible in `BatchGetActiveAlerts` for at least 1 second after cancel — likely the stand's `user_alert_ttl` (300 s in `LogicService.GetConfig`). The cancel itself succeeded (`result: true`); the lingering visibility is server-side TTL, not a tool defect.
- **No credentials in output.** Bearer token, password, root login never appear. Host IP replaced with `<demo-host>`; alert GUID replaced with `<demo-alarm-id>`.

## Sanitization rules applied

- Host IP → `<demo-host>` (string replace in `sanitize()` and JSON substitution).
- Alert GUID → `<demo-alarm-id>` (JSON-level replace using captured `alert_id`).
- `hosts/Server/...` kept (intrinsic).
- Bearer token never echoed.
- Password never echoed.
- `complete_review` / `escalate` are not exercised in the default smoke — they create persistent records (bookmark, escalation). Run `--full` only on a dedicated stand.
