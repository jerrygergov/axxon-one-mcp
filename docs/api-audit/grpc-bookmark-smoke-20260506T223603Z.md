# Axxon One gRPC BookmarkService Smoke

- Started: `2026-05-06T22:36:03.642826+00:00`
- Finished: `2026-05-06T22:36:10.038581+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`
- Camera AP: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- Archive AP: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`

Creates a temporary `codex-grpc-bookmark-smoke-*` bookmark through `BookmarkService.CreateBookmark`, updates it, verifies listing filters, and deletes it.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `grpc_bookmark_lifecycle` | 3023 | created_id_len=36 created_filter_count=1 updated_filter_count=1 deleted_filter_count=0 |
