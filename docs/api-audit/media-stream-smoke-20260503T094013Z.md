# Axxon One Media Stream Smoke

- Started: `2026-05-03T09:40:13.090342+00:00`
- Finished: `2026-05-03T09:40:23.196957+00:00`
- HTTP target: `http://<demo-host>:80`
- Max bytes per check: `1048576`
- Auth mode: `bearer`

## Summary

- PASS: 9
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- begin: `20260502T094015.403938`
- end: `20260503T094015.403938`
- archive_interval_begin: `20260503T075907.557000`
- archive_interval_end: `20260503T094015.659000`
- archive_media_time: `20260503T094015.659000`

## Results

| Status | Check | Endpoint | Size | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `camera_stream_info` | `GET /stream-info/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 28 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_snapshot` | `GET /live/media/snapshot/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0` | 53836 | HTTP 200 image/jpeg |
| PASS | `camera_live_mjpeg` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0` | 1048576 | HTTP 200 multipart/x-mixed-replace; boundary=ngpboundary |
| PASS | `camera_live_hls` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=hls` | 282 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_live_mp4` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=mp4` | 841 | HTTP 200 video/mp4 |
| PASS | `camera_live_rtsp_descriptor` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=rtsp` | 253 | HTTP 200 application/json; charset=utf-8 |
| PASS | `rtsp_statistics` | `GET /rtsp/stat` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_frame_by_time` | `GET /archive/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T094015.659000?threshold=60000&w=640&h=0` | 53738 | HTTP 200 image/jpeg |
| PASS | `archive_media_mjpeg` | `GET /archive/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T094015.659000?w=640&h=0&speed=1` | 1048576 | HTTP 200 multipart/x-mixed-replace; boundary=ngpboundary |
