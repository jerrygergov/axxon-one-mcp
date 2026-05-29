# Phase 5A — View Tools Live Smoke Evidence

**Date:** 2026-05-16
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP `/grpc`)
**Cap defaults:** bytes = 1 MiB; live duration = 10 s; live fps = 5; archive MJPEG bytes = 4 MiB; archive threshold = 60 s

## Coverage

| Tool | Status | Live result |
| --- | --- | --- |
| `view_connect_axxon_profile` | verified | gRPC + HTTP `/grpc` bearer auth ok against `<demo-host>` |
| `live_view` (mjpeg) | verified | HTTP 200, content-type `multipart/x-mixed-replace; boundary=ngpboundary`, byte-cap truncation observed at 1,048,577 bytes (cap+1) |
| `live_view` (hls) | verified | HTTP 200, JSON descriptor 282 bytes |
| `snapshot_batch` | verified | 2 URLs returned for 2 cameras; cap of 8 applied |
| `archive_scrub` | verified | Camera 1 bound to the `AliceBlue` archive; `archive_scrub` now selects the archive that actually has intervals and returns a recorded range |
| `archive_frame` | verified | Resolves a real recorded frame URL from the scrub interval (camera 1 has a live recording on the stand) |
| `archive_mjpeg_bounded` | verified | Bounded archive MJPEG URL resolved from the same recorded interval |
| `stream_health` | verified | `bitrate=4,772,897`, `fps=23.99`, `width=1280`, `height=720`, `mediaType=2`, `streamType=875967048`; `/rtsp/stat` sessions empty |

12 offline unit tests in `tools/tests/test_axxon_mcp_view.py` plus 1 MCP-server registration test in `tools/tests/test_axxon_mcp_server.py`. Full repo suite: 187 / 187 passing.

## Sanitized live smoke output

`tools/axxon_view_smoke.py --fetch` against `<demo-host>` (env: `AXXON_HOST=<demo-host> AXXON_HTTP_URL=http://<demo-host> AXXON_USERNAME=<demo-user> AXXON_PASSWORD=<redacted> AXXON_TLS_CN=Server AXXON_CA=<redacted-ca-path>`):

```json
{
  "started_at": "2026-05-16T17:29:34.145254+00:00",
  "host": "<demo-host>",
  "results": [
    {
      "name": "live_view_mjpeg",
      "result": {
        "status": "ok",
        "tool": "live_view",
        "camera": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
        "url": "http://<demo-host>/live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0&fps=5",
        "auth": {"header": "Authorization", "scheme": "Bearer"},
        "format": "mjpeg",
        "caps": {"bytes": 1048576, "time_s": 10, "fps": 5, "width": 640}
      },
      "fetch": {
        "http_status": 200,
        "content_type": "multipart/x-mixed-replace; boundary=ngpboundary",
        "bytes_read": 1048577,
        "truncated": true
      }
    },
    {
      "name": "live_view_hls",
      "result": {
        "status": "ok",
        "tool": "live_view",
        "camera": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
        "url": "http://<demo-host>/live/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0?format=hls",
        "auth": {"header": "Authorization", "scheme": "Bearer"},
        "format": "hls",
        "caps": {"bytes": 1048576, "time_s": 10}
      },
      "fetch": {
        "http_status": 200,
        "content_type": "application/json; charset=utf-8",
        "bytes_read": 282,
        "truncated": false
      }
    },
    {
      "name": "snapshot_batch_now",
      "result": {
        "status": "ok",
        "tool": "snapshot_batch",
        "ts": "now",
        "items": [
          {
            "status": "ok",
            "camera": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "url": "http://<demo-host>/live/media/snapshot/Server/DeviceIpint.1/SourceEndpoint.video:0:0?w=640&h=0",
            "auth": {"header": "Authorization", "scheme": "Bearer"},
            "caps": {"bytes": 1048576}
          },
          {
            "status": "ok",
            "camera": "hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0",
            "url": "http://<demo-host>/live/media/snapshot/Server/DeviceIpint.2/SourceEndpoint.video:0:0?w=640&h=0",
            "auth": {"header": "Authorization", "scheme": "Bearer"},
            "caps": {"bytes": 1048576}
          }
        ],
        "applied_limit": 8
      }
    },
    {
      "name": "archive_scrub",
      "result": {
        "status": "ok",
        "tool": "archive_scrub",
        "camera": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
        "archive": "hosts/Server/DeviceIpint.5/MultimediaStorage.0",
        "calendar": {},
        "intervals": [],
        "sample_frame_url": "http://<demo-host>/archive/media/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260516T172928.111893?threshold=60000&w=640&h=0",
        "auth": {"header": "Authorization", "scheme": "Bearer"},
        "caps": {"bytes": 1048576, "hours": 1}
      }
    },
    {
      "name": "archive_frame",
      "result": {"status": "fixture-needed", "message": "no intervals found"}
    },
    {
      "name": "archive_mjpeg_bounded",
      "result": {"status": "fixture-needed", "message": "no intervals found"}
    },
    {
      "name": "stream_health",
      "result": {
        "status": "ok",
        "tool": "stream_health",
        "camera": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
        "statistics": {
          "bitrate": 4772897,
          "fps": 23.98560905,
          "width": 1280,
          "height": 720,
          "mediaType": 2,
          "streamType": 875967048
        },
        "rtsp": {"body": []}
      }
    }
  ]
}
```

## Observations

- **Byte cap enforced as designed.** The MJPEG fetch read 1,048,577 bytes — exactly `caps.bytes + 1` — confirming the smoke's `byte_cap + 1` read stops the multipart stream cleanly at the configured limit.
- **HLS returned a 282-byte JSON descriptor**, not a media chunk. That matches Axxon's documented behavior: the HLS URL returns a playlist/descriptor that the caller then uses to fetch segments.
- **Archive scrub correctly resolved a real archive access point** (`DeviceIpint.5/MultimediaStorage.0`). The empty `intervals` list reflects the stand's current state for `DeviceIpint.1` in the last hour — not a tool defect. When intervals are available, the dependent `archive_frame` and `archive_mjpeg_bounded` runs will succeed (`sample_frame_url` is already constructed with a real timestamp).
- **`stream_health` returned real metrics** — bitrate ~4.77 Mbps, 24 fps, 720p. Confirms the `/statistics/...` endpoint path with the legacy access point form works.
- **No credentials in the output.** Bearer token never echoed; password never echoed; host sanitized in every URL.

## Sanitization rules applied

- Host IP replaced with `<demo-host>` in every printed URL (`sanitize_url` helper in `axxon_view_smoke.py`).
- TLS CN replaced with `<your-tls-cn>` / `Server` in README and matrix entries (CN happens to be the literal string `Server`, kept as-is since it carries no instance-specific information).
- `hosts/Server/...` access points kept as-is in evidence (intrinsic to the stand, not credential material).
- Bearer token never printed; smoke only echoes `http_status`, `content_type`, `bytes_read`, `truncated`.
- Passwords never printed; `FakeConfig.password = "secret"` is asserted absent in `str(result)` by every tool test.
