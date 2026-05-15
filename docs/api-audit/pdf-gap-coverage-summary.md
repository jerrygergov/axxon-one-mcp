# PDF Gap Coverage Summary

This summarizes the current coverage state for `Integration APIs 3.0.pdf` gaps tracked in `pdf-gap-coverage-matrix.json`.

## Status Counts

- `verified`: 19
- `partial`: 0
- `fixture-needed`: 6
- `unsafe`: 0

## Risk Counts

- `safe-read`: 3
- `bounded-stream`: 5
- `fixture-heavy`: 4
- `mutation`: 12
- `external-client`: 1

## Verified Areas

- Direct gRPC environment walkthrough from the PDF.
- Legacy HTTP camera stream info, live HLS/RTSP/HTTP, snapshots, frame timestamps, composite stream.
- Legacy HTTP archive contents, archive stats, archive stream, frame review, bookmarks, and delete-video endpoint disposition.
- Legacy Server HTTP API: unique id, hosts, server usage, product version, webserver statistics.
- Legacy HTTP audit/system log and alarms endpoints.
- HTTP export workflow.
- gRPC event subscriptions.
- gRPC export start/download/stop/destroy.
- gRPC archive creation, volume changes, cloud archive examples, reindex, remove/link operations.
- gRPC heatmap.
- gRPC device templates.
- gRPC interactive map create/change/remove, markers, map image, layout display control.
- gRPC macro configuration and macro mutations.
- gRPC users, roles, permissions, security policy, IP filtering, LDAP directory mutations.
- HTTP macros and virtual IP device state switch.
- Legacy HTTP archive search: face, LP, VMDA, stranger/familiar face, heatmap, and `faceAppearanceRate`.
- gRPC detector parameter management and Get tracks using GO.
- Virtual trigger and external event injection. With a real `DetectorEx.1` fixture on camera 1, `RaiseOccasionalEvent` with `Event1` is accepted and found in event history, and `RaisePeriodicalEvent` with `TargetList` is accepted and visible through `MetadataService.PullMetadata` on the DetectorEx VMDA endpoint.
- Embeddable video component for Web server. The demo Web server exposes `/embedded.html`; focused preflight verifies HTTP 200, a Video component title, `embedded.js`, and component/embed/video signatures without browser artifact persistence.

## Partial Areas

- None.

## Fixture-Needed Areas

- Legacy HTTP PTZ camera control. Fresh PTZ preflight on 2026-05-12 found zero telemetry/PTZ access points and zero control panels on the demo stand; movement remains fixture-needed and approval-only.
- HTTP WebSocket camera-event subscription. gRPC `PullEvents` is verified, but the demo Web server's `/events` endpoint still upgrades and then closes during receive for camera include and device track commands.
- Client HTTP API for layouts and videowalls. Fresh external-client preflight on 2026-05-12 confirms `127.0.0.1:8888` and `<demo-host>:8888` refuse TCP connections.
- gRPC control panels and water level. Fresh fixture discovery on 2026-05-12 found zero control panels and zero water-level devices.
- gRPC Tag&Track Pro PTZ mode. Tag&Track tracker reads require a telemetry/PTZ access point, and none is configured.
- gRPC TFA mutations (`EnableGoogleAuth`/`DisableGoogleAuth`). Proto surface exists in `SecurityService.proto:1000-1002` with `EEnableTFAResult`/`EDisableTFAResult` enums, but no live TFA mutation evidence is recorded; requires a Google Authenticator/OTP fixture and an isolated test user before enable/disable can be exercised with rollback.

## Unsafe Areas Awaiting Approval And Rollback Execution

- None currently classified as unsafe unknowns; remaining mutating gaps are fixture-needed or partial with explicit rollback requirements.

## Reports Generated

- `legacy-http-sweep-latest.md`
- `legacy-http-sweep-demo-bearer-2026-05-03.md`
- `legacy-auth-probe-demo-2026-05-03.md`
- `media-stream-smoke-latest.md`
- `bookmark-smoke-latest.md`
- `grpc-bookmark-smoke-latest.md`
- `delete-video-noop-probe-latest.md`
- `subscription-smoke-latest.md`
- `archive-search-smoke-latest.md`
- `config-detail-sweep-latest.md`
- `config-model-study-latest.md`
- `config-mutation-smoke-latest.md`
- `archive-management-preflight-latest.md`
- `archive-management-noop-smoke-latest.md`
- `security-admin-preflight-latest.md`
- `security-mutation-smoke-latest.md`
- `export-preflight-latest.md`
- `export-smoke-latest.md`
- `http-export-smoke-latest.md`
- `export-settings-update-20260511.md`
- `ptz-preflight-latest.md`
- `external-client-preflight-latest.md`
- `external-event-smoke-latest.md`
- `external-event-detectorex-20260508.md`
- `layout-mutation-smoke-latest.md`
- `armstate-smoke-latest.md`
- `config-model-study-demo-2026-05-02.md`
- `config-mutation-smoke-demo-2026-05-02.md`
- `demo-metadata-tracklets-2026-05-02.md`
- `macro-smoke-demo-2026-05-03.md`
- `device-template-smoke-demo-2026-05-02.md`
- `map-marker-smoke-demo-2026-05-03.md`
- `fixture-discovery-latest.md`
- `mcp-corpus/api_methods.json`
- `mcp-corpus/http_endpoints.json`
- `mcp-corpus/task_recipes.json`
- `mcp-corpus/fixtures.json`
- `mcp-corpus/safety_policies.json`
- `mcp-corpus/known_behaviors.json`

## Mutation Playbooks

- `mutation-playbooks/bookmarks.md`
- `mutation-playbooks/external-events.md`
- `mutation-playbooks/export.md`
- `mutation-playbooks/macros.md`
- `mutation-playbooks/device-templates.md`
- `mutation-playbooks/users-roles-security.md`
- `mutation-playbooks/archive-management.md`
- `mutation-playbooks/detector-parameters.md`
- `mutation-playbooks/maps-markers.md`
- `mutation-playbooks/ptz-control.md`

## Verification Commands

- Unit tests: `/tmp/axxon-grpc-venv/bin/python -m unittest discover arm64-docker/tools/tests -v`
- Whitespace check: `git diff --check`
- Secret scan: run the project secret regex over changed docs/tools and review broad-scan false positives from converted vendor PDF examples separately.
- ASCII scan: run over changed docs/tools; broad `api-audit` scans include pre-existing generated CSV/catalog formatting.
