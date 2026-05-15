# Axxon One External Event Smoke

- Started: `2026-05-08T09:14:43.122109+00:00`
- Finished: `2026-05-08T09:14:46.720692+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary external-event fixture or probes explicit access points, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes any temporary fixture.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `external_event_lifecycle` | 3350 | fixture= type=access_point_probe attempts=1 last_status=200 matches=1 |
