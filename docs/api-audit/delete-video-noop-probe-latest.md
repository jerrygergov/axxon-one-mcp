# Axxon One Delete-Video No-Op Probe

- Started: `2026-05-12T08:49:35.448648+00:00`
- Finished: `2026-05-12T08:49:51.510516+00:00`
- HTTP target: `http://<demo-host>:80`
- Auth mode: `bearer`

This probe calls the PDF-documented `DELETE /archive/contents/bookmarks/` shape with a `codex-nonexistent-*` endpoint and storage id. It verifies dispatch behavior only and does not target real archive data.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Fixtures

- host_name: `Server`
- begin: `20260512T084935.448648`
- end: `20260512T084935.448648`
- endpoint: `hosts/Server/codex-nonexistent-delete-video/SourceEndpoint.video:0:0`
- storage_id: `hosts/Server/codex-nonexistent-delete-video/MultimediaStorage`
- camera_count: `33`

## Results

| Status | Step | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `delete_video_noop_dispatch` | `DELETE /archive/contents/bookmarks/?begins_at=20260512T084935.448648&ends_at=20260512T084935.448648&storage_id=hosts%2FServer%2Fcodex-nonexistent-delete-video%2FMultimediaStorage&endpoint=hosts%2FServer%2Fcodex-nonexistent-delete-video%2FSourceEndpoint.video%3A0%3A0` | 449 | HTTP 404  |
