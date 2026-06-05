# Evidence Bundle: phase-9-periodical-event

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — workflow registered + builder — PASS
- `_build_raise_periodical_event_plan` added in `tools/axxon_mcp_operator.py`,
  mirroring `_build_external_event_inject_plan`. Registered in `WORKFLOWS` as
  `"raise_periodical_event"`.
- Proof: `rg -n "raise_periodical_event" tools/axxon_mcp_operator.py`.

## AC2 — plan shape (http_post + body keys + tracklets) — PASS
- Single `http_post` step to `/v1/detectors/external:raisePeriodicalEvent`; body has
  `accessPoint`, `eventType`, `timestamp` (RFC3339 Z), `data.targetList.tracklets[]`;
  each tracklet has `objectId`, `objectType`, `rectangle{x,y,w,h}`. Default single
  tracklet synthesized when none supplied.
- Proof: `test_raise_periodical_event_plan_shape_and_default_tracklet`,
  `test_raise_periodical_event_passes_through_custom_tracklets`.

## AC3 — missing access_point returns gap — PASS
- Returns `{"status": "gap", "message": "...access_point..."}` not an exception.
- Proof: `test_raise_periodical_event_requires_access_point`.

## AC4 — mutation risk + tokens + noop rollback — PASS
- `risk="mutation"`, `confirmation_token="CONFIRM-raise_periodical_event"`,
  rollback token + `noop` strategy; rollback `removed_uids == []`.
- Proof: assertions in the plan-shape + custom-tracklets tests.

## AC5 — unit tests + full suite green — PASS
- 6 new tests under `tools/tests/test_axxon_mcp_operator.py`.
- Full suite `Ran 689 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp (live-justified) — PASS
- Live (raw/live-verify.txt): `eventType=TargetList` accepted at
  `hosts/Server/DetectorEx.1/EventSupplier` (`{"error":"OK"}`); `Event1` rejected.
- `ExternalDetectorService.RaisePeriodicalEvent` + `RaiseOccasionalEvent`
  restamped `pending -> tested-pass` via `tools/axxon_corpus_restamp.py`. Service 0/2 -> 2/2.

## AC7 — http_post body-error treated as failure — PASS
- External-detector endpoints answer HTTP 200 even on rejection, with outcome in
  body `{"error": ...}`. Apply handler now returns `{"status":"error",...}` when
  body error != "OK". Hardens pre-existing `external_event_inject` too.
- Live proof: wrong `Event1` periodical event now yields
  `{"status":"error","message":"http_post rejected by server: BAD_EVENT_TYPE"}`
  (raw/live-verify.txt section B); previously falsely `applied`.
- Unit proof: `test_http_post_body_error_is_apply_failure`,
  `test_http_post_body_error_ok_is_applied`.

## Sanitization
- raw/live-verify.txt contains only `hosts/Server/...` access-point UID (allowed),
  no host IP / credentials.
