# Axxon One Map And Marker Smoke

- Started: `2026-05-02T22:16:06.237777+00:00`
- Finished: `2026-05-02T22:16:14.617108+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a `codex-*` raster map with a tiny PNG and marker, changes it, reads image/markers, updates/removes the marker, then removes the map.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `map_marker_lifecycle` | 7811 | map=codex-f6639e31-27f0-4540-9dee-97474532b3ce image_b64_len=92 markers=1->1->0 removed_not_found=['codex-f6639e31-27f0-4540-9dee-97474532b3ce'] |
