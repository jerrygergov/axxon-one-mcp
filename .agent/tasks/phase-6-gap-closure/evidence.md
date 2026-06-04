# Evidence: phase-6-gap-closure (live, destructive testing authorized)

Closed every remaining non-PTZ gap by creating fixtures and exercising the real
mutating paths against the demo stand (<demo-host>:20109, CN=Server). The user
authorized aggressive/destructive testing on this test-only stand.

## Gaps closed

### Gap 1 — ml_detector_bridge mutating raise path: CLOSED
- `DetectorEx.1` exists on the stand. Probed its accepted event types: **`Event1`**
  returns `error: OK`; all others (`Event2`, `moveInZone`, `TargetList`, ...) return
  `BAD_EVENT_TYPE`.
- external_event smoke (`access_point_probe`, event_type `Event1`) -> **PASS**:
  RaiseOccasionalEvent accepted, event found in the tight-window verify (matches: 1).
- The generated `ml_detector_bridge` bundle raised 2 real Event1 events live:
  `{"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "raised": 2, "results": 2}`.

### Gap 2 — recent_events / EventHistory: CONFIRMED HARD STAND-CONFIG GAP
- `EventHistoryService.ReadCount` over a 30-day window across **all 20 event types**
  (ET_DetectorEvent, ET_Alert, ET_MacroEvent, ...) returns **0**. The stand does not
  persist any events to the queryable EventHistory DB (event archiving appears disabled
  in its server config). Injected DetectorEx events flow live but are not persisted.
- `dashboard_backend recent_events: 0` is therefore correct behavior, not a template bug
  (the same bundle returns cameras: 40, active_alerts: 21). Closing this needs server-side
  event-archive configuration that the API does not expose for creation.

### Gap 3 — alarm_responder review lifecycle: CLOSED (+ template bug fixed)
- `DeviceIpint.9` has 21 active alerts. Direct lifecycle test found that
  `CompleteAlertReview` rejects `severity=2 (SV_NOTICE)` with
  `Unknown bl::events::AlertState::ESeverity`, but accepts `1 (SV_FALSE)`, `3 (SV_WARNING)`,
  and `4 (SV_ALARM)`.
- **Fix:** `alarm_responder` (py + node) now completes with `SV_ALARM (4)` instead of
  `SV_NOTICE (2)`.
- Re-ran the generated `alarm_responder` bundle live: `{"handled": 5}` — Began and Completed
  review on 5 real alerts. BeginAlertReview + CompleteAlertReview both confirmed working.

### Gap 4 — schedule_descriptor_get (5F-A WARN): CONFIRMED HARD FIXTURE GAP
- Scanned all 38 device descriptors via `ConfigurationService.ListUnits` (full property
  tree) plus `BatchGetFactories`: **zero** schedule/calendar/weekly/daily fields anywhere on
  the stand. Axxon schedules are authored in the desktop client and are not exposed as a
  creatable config unit via the API on this stand. Genuine fixture gap.

## Mutation smokes run live (all reversible / rolled back)

| Smoke | Result |
|-------|--------|
| external_event (access_point_probe, Event1) | PASS=1 |
| admin mutation (5F-B1 + 5F-B2): user/role, role-perms, policy no-op, LDAP temp, TFA temp, production role edit/restore | PASS=6, WARN=0, FAIL=0 |
| alarms mutation round-trip (raise -> begin -> continue -> cancel) | all `ok` |
| gRPC bookmark lifecycle (Create -> Get -> Delete) | PASS=1, WARN=0, FAIL=0 |
| operator full apply/verify/rollback (8 ephemeral workflows) | all applied + rolled_back (temp_appdata_detector, temp_archive, temp_av_detector, temp_camera, temp_device_template, temp_macro, temp_wall, external_event_inject) |

Notes:
- Legacy HTTP bookmark create returns 501 on this stand (endpoint unsupported); the gRPC
  BookmarkService lifecycle is the supported path and passes.
- `raise_alert` returns an empty synchronous alert_id on this stand (the id arrives async);
  the review lifecycle uses captured ids and completes cleanly.
- All created fixtures were rolled back; alarms reviewed were real stand alerts (test-only
  stand, destructive testing authorized).

## Code change
- `tools/templates/alarm_responder.py.tmpl` and `.ts.tmpl`: CompleteAlertReview severity
  `SV_NOTICE(2)` -> `SV_ALARM(4)` (server rejects SV_NOTICE).

## Unit tests
`python3.12 -m unittest discover -s tools/tests` -> Ran 621 tests, OK.

## Remaining genuine gaps (cannot close from the API client)
1. `ptz_controller` — needs a PTZ camera (excluded by user).
2. EventHistory persistence — stand does not archive events (server config).
3. `schedule_descriptor_get` — no schedule descriptor object on the stand (desktop-client authored).
