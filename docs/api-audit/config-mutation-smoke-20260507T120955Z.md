# Axxon One ChangeConfig Mutation Smoke

- Started: `2026-05-07T12:09:55.816791+00:00`
- Finished: `2026-05-07T12:10:09.389861+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

All created objects use `codex-temp-*` names and are removed before the tool exits.

## Summary

- PASS: 0
- WARN: 0
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| FAIL | `av_detector_parameters` | 12150 | no VisualElement child found for hosts/Server/AVDetector.100 |
