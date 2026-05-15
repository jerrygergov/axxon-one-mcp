# Axxon One Legacy HTTP Read Sweep

- Started: `2026-05-03T09:19:44.517424+00:00`
- Finished: `2026-05-03T09:19:52.886225+00:00`
- HTTP target: `http://<demo-host>:80`
- Groups: `events_read`
- Auth mode: `bearer`

## Summary

- PASS: 5
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_device: `Server/DeviceIpint.1`
- host_name: `Server`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- begin: `20260502T091947.460015`
- end: `20260503T091947.460015`

## Results

| Status | Group | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `events_read` | `GET /audit/Server/20260503T091947.460015/20260502T091947.460015?filter=17-20,6,1:4` | 1946 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/20260503T091947.460015/20260502T091947.460015` | 519 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T091947.460015/20260502T091947.460015` | 517 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/20260503T091947.460015/20260502T091947.460015?limit=50&offset=0` | 1698 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/Server/20260503T091947.460015/20260502T091947.460015?limit=50&offset=0` | 742 | HTTP 200 application/json; charset=utf-8 |
