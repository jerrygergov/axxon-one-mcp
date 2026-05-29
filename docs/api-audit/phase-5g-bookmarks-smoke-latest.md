# Axxon One Phase 5G BookmarkService Smoke

- Started: `2026-05-29T09:58:42.737778+00:00`
- Finished: `2026-05-29T09:58:47.473570+00:00`
- HTTP target: `http://<demo-host>`
- Transport: `http-grpc`
- Approval env: `AXXON_BOOKMARK_MUTATION_APPROVE`

Reads are non-mutating. The lifecycle workflow only writes a temporary `codex-` bookmark and removes it on rollback.

## Summary

- PASS: 2
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `bookmark_list` | 1256 | count=0 status=ok |
| PASS | `bookmark_lifecycle` | 3477 | plan=planned apply=applied verify=verified rollback=rolled-back |
