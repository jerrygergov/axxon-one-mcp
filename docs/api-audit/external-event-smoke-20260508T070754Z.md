# Axxon One External Event Smoke

- Started: `2026-05-08T07:07:54.784430+00:00`
- Finished: `2026-05-08T07:07:55.288245+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary external-event fixture, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes the fixture.

## Summary

- PASS: 0
- WARN: 0
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| FAIL | `external_event_lifecycle` | 249 | AppDataDetector add returned no uid: {'failed': [], 'added': [], 'added_macros': [], 'removed_macros': [], 'failed_reason': []} |
