# Axxon One ChangeConfig Mutation Smoke

- Started: `2026-05-07T12:14:29.801423+00:00`
- Finished: `2026-05-07T12:15:00.385886+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

All created objects use `codex-temp-*` names and are removed before the tool exits.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `av_detector_parameters` | 30115 | added=['hosts/Server/AVDetector.102'] scalar=enabled visual=polyline visual_readback=True |
