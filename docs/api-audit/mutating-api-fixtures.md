# Mutating API Fixture Strategy

Mutating APIs are not run by the generic sweep. They require isolated fixtures, pre/post snapshots, and rollback steps.

## Rules

- Do not run destructive APIs against real production servers.
- Do not mutate the root user, license state, system timezone, global security policy, or archive storage unless the user explicitly requests it.
- Prefer temporary objects with a `codex-` prefix and deterministic cleanup.
- Snapshot affected state before mutation and verify rollback.
- Store only sanitized summaries in reports.

## Low-Risk Fixture Candidates

Shared key-value storage:

- APIs: `SharedKVStorageService.Commit`, `BatchGetRecords`, `ListRecords`, `GetRecordsStream`.
- Fixture: temporary key `codex-api-probe-*` with JSON payload.
- Rollback: remove the key and verify `ListRecords` absence and no value from `BatchGetRecords`.
- Current status: live-tested as `tested-pass-safe-record`; reusable tool is `arm64-docker/tools/axxon_mutating_fixture_sweep.py`.

Current implemented mutating fixture:

- `arm64-docker/tools/axxon_mutating_fixture_sweep.py`
- Creates a temporary `codex-mutating-fixture-*` SharedKV record.
- Reads it through `BatchGetRecords`.
- Streams it through `GetRecordsStream`.
- Removes it through `Commit`.
- Verifies rollback through `ListRecords` and `BatchGetRecords`.

Bookmarks:

- APIs: `BookmarkService.CreateBookmark`, `UpdateBookmark`, `DeleteBookmark`, `SetExportedTime`, `RenderTrack`.
- Fixture: short bookmark on a known camera/archive time range, message prefixed `codex-`.
- Rollback: delete the bookmark by ID and verify it is absent from `ListBookmarks`.
- Risk: requires a valid archived time range.

Maps:

- APIs: `MapService.ChangeMaps`, `UpdateMarkers`.
- Fixture: temporary map ID prefixed `codex-` with a minimal image and marker set.
- Rollback: remove the map or marker and verify `ListMaps`/`BatchGetMaps`.
- Risk: map ownership/sharing semantics must be captured before update.

Layouts:

- APIs: `LayoutManager.Update`.
- Fixture: temporary layout with a `codex-` ID or isolated user-owned layout.
- Rollback: remove or restore original layout by saved etag.
- Risk: avoid modifying operator default layouts.

Logic counters/macros:

- APIs: `LogicService.ChangeCounters`, `CounterAction`, `ChangeMacros`, `LaunchMacro`.
- Fixture: temporary counter or macro prefixed `codex-`.
- Rollback: remove object and verify list absence.
- Risk: macros can trigger operational side effects. Do not launch macros without explicit content review.

## Medium-Risk Fixture Candidates

Configuration/device changes:

- APIs: `ConfigurationService` mutating methods.
- Fixture: virtual camera or detector created specifically for test.
- Rollback: remove the virtual device/detector and verify inventory returns to baseline.
- Risk: can disrupt video pipelines and analytics.

Export sessions:

- APIs: export create/cancel/delete methods.
- Fixture: short clip from known local video archive.
- Rollback: cancel/delete export session and remove generated files.
- Risk: disk usage and long-running jobs.
- Verified workflow: `export-smoke-latest.md` covers gRPC snapshot export/download/destroy and live stop/destroy with temporary `codex-*` sessions; `http-export-smoke-latest.md` covers legacy HTTP one-frame JPEG export/status/download/delete.

PTZ sessions:

- APIs: `TelemetryService.AcquireSessionId`, `KeepAlive`, `ReleaseSessionId`, movement/preset/tour methods.
- Fixture: a non-production PTZ-capable virtual or lab camera.
- Rollback: release session and return PTZ to known preset.
- Risk: can move physical cameras; do not run on real PTZ devices without approval.

## High-Risk Or Gated APIs

Security:

- Password/login/TFA changes.
- Role/user/permission mutation. `security-mutation-smoke-latest.md` verifies this only for temporary UUID-indexed `codex-*` role/user records and temp-role permissions.
- LDAP synchronization start/stop. Temporary LDAP directory add/edit/remove is verified, but sync/search still needs a real LDAP fixture.
- Global security policy changes. No-op password-policy/IP-filter/trusted-IP writes from the current snapshot are verified; real policy changes still need explicit restore plans.

System and storage:

- Timezone and NTP setters.
- Archive partition format/resize/reindex/clear.
- License/binding methods.
- Domain/node management.

Media and downloads:

- File downloads and media streams should have byte/time limits before automated testing.

## Snapshot Checklist

Before a mutating test, capture:

- Target service and method.
- Target access point, object ID, or user/role ID.
- Current object representation or list count.
- Expected post-mutation state.
- Rollback method and rollback verification.

After a mutating test, capture:

- Method status and response shape.
- Created/updated/deleted object ID.
- Rollback status.
- Final verification result.

## Mutation Review Checklist

[ ] User approved the exact target stand.
[ ] Preflight snapshot saved.
[ ] Rollback request generated before mutation.
[ ] Mutation scoped to a test object.
[ ] Verification command identified.
[ ] Cleanup command identified.
[ ] No secrets in report.

## Detailed Playbooks

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
