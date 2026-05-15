# Axxon One External Event Smoke

- Started: `2026-05-07T12:05:28.039892+00:00`
- Finished: `2026-05-07T12:05:33.017159+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary AppDataDetector, calls `/v1/detectors/external:raiseOccasionalEvent`, verifies event history if accepted, then removes the detector.

## Summary

- PASS: 0
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `external_event_lifecycle` | 4565 | detector=hosts/Server/AppDataDetector.23 raise_status=500 raise_error=None matches=None |
