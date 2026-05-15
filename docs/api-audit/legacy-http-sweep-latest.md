# Axxon One Legacy HTTP Read Sweep

- Started: `2026-05-06T22:31:21.101730+00:00`
- Finished: `2026-05-06T22:31:25.397730+00:00`
- HTTP target: `http://<demo-host>:80`
- Groups: `archive_read`
- Auth mode: `bearer`

## Summary

- PASS: 6
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_legacy_ap: `Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- camera_device: `Server/DeviceIpint.1`
- host_name: `Server`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- begin: `20260505T223123.868018`
- end: `20260506T223123.868018`

## Results

| Status | Group | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `archive_read` | `GET /archive/list/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 245 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/contents/intervals/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260506T223123.868018/20260505T223123.868018` | 244 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/contents/frames/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260506T223123.868018/20260505T223123.868018?limit=3` | 273 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/depth/Server/DeviceIpint.1/SourceEndpoint.video:0:0` | 244 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/statistics/capacity/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260506T223123.868018/20260505T223123.868018` | 277 | HTTP 200 application/json; charset=utf-8 |
| PASS | `archive_read` | `GET /archive/calendar/Server/DeviceIpint.1/SourceEndpoint.video:0:0/20260505T223123.868018/20260506T223123.868018` | 243 | HTTP 200 application/json; charset=utf-8 |
