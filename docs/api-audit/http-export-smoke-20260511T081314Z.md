# Axxon One Legacy HTTP Export Smoke

- Started: `2026-05-11T08:13:14.748096+00:00`
- Finished: `2026-05-11T08:13:23.482688+00:00`
- HTTP target: `http://<demo-host>:80`

Starts one temporary one-frame JPEG export through legacy HTTP `/export`, downloads only a bounded file prefix, and deletes the export id.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- archive_timestamp: `20260511T081318`

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `archive_frame_export_lifecycle` | 4867 | start=202 state=2 files=1 download=200/72107 deleted=True |
