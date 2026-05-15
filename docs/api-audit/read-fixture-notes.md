# Axxon One Read Fixture Notes

This file tracks read-only sweep methods that need non-empty parameters, active subsystems, or seed data.

Latest verified direct-gRPC read sweep:

- PASS: `117`
- WARN: `32`
- FAIL: `0`

## Fixed Fixtures

These methods previously warned with empty/default requests and now pass with precise live fixtures:

- `axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo`
  - Fixture source: `SecurityService.ListRoles`
  - Request uses the admin role ID when present, otherwise the first available role ID.
- `axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages`
  - Fixture source: `LayoutManager.ListLayouts`
  - Request uses the current layout ID when present, otherwise the first listed layout ID.

## Remaining Warning Groups

These are still warning on the current local ARM64 lab. Most are not generic empty-request bugs; they require configured subsystems or seed objects.

- Archive backup source:
  - `BackupSourceService.IsBackupInProgress`
  - `BackupSourceService.GetRestProgress`
  - Needs a backup-capable source/task state. AliceBlue source AP still returns server-side execution errors.
- Cloud:
  - `CloudService.GetBindingConfiguration`
  - Needs cloud binding configured.
- Discovery:
  - `DiscoveryService.Probe`
  - Needs real connection info; do not broad-scan arbitrary networks in the generic sweep.
- Text events:
  - `TextEventSupportService.GetTextEvent`
  - Needs a valid text event source/event fixture.
- Global tracker:
  - `GlobalTrackerService.GetGlobalTrackerProfiles`
  - `GlobalTrackerService.GetGlobalTrackBestVisibilityPositions`
  - Current service behavior is unimplemented or missing object state on this lab.
- Logic counters:
  - `LogicService.GetCounterState`
  - `LogicService.GetCounterGroupState`
  - Needs at least one configured counter. `ListCounters` currently returns no counters.
- Maps:
  - `MapService.GetMapImage`
  - `MapService.GetMapProvider`
  - Needs at least one configured map/provider. `ListMaps` and `ListMapProviders` currently return empty.
- Export:
  - `ExportService.GetSessionState`
  - Covered by `export-smoke-latest.md`, which creates temporary export sessions, polls state, downloads a bounded result, and destroys them. Generic read sweeps can still report fixture-needed when no session id is supplied.
- Notifications:
  - `EMailNotifier.GetActionState`
  - `EMailNotifier.GetSendMode`
  - Needs notification service/action state configured.
- PTZ and tag-and-track:
  - `TelemetryService.GetPositionInformation`
  - `TelemetryService.GetPositionInformationNormalized`
  - `TelemetryService.GetPresetsInfo`
  - `TelemetryService.GetAuxiliaryOperations`
  - `TelemetryService.GetTours`
  - `TelemetryService.GetTourPoints`
  - `TagAndTrackService.ListTrackers`
  - Current virtual cameras are not PTZ/tag-and-track fixtures.
- Realtime recognizer:
  - `RealtimeRecognizerService.GetLists`
  - `RealtimeRecognizerService.GetListStream`
  - `RealtimeRecognizerService.GetItems`
  - `RealtimeRecognizerExternalService.GetData`
  - Needs recognizer service and list/data fixtures.
- Security LDAP:
  - `SecurityService.GetLDAPSynchronizationState`
  - `SecurityService.SearchLDAP`
  - Needs LDAP configured.
- Generic settings:
  - `GenericSettingsService.GetSettings`
  - Empty context fails validation; random GUIDs return not found. Needs a known settings context.
- State control:
  - `StateControlService.GetDefaultState`
  - `StateControlService.GetCurrentState`
  - Camera APs resolve but return server-side state command errors on this lab.
- Video wall:
  - `VideowallService.BatchGetWalls`
  - `VideowallService.GetMyControlData`
  - Needs configured wall access points or control cookie/session fixture.

## Next Fixture Priorities

1. Configure one logic counter, then add `GetCounterState` and `GetCounterGroupState` fixtures.
2. Create one map/provider fixture, then add `GetMapImage` and `GetMapProvider` fixtures.
3. Start one export session with a rollback/cleanup plan, then add `GetSessionState`.
4. Configure a known generic settings context or create a temporary safe settings record, then add `GetSettings`.
5. Leave PTZ, LDAP, cloud, realtime recognizer, video wall, and email notifier as subsystem-required until those services are configured in the lab.
