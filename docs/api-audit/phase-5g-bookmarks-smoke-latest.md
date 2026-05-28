# Axxon One Phase 5G BookmarkService Smoke

- Started: `2026-05-28T20:28:02.129334+00:00`
- Finished: `2026-05-28T20:28:02.963555+00:00`
- HTTP target: `http://<demo-host>`
- Transport: `http-grpc`
- Approval env: `AXXON_BOOKMARK_MUTATION_APPROVE`

Reads are non-mutating. The lifecycle workflow only writes a temporary `codex-` bookmark and removes it on rollback.

## Summary

- PASS: 1
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `bookmark_list` | 833 | count=0 status=ok |
| WARN | `bookmark_lifecycle` | 0 | Set AXXON_BOOKMARK_MUTATION_APPROVE=1 to exercise the bookmark lifecycle. |
