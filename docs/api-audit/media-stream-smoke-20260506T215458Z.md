# Axxon One Media Stream Smoke

- Started: `2026-05-06T21:54:58.996935+00:00`
- Finished: `2026-05-06T21:55:15.949794+00:00`
- HTTP target: `http://<demo-host>:80`
- Max bytes per check: `1048576`
- Auth mode: `bearer`

## Summary

- PASS: 11
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- composite_sources: `Server/1/0/0+Server/2/0/0`
- begin: `20260505T215501.270160`
- end: `20260506T215501.270160`
- archive_interval_begin: `20260506T201358.409000`
- archive_interval_end: `20260506T215501.521000`
- archive_media_time: `20260506T215501.521000`
- host: `<demo-host>`

## Results

| Status | Check | Endpoint | Size | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `camera_stream_info` | `GET /stream-info/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 28 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_snapshot` | `GET /live/media/snapshot/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0` | 51857 | HTTP 200 image/jpeg |
| PASS | `camera_live_mjpeg` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0` | 1048576 | HTTP 200 multipart/x-mixed-replace; boundary=ngpboundary |
| PASS | `camera_live_hls` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=hls` | 282 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_live_mp4` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=mp4` | 32 | HTTP 200 video/mp4 |
| PASS | `camera_live_rtsp_descriptor` | `GET /live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=rtsp` | 253 | HTTP 200 application/json; charset=utf-8 |
| PASS | `rtsp_statistics` | `GET /rtsp/stat` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `rtsp_playback_ffprobe` | `FFPROBE rtsp://<demo-host>:554/hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 0 | ffprobe rc=0 stream=h264 1280x720 |
| PASS | `composite_rtsp_playback_ffprobe` | `FFPROBE rtsp://<demo-host>:554/composite/Server/1/0/0+Server/2/0/0?res=640x360&fps=5&quality=4&softacceleration=1` | 0 | ffprobe rc=0 stream=h264 640x360 |
| PASS | `archive_frame_by_time` | `GET /archive/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260506T215501.521000?threshold=60000&w=640&h=0` | 51591 | HTTP 200 image/jpeg |
| PASS | `archive_media_mjpeg` | `GET /archive/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260506T215501.521000?w=640&h=0&speed=1` | 1048576 | HTTP 200 multipart/x-mixed-replace; boundary=ngpboundary |
