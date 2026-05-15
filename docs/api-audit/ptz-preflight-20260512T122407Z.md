# Axxon One PTZ Preflight

- Started: `2026-05-12T12:24:07.225335+00:00`
- Finished: `2026-05-12T12:24:11.058557+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Read-only preflight for PTZ and Tag&Track workflows. It does not acquire sessions, move cameras, change presets, play tours, or change Tag&Track mode.

## Summary

- PASS: 0
- WARN: 4
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| WARN | `ptz_fixture_discovery` | 0 | telemetry=0 gap=no telemetry/PTZ access point found |
| WARN | `control_panel_discovery` | 194 | control_panels=0 gap=no control panels found |
| WARN | `telemetry_read_preflight` | 0 | skipped=no telemetry access point presets=None operations=None trackers=None |
| WARN | `approval_only_mutations` | 0 | TelemetryService.AcquireSessionId, TelemetryService.Move, TelemetryService.Zoom, TelemetryService.AbsoluteMove, TelemetryService.GoPreset, TelemetryService.SetPreset, TelemetryService.PlayTour, TelemetryService.PerformAu |
