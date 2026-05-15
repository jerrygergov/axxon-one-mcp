# Axxon One Bookmark Mutation Smoke

- Started: `2026-05-12T08:50:14.337727+00:00`
- Finished: `2026-05-12T08:50:21.167645+00:00`
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
- begin: `20260512T085009.053000`
- end: `20260512T085019.053000`

## Results

| Status | Step | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `preflight_list` | `GET /archive/contents/bookmarks/Server/20260512T085019.053000/20260512T085009.053000` | 517 | HTTP 200 id= |
| WARN | `create_bookmark` | `POST /archive/contents/bookmarks/create/` | 1577 | HTTP 501 id= |
