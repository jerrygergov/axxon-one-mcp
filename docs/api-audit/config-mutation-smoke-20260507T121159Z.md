# Axxon One ChangeConfig Mutation Smoke

- Started: `2026-05-07T12:11:59.096982+00:00`
- Finished: `2026-05-07T12:12:53.091147+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

All created objects use `codex-temp-*` names and are removed before the tool exits.

## Summary

- PASS: 0
- WARN: 1
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| FAIL | `av_detector_parameters` | 49667 | timed out |
| WARN | `cleanup` | 0 | keys=1 |
