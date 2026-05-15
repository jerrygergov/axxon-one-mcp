# Axxon One Legacy HTTP Read Sweep

- Started: `2026-05-03T09:20:00.133337+00:00`
- Finished: `2026-05-03T09:20:09.553416+00:00`
- HTTP target: `http://<demo-host>:80`
- Groups: `server, camera_inventory, archive_read, events_read, macros_read`
- Auth mode: `bearer`

## Summary

- PASS: 19
- WARN: 1
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_device: `Server/DeviceIpint.1`
- host_name: `Server`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- begin: `20260502T092002.405608`
- end: `20260503T092002.405608`

## Results

| Status | Group | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `server` | `GET /hosts/` | 315 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /product/version` | 304 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /statistics/webserver` | 242 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /statistics/hardware` | 284 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /camera/list` | 640 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /camera/list?filter=Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 260 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /detectors/Server/DeviceIpint.1` | 272 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /statistics/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 251 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/list/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 260 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/contents/intervals/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092002.405608/20260502T092002.405608` | 233 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/depth/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 296 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/capacity/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092002.405608/20260502T092002.405608` | 240 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/calendar/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260502T092002.405608/20260503T092002.405608` | 279 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /audit/Server/20260503T092002.405608/20260502T092002.405608?filter=17-20,6,1:4` | 533 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/20260503T092002.405608/20260502T092002.405608` | 525 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092002.405608/20260502T092002.405608` | 517 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/20260503T092002.405608/20260502T092002.405608?limit=50&offset=0` | 638 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/Server/20260503T092002.405608/20260502T092002.405608?limit=50&offset=0` | 582 | HTTP 200 application/json; charset=utf-8 |
| WARN | `macros_read` | `GET /macros` | 229 | HTTP 400  |
| PASS | `macros_read` | `GET /macro/list` | 236 | HTTP 200 application/json; charset=utf-8 |
