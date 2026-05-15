# Axxon One Legacy HTTP Auth Probe

- Started: `2026-05-02T22:28:47.002622+00:00`
- Finished: `2026-05-02T22:28:52.757653+00:00`
- HTTP target: `http://<demo-host>:80`
- Auth modes: `anonymous, basic, bearer`

Read-only endpoint comparison for anonymous, Basic, and HTTP `/grpc` Bearer auth. Tokens and credentials are not written to this report.

## Summary

- PASS: 13
- WARN: 8
- FAIL: 0

## Results

| Status | Auth | Endpoint | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `anonymous` | `GET /hosts/` | 233 | HTTP 200 application/json; charset=utf-8 |
| PASS | `basic` | `GET /hosts/` | 279 | HTTP 200 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /hosts/` | 228 | HTTP 200 application/json; charset=utf-8 |
| WARN | `anonymous` | `GET /product/version` | 293 | HTTP 401 application/json; charset=utf-8 |
| WARN | `basic` | `GET /product/version` | 236 | HTTP 401 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /product/version` | 296 | HTTP 200 application/json; charset=utf-8 |
| PASS | `anonymous` | `GET /statistics/webserver` | 233 | HTTP 200 application/json; charset=utf-8 |
| PASS | `basic` | `GET /statistics/webserver` | 283 | HTTP 200 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /statistics/webserver` | 230 | HTTP 200 application/json; charset=utf-8 |
| PASS | `anonymous` | `GET /statistics/hardware` | 294 | HTTP 200 application/json; charset=utf-8 |
| PASS | `basic` | `GET /statistics/hardware` | 227 | HTTP 200 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /statistics/hardware` | 368 | HTTP 200 application/json; charset=utf-8 |
| WARN | `anonymous` | `GET /macro/list/` | 235 | HTTP 401 application/json; charset=utf-8 |
| WARN | `basic` | `GET /macro/list/` | 226 | HTTP 401 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /macro/list/` | 237 | HTTP 200 application/json; charset=utf-8 |
| WARN | `anonymous` | `GET /macro/list/?exclude_auto` | 275 | HTTP 401 application/json; charset=utf-8 |
| WARN | `basic` | `GET /macro/list/?exclude_auto` | 232 | HTTP 401 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /macro/list/?exclude_auto` | 297 | HTTP 200 application/json; charset=utf-8 |
| WARN | `anonymous` | `GET /v1/logic_service/macros` | 226 | HTTP 401 application/json; charset=utf-8 |
| WARN | `basic` | `GET /v1/logic_service/macros` | 290 | HTTP 401 application/json; charset=utf-8 |
| PASS | `bearer` | `GET /v1/logic_service/macros` | 238 | HTTP 200 application/json; charset=utf-8 |
