# Axxon One External Event Smoke

- Started: `2026-05-08T08:22:31.372903+00:00`
- Finished: `2026-05-08T08:22:32.396551+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary external-event fixture or probes explicit access points, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes any temporary fixture.

## Summary

- PASS: 0
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `external_event_lifecycle` | 773 | fixture= type=access_point_probe attempts=3 last_status=503 matches=None |
