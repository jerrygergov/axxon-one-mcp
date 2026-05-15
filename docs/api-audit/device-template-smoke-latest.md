# Axxon One Device Template Smoke

- Started: `2026-05-02T18:03:54.957470+00:00`
- Finished: `2026-05-02T18:04:07.376383+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates an isolated virtual camera, creates and edits a `codex-*` template, assigns and unassigns it, then removes both objects.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `device_template_lifecycle` | 11967 | template=codex-fe87fb6f-e775-4314-bb3e-71959efc0baf created_etag_len=40 modified_etag_len=40 unassign_attempts=2 removed_not_found=['codex-fe87fb6f-e775-4314-bb3e-71959efc0baf'] |
