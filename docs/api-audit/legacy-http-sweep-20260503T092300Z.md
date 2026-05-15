# Axxon One Legacy HTTP Read Sweep

- Started: `2026-05-03T09:23:00.372893+00:00`
- Finished: `2026-05-03T09:23:10.028107+00:00`
- HTTP target: `http://<demo-host>:80`
- Groups: `server, camera_inventory, archive_read, events_read, macros_read`
- Auth mode: `bearer`

## Summary

- PASS: 20
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_device: `Server/DeviceIpint.1`
- host_name: `Server`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- begin: `20260502T092302.738604`
- end: `20260503T092302.738604`

## Results

| Status | Group | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `server` | `GET /hosts/` | 240 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /product/version` | 233 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /statistics/webserver` | 291 | HTTP 200 application/json; charset=utf-8 |
| PASS | `server` | `GET /statistics/hardware` | 249 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /camera/list` | 678 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /camera/list?filter=Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 241 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /detectors/Server/DeviceIpint.1` | 281 | HTTP 200 application/json; charset=utf-8 |
| PASS | `camera_inventory` | `GET /statistics/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 232 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/list/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 291 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/contents/intervals/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092302.738604/20260502T092302.738604` | 237 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/depth/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 287 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/capacity/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092302.738604/20260502T092302.738604` | 234 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/calendar/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260502T092302.738604/20260503T092302.738604` | 289 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /audit/Server/20260503T092302.738604/20260502T092302.738604?filter=17-20,6,1:4` | 541 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/20260503T092302.738604/20260502T092302.738604` | 515 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/detectors/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260503T092302.738604/20260502T092302.738604` | 519 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/20260503T092302.738604/20260502T092302.738604?limit=50&offset=0` | 749 | HTTP 200 application/json; charset=utf-8 |
| PASS | `events_read` | `GET /archive/events/alerts/Server/20260503T092302.738604/20260502T092302.738604?limit=50&offset=0` | 691 | HTTP 200 application/json; charset=utf-8 |
| PASS | `macros_read` | `GET /macro/list/` | 243 | HTTP 200 application/json; charset=utf-8 |
| PASS | `macros_read` | `GET /macro/list/?exclude_auto` | 238 | HTTP 200 application/json; charset=utf-8 |
