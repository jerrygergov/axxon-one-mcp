# Axxon One Bookmark Mutation Smoke

- Started: `2026-05-06T22:05:43.808320+00:00`
- Finished: `2026-05-06T22:05:47.489941+00:00`
- HTTP target: `http://<demo-host>:80`
- Auth mode: `bearer`

This smoke creates, edits, and removes only a temporary `codex-` bookmark.

## Summary

- PASS: 1
- WARN: 1
- FAIL: 0

## Fixtures

- host_name: `Server`
- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- begin: `20260506T220536.720000`
- end: `20260506T220546.720000`

## Results

| Status | Step | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `preflight_list` | `GET /archive/contents/bookmarks/Server/20260506T220546.720000/20260506T220536.720000` | 261 | HTTP 200 id= |
| WARN | `create_bookmark` | `POST /archive/contents/bookmarks/create` | 497 | HTTP 501 id= |
