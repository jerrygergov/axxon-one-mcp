# MCP Operator Smoke

Generated: 2026-05-14

Tool:

```text
arm64-docker/tools/axxon_mcp_operator.py
```

Live smoke harness:

```text
arm64-docker/tools/axxon_mcp_operator_smoke.py
```

Raw output of the full 7-workflow live run (2026-05-14):

```text
arm64-docker/docs/api-audit/mcp-operator-smoke-2026-05-14-run.log
```

Target:

- Host: `<demo-host>`
- gRPC port: `20109`
- TLS CN: `<demo-tls-cn>`

Mode: controlled-operator (plan / apply / verify / rollback).

## Result

Seven Phase 3 operator workflows are implemented and all seven ran end-to-end on the demo stand on 2026-05-14. Every workflow created exactly the planned object(s), verified presence, removed them, and re-verified absence. `temp_appdata_detector` is a chained two-step workflow when no vmda source AP is supplied: it creates a SceneDescription AVDetector first, waits for its `SourceEndpoint.vmda` to publish, then creates the AppDataDetector against it. Rollback removes both in reverse order.

| Workflow | Plan | Bad-token reject | Apply | Verify (post-apply) | Rollback | Verify (post-rollback) |
|---|---|---|---|---|---|---|
| `temp_camera` | OK | OK (2026-05-13) | applied, 1 `DeviceIpint` created under `hosts/Server` | still_present=1 | 1 UID removed | still_present=0 |
| `temp_archive` | OK | covered by unit tests | applied, 1 `MultimediaStorage` created under `hosts/Server` | still_present=1 | 1 UID removed | still_present=0 |
| `temp_av_detector` | OK (requires `video_source_ap` param; returns gap otherwise) | covered by unit tests | applied, 1 `AVDetector` created (MotionDetection bound to `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`) | still_present=1 | 1 UID removed | still_present=0 |
| `temp_appdata_detector` | OK (requires `video_source_ap`; if no `vmda_source_ap`, chains a SceneDescription AVDetector) | covered by unit tests | applied, 2 UIDs created (AVDetector + AppDataDetector) | still_present=2 | 2 UIDs removed | still_present=0 |
| `temp_device_template` | OK (requires `camera_uid`) | covered by unit tests | applied, 1 template ID created via `ChangeTemplates` (`codex-<uuid>`) | still_present=1 | 1 template ID removed | still_present=0 |
| `external_event_inject` | OK (requires `access_point`) | covered by unit tests | applied, 1 `raiseOccasionalEvent` POST returned 200 | n/a (one-shot, no UIDs tracked) | no-op | still_present=0 |
| `temp_macro` | OK | covered by unit tests | applied, 1 macro GUID created via `LogicService.ChangeMacros` (disabled, empty) | still_present=1 | 1 macro GUID removed | still_present=0 |

Audit log for the 6-workflow run records actions for every plan/apply/rollback, including the `gap` plan that did not call the server.

## Plan Bodies (Sanitized)

- `temp_camera`: adds `DeviceIpint` with `vendor=Virtual`, `model=Virtual several streams`, `display_name=codex-temp-camera-<hint>-<stamp>`, `display_id=9XXX`.
- `temp_archive`: adds `MultimediaStorage` with `color=Gray`, `storage_type=object`, `day_depth=0`, `display_name=codex-temp-archive-<hint>-<stamp>`. Disabled by default because `day_depth=0`.
- `temp_av_detector`: adds `AVDetector` bound to the caller-supplied `video_source_ap`; default `detector=MotionDetection` (caller may pass `SceneDescription` / `NeuroTracker` / etc.). Display name `codex-temp-<detector>-<hint>-<stamp>`.
- `temp_appdata_detector`: adds `AppDataDetector` with `input=TargetList`, `camera_ref` carrying nested `streaming_id` pointing to a `vmda_source_ap`; default `detector=MoveInZone`. When no `vmda_source_ap` is supplied, the workflow first adds a temporary SceneDescription `AVDetector`, waits via `DomainService.ListComponents` for its `SourceEndpoint.vmda` to publish (10s cap), then chains the AppDataDetector against it.
- `temp_device_template`: creates one `DeviceTemplate` (id `codex-<uuid>`) attached to the caller-supplied `camera_uid` with sample geo coordinates. Removed on rollback by template ID via `ChangeTemplates`.
- `external_event_inject`: POSTs an `eventState=HAPPENED` event to `/v1/detectors/external:raiseOccasionalEvent` with bearer auth. Timestamp is RFC3339 with `Z` suffix. One-shot; no rollback.
- `temp_macro`: creates a disabled, empty `MacroConfig` (client-generated GUID) via `LogicService.ChangeMacros.added_macros`. Self-contained: no fixture required. Rollback removes by GUID via `removed_macros`.

## Transport

`AxxonOperatorClient` routes `ChangeConfig`/`ListUnits` through direct gRPC `ConfigurationServiceStub`, `ChangeTemplates`/`BatchGetTemplates` through HTTP `/grpc`, `ChangeMacros`/`BatchGetMacros` through direct gRPC `LogicServiceStub`, and `raiseOccasionalEvent` through the bearer-authenticated HTTP REST endpoint. Authentication uses the in-memory bearer token from `AuthenticateEx2`. No credential, token, license key, serial number, or raw security payload is stored in this report.

## Safety Properties Verified Live

- Wrong confirmation token rejected before any server call (verified on 2026-05-13 run).
- Builders may return `status: gap` instead of a plan when a required fixture parameter is missing (verified for `temp_av_detector` without `video_source_ap` — offline unit test).
- Every plan generates a fresh `plan_id`; replays of `apply` use independent plans.
- Every apply records the created UIDs; rollback removes exactly that set in reverse order.
- Audit log records every action (plan / apply / rollback) with timestamps.

## Notes

- `AXXON_TIMEOUT=30` was used.
- The cycle is repeatable: re-running the script creates new `codex-*` objects with fresh stamps and removes them within the same session.
- Four workflows use `ConfigurationService.ChangeConfig` directly (`temp_camera`, `temp_archive`, `temp_av_detector`, `temp_appdata_detector`). `temp_device_template` uses `ConfigurationService.ChangeTemplates`. `temp_macro` uses `LogicService.ChangeMacros`. `external_event_inject` uses the HTTP `raiseOccasionalEvent` endpoint.
- `temp_appdata_detector` is the only multi-step workflow in this set. It uses an inter-step dependency: step 1's payload is built at apply-time from step 0's created UID by appending `/SourceEndpoint.vmda`. `wait_for_component` polls `DomainService.ListComponents` to confirm publication before the chained ChangeConfig call (10s cap).
