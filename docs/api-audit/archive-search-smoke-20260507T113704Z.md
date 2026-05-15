# Axxon One Archive Search Smoke

- Started: `2026-05-07T11:37:04.007543+00:00`
- Finished: `2026-05-07T11:37:24.852604+00:00`
- gRPC target: `<demo-host>:20109`

## Summary

- PASS: 7
- WARN: 0
- SKIP: 2
- FAIL: 0

## Results

| Status | Mode | ms | Notes |
| --- | --- | ---: | --- |
| PASS | `lpr` | 405 | items=0 |
| SKIP | `face` | 0 | missing --face-image fixture |
| PASS | `vmda` | 378 | items=1 |
| PASS | `heatmap` | 1935 | items=0 |
| PASS | `build_heatmap` | 2786 | result=True image_bytes=5842 |
| SKIP | `stranger` | 0 | missing --face-image fixture |
| PASS | `legacy_auto` | 1761 | items=0 |
| PASS | `legacy_vmda` | 1601 | items=0 |
| PASS | `legacy_heatmap` | 2054 | items=0 |
