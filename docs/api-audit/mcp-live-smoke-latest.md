# MCP Live Inspection Smoke

Generated: 2026-05-13

Tool:

```text
arm64-docker/tools/axxon_mcp_live.py
```

Target:

- Host: `<demo-host>`
- gRPC port: `20109`
- HTTP port: `80`
- TLS CN: `<demo-tls-cn>`
- Password stored: no

Mode: read-only.

## Result

The MCP live-inspection layer connected to the demo stand through `AxxonApiClient` and loaded sanitized inventory.

Counts:

- Cameras: 33
- Archives: 14
- Detectors: 35
- AppDataDetector entries: 18
- Event suppliers: 51
- Metadata endpoints: 15

Preflight:

- Task: `subscribe detector events`
- Status: `ready`
- Available fixtures: `event_supplier`, `metadata_endpoint`, `camera`, `archive`, `appdata_detector`
- Missing fixtures: none

## Phase 2 Bounded Tools (2026-05-13)

`get_archive_intervals` (wraps `ArchiveService.GetHistory2`):

- Input: camera `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`, hours=1.0, max_count=8.
- Source AP resolution: camera SourceEndpoint translated to `MultimediaStorage.*/Sources/src.*` (device-embedded `Sources/src.0` access points were observed to be stale and unresolvable on this stand).
- Status: `ok`.
- Intervals returned: 1.
- Interval shape (key names only): `begin_time`, `end_time`.

`subscribe_events_bounded` (wraps `DomainNotifier.PullEvents`):

- Input: subjects=[`hosts/Server/AppDataDetector.6/EventSupplier`], event_types=[], timeout=5.0 s, limit=10.
- Status: `ok`.
- Events received: 0 in window (stand was quiet at smoke time).
- Disconnect cleanup ran via `DisconnectEventChannel`.

Cap safety:

- Request: timeout=9999.0 s, limit=99999.
- Applied caps: timeout clamped to 30.0 s, limit clamped to 500.

## Notes

- The smoke refreshed the temporary demo gRPC certificate at `/tmp/axxon-demo-server.crt`.
- This report stores no password, bearer token, license key, serial number, raw security payload, image, or video.
