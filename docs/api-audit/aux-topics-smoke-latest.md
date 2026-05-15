# Aux Topics Smoke

Generated: 2026-05-15

Tool: `arm64-docker/tools/axxon_aux_topics_smoke.py`

Live run: `arm64-docker/docs/api-audit/aux-topics-smoke-2026-05-15-run.log`

## Result

Eleven Integration APIs 3.0 topics that did not previously have a coverage-matrix row were verified read-only against the demo stand on 2026-05-15. Every call returned 200.

| Topic | RPC / endpoint | Status |
|---|---|---|
| Camera statistics | `GET /statistics/{three-component video source id}` | 200, real payload (bitrate/fps/resolution) |
| Camera/device groups | `axxonsoft.bl.groups.GroupManager.ListGroups` | 200, group tree (Demo + Similarity Search + nested groups) |
| Active alerts read | `axxonsoft.bl.logic.LogicService.GetActiveAlerts` (requires `camera_ap`) | 200, `alerts=[]` |
| Active alerts batch read | `axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts` (requires `nodes`) | 200, `event_stream_items` |
| Time zone get | `axxonsoft.bl.tz.TimeZoneManager.GetTimeZone` | 200, current zone + available zones |
| Time zones batch get | `axxonsoft.bl.tz.TimeZoneManager.BatchGetZones` | 200 |
| Archive calendar | `axxonsoft.bl.archive.ArchiveService.GetCalendar` (requires `MultimediaStorage.*/Sources/src.*` access point) | 200, `days=[]` |
| Current Web-Client user | `GET /v1/security/users:self` | 200, login + role ids |
| Bearer renew | `axxonsoft.bl.auth.AuthenticationService.RenewSession` | 200, new bearer (5-minute TTL) |
| Bearer renew v2 | `axxonsoft.bl.auth.AuthenticationService.RenewSession2` | 200, new bearer (5-minute TTL) |
| Bearer close | `axxonsoft.bl.auth.AuthenticationService.CloseSession` | 200, `error_code=OK` |

## Notes

- `LogicService.GetActiveAlerts` requires a camera access point (not just any host). The `GetActiveAlertsRequest` proto has a single `camera_ap` field; calling without it returns gRPC code 13 (`std::exception: An empty name is not acceptable.`).
- `ArchiveService.GetCalendar` requires an actual `MultimediaStorage.*/Sources/src.*` access point. Device-embedded `DeviceIpint.*/Sources/src.*` shapes are not valid history sources (same quirk as `GetHistory2`).
- `/statistics/{id}` uses the legacy three-component video source id with no `hosts/` prefix. Passing the full configuration UID (`hosts/Server/...`) returns 404.
- `RenewSession2` returns the same shape as `RenewSession`; the only observable difference is the proto definition supports a longer-form `expires_in` semantic. Both return a 5-minute TTL on this stand.
- `CloseSession` was exercised on an isolated `AxxonApiClient` instance so the smoke's own bearer remains valid.
- Detector mask (PDF §5.6.5) is intentionally not exercised separately. The PDF documents mask as a `VisualElement` sub-unit edited via `ConfigurationService.ChangeConfig`, which is already covered by `axxon_config_mutation_smoke.py`.

## Transport

All gRPC calls go through HTTP `/grpc` with bearer auth. The legacy statistics endpoint and the REST `users:self` endpoint use bearer-authenticated HTTP. No credentials, tokens, license keys, or raw security payloads appear in this report or the live-run log.
