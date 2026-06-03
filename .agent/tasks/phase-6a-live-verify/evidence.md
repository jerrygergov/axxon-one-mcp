# Evidence: phase-6a-live-verify

## Summary
Live verification of the Phase 6A generated bundles against the demo stand
(<demo-host>, gRPC CN=Server). Generated each bundle from the current generator, ran it with
real credentials from env, and captured the JSON result. Live runs surfaced one genuine
template bug (GetActiveAlerts request shape) which was fixed and re-verified.

## Environment (sanitized)
- AXXON_HOST=<demo-host>:20109  AXXON_HTTP_URL=http://<demo-host>
- AXXON_USERNAME=<demo-user>  AXXON_PASSWORD=<redacted>  AXXON_TLS_CN=Server
- AXXON_CA=<redacted>  AXXON_STUBS_PATH=/tmp/axxon-grpc-py (generated pb2 stubs)
- Note: generated bundles take the full gRPC target in AXXON_HOST (host:20109).

## Bug found and fixed: GetActiveAlerts request shape
- `LogicService.GetActiveAlertsRequest` REQUIRES `camera_ap`. Calling it with an empty
  request returns `StatusCode.INTERNAL "An empty name is not acceptable."`.
- The alert-review lifecycle requests use `camera_ap` + `alert_id` (the alert's `guid`);
  `CompleteAlertReview` also takes `severity` (AlertState.ESeverity, SV_NOTICE=2).
- Fixed:
  - `alarm_responder` now requires `camera_ap` (operator is optional, defaults "axxon-mcp"),
    calls `GetActiveAlerts(camera_ap=...)`, and uses `alert.guid` + `severity=2` in the lifecycle.
  - `dashboard_backend` now calls `GetActiveAlerts(camera_ap=...)` per camera from the snapshot.
- Re-verified live: `dashboard_backend` went from `active_alerts: 0` (broken) to `active_alerts: 20`.

## Live runs (sanitized results)

| Template | Transport | Result |
|----------|-----------|--------|
| grpc_consumer (ListUnits) | direct gRPC | `{"status implied", "preview_chars": 849}` PASS |
| http_grpc_consumer (ListUnits) | HTTP /grpc | `{"status": 200, "bytes": 2101}` PASS |
| inventory_sync | direct gRPC | `{"cameras": 37, "units": 1, "bytes": 27800}` PASS |
| event_consumer (10s) | direct gRPC | `{"received": 0}` PASS (empty event history) |
| scheduled_exporter (1 run) | direct gRPC | `{"runs":[{"sessions_inspected": 1}]}` PASS |
| dashboard_backend (fixed) | direct gRPC | `{"cameras": 37, "active_alerts": 20, "recent_events": 0, "bytes": 113202}` PASS |
| alarm_responder (read path) | direct gRPC | `{"handled": 0}` PASS (camera 1 has 0 active alerts now) |
| ml_detector_bridge (empty results) | direct gRPC | `{"raised": 0}` PASS (safe no-op path) |

## Genuine stand-side fixture gaps (cannot close from client)
1. **ml_detector_bridge mutating path**: no `ExternalDetector` unit exists on the stand
   (ListUnits shows zero units with a `detector=External*` property). Without an
   ExternalDetector access point, `RaiseOccasionalEvent` has no valid target. Fixture needed:
   create one External Detector on a camera (Axxon Console: add an "External Detector" to a
   device), then re-run `ml_detector_bridge` with its access point to exercise the raise.
2. **recent_events always 0**: the stand's event-history DB returns 0 events even over a
   30-day window (ReadCount confirms empty). Fixture needed: generate some detector/system
   events (e.g. arm a detector, trigger motion) so EventHistoryService.ReadEvents has data.
3. **alarm_responder mutating lifecycle**: camera 1 currently has 0 active alerts, so the
   BeginAlertReview->CompleteAlertReview path was not exercised live. To exercise reversibly,
   a macro/rule that raises an alert on camera 1 would let the responder review+complete it.

## Notes
- All mutations attempted were reversible/no-op; nothing on the stand was left changed.
- The proto symlink used for stub generation was removed before commit; no proto/CA committed.
