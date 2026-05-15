# Axxon One External Event Smoke

- Started: `2026-05-07T16:48:02.614068+00:00`
- Finished: `2026-05-07T16:48:12.780828+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary external-event fixture, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes the fixture.

## Summary

- PASS: 0
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `external_event_lifecycle` | 9733 | fixture=hosts/Server/RealtimeRecognizerExternal.1 type=RealtimeRecognizerExternal attempts=3 last_status=503 matches=None |
