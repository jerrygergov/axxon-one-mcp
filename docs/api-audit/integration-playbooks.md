# Axxon One API Integration Playbooks

This document maps common plugin and vertical-integration needs to the Axxon One gRPC/HTTP APIs verified in this local ARM64 lab.

For runnable examples, source mapping to `Integration APIs 3.0.pdf`, and demo-stand evidence, start with:

- `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- `arm64-docker/docs/api-audit/demo-stand-2026-05-01.md`
- `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.md`
- `arm64-docker/docs/api-audit/pdf-gap-coverage-summary.md`

## Baseline Client Pattern

Prefer the reusable local client for new Python tooling:

- `arm64-docker/tools/axxon_api_client.py`
- Usage examples: `arm64-docker/docs/api-audit/client-sdk-usage.md`
- Runnable examples: `arm64-docker/tools/examples/`

It handles local Docker TLS, gRPC auth metadata, HTTP `/grpc` Basic-to-Bearer auth, `/v1` requests, response parsing, sanitizing, and common inventory/archive fixtures.

The comprehensive probe, read-only sweep, event-search CLI, HTTP sweeps, and example scripts now share this client path. Keep new integration code on this path unless there is a specific reason to test raw transport behavior.

Use direct gRPC when building durable integrations:

- Connect to `127.0.0.1:20109` with TLS.
- Use `api.ngp.root-ca.crt` as the root CA.
- Set `grpc.ssl_target_name_override` to `F4E66972EC19` for the local Docker certificate.
- Call `axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2` first without auth metadata.
- Reconnect or wrap calls with metadata from `token_name` and `token_value`.
- Iterate server-streaming responses even when only one page is expected.

Use HTTP for quick checks, web-adjacent integrations, or environments where gRPC is inconvenient:

- Authenticate through `POST /grpc` with Basic auth and method `axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2`.
- Use `Authorization: Bearer <token_value>` for follow-up `/grpc` calls.
- Expect server-streaming `/grpc` responses to use multipart or `text/event-stream` wrappers.
- Prefer annotated `/v1/...` GET endpoints for lightweight inventory/status checks.

## Audit Tooling

Use these reports before choosing APIs for a plugin:

- `grpc-api-catalog.md`: full proto-derived method catalog.
- `http-endpoints-catalog.md`: full annotated `/v1/...` endpoint catalog.
- `live-readonly-sweep-latest.md`: direct-gRPC read behavior.
- `http-grpc-sweep-latest.md`: HTTP `/grpc` wrapper parity for direct-pass unary reads.
- `http-v1-sweep-latest.md`: safe annotated `/v1` GET plus read-like POST endpoint behavior.
- `mutating-fixture-sweep-latest.md`: controlled write/rollback behavior.
- `fixture-discovery-latest.md`: current availability of PTZ, control-panel, water-level, export-agent, map, template, and detector fixtures.
- `mutation-playbooks/`: rollback plans for unsafe API families.

The default HTTP sweeps are intentionally conservative. They test direct-gRPC-passing read methods by default, include safe read-like POST `/v1` endpoints, and leave fixture-needed methods behind opt-in flags.

Use these runnable examples as starting templates before building a plugin:

- `inventory_sync.py`: baseline inventory bootstrap.
- `event_search_summary.py`: event polling/search foundation for bots and notification integrations.
- `camera_archive_status.py`: archive availability and storage health.
- `metadata_tracker_stream.py`: live analytics/object-tracker validation.
- `http_grpc_vs_grpc.py`: direct gRPC versus HTTP `/grpc` wrapper comparison.

## Inventory And Discovery

Primary APIs:

- `DomainService.GetVersion`
- `DomainService.GetHostPlatformInfo`
- `DomainService.ListNodes`
- `DomainService.ListCameras`
- `DomainService.BatchGetCameras`
- `DomainService.ListArchives`
- `DomainService.ListComponents`
- `ConfigurationService.ListUnits`
- `ConfigurationService.ListUnitsByAccessPoints`

Use this for:

- VMS inventory sync.
- Camera and archive selection UIs.
- Plugin bootstrap and health pages.
- Mapping camera access points to configuration units.

Local findings:

- Current local lab has one node, two cameras, three archives, and 22 components.
- The external demo stand has one node, 33 cameras, 14 archives, and 200 components.
- Main archive access point is `hosts/F4E66972EC19/MultimediaStorage.AliceBlue/MultimediaStorage`.
- Demo main archive access point is `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`.
- Object-tracker metadata endpoint is `hosts/F4E66972EC19/AVDetector.2/SourceEndpoint.vmda`.
- Demo metadata stream proof uses `hosts/Server/AVDetector.1/SourceEndpoint.vmda` on camera `Tracker`.

## Events And Search

Primary APIs:

- `EventHistoryService.ReadEvents`
- `EventHistoryService.ReadCount`
- `EventHistoryService.ReadLprEvents`
- `EventHistoryService.ReadTextEvents`
- `EventHistoryService.ReadAlerts`
- `EventHistoryService.FindByPrompt`
- `EventHistoryService.FindSimilarObjects`
- `EventHistoryService.FindStrangers`

Use this for:

- Telegram or incident-notification bots.
- LPR event search.
- Alarm dashboards.
- Vertical event correlation.
- Operator audit/troubleshooting views.

Local findings:

- Recent local history is dominated by detector line-crossing events.
- `ReadLprEvents` works but currently returns no LPR rows on this lab.
- The reusable CLI is `arm64-docker/tools/axxon_event_search.py`.
- The demo stand has live face, LPR/MMR, tracker, and traffic-analyzer history. Good fixture cameras are `Face`, `LPR + MMR`, `Tracker`, and `Traffic Analyzer RR 1`.
- On the demo stand, general `ReadEvents` with a camera subject is more useful than `ReadLprEvents` alone for mixed LPR detector and realtime recognizer examples.

## Metadata And Analytics

Primary APIs:

- `MetadataService.PullMetadata`
- `DomainService.ListComponents`
- `DomainService.GetCamerasByComponents`

Use this for:

- Live object tracking.
- Detector health validation.
- Analytics-to-camera mapping.
- Future vertical integrations that need tracklets, object IDs, or detector samples.

Local findings:

- `PullMetadata` against the VMDA endpoint is the best proof that object tracking is actually producing data.
- In this ARM Docker lab, the object tracker should use CPU decoder mode.
- On the demo stand, generic first-candidate VMDA selection can choose an endpoint with no samples in the short probe window. Prefer resolving endpoints with `GetCamerasByComponents` and sampling candidates; `hosts/Server/AVDetector.1/SourceEndpoint.vmda` returned live tracklets.

## Archive And Video Availability

Primary APIs:

- `ArchiveService.GetArchiveTraits`
- `ArchiveService.GetVolumesState`
- `ArchiveService.GetDiskSpace`
- `ArchiveService.GetHistory2`
- `ArchiveService.GetCalendar`
- `ArchiveService.GetSize`

Use this for:

- Archive health checks.
- Timeline availability.
- Retention dashboards.
- Storage utilization reports.

Local findings:

- Archive APIs need real archive and source access points. Empty/default requests correctly return fixture-needed errors.
- Prefer the AliceBlue archive AP in this lab.
- Embedded storage APs may appear in inventory but are not always valid for archive service calls.
- Current archive fixtures use the AliceBlue archive AP for traits/volume/disk and a real `/Sources/src.*` AP for history/calendar/size.
- HTTP `/v1/archive/size` still returns HTTP 500 on this lab even though direct gRPC `GetSize` passes; treat this as wrapper or endpoint-specific behavior.
- The demo stand returned real archive history intervals and calendar days through direct gRPC. Direct gRPC and HTTP `/grpc` `GetSize` passed, while `/v1/archive/size` returned HTTP 500.

## Media And Export

Primary APIs:

- `ExportService.ListSessions`
- `ExportService.StartSession`
- `ExportService.GetSessionState`
- `ExportService.DownloadFile`
- `ExportService.StopSession`
- `ExportService.DestroySession`
- `MediaService.Stream`
- `MediaService.RequestConnection`
- `MediaService.AwaitConnection`
- `MediaService.ConnectEndpoint`

Use this for:

- Export status dashboards.
- Clip retrieval workflows.
- Live video or media tunnel integrations.

Current strategy:

- Keep media streaming and file-download tests out of the generic read sweep.
- Use `axxon_export_smoke.py` for gRPC export lifecycle proof: temporary `codex-*` archive snapshot export, bounded download, live stop, and destroy cleanup.
- Use `axxon_http_export_smoke.py` for legacy HTTP export proof: one-frame JPEG `POST /export/archive/...`, status polling, bounded file download, and `DELETE /export/{id}` cleanup.
- Test them only with explicit endpoints, time windows, byte limits, and cleanup rules.

## Configuration And Device Catalog

Primary APIs:

- `ConfigurationService.ListUnits`
- `ConfigurationService.ListTemplates`
- `DevicesCatalog.ListVendors`
- `DevicesCatalog.ListDevices`
- `DevicesCatalog.GetDevice`
- `FileSystemBrowser.ListDirectory`
- `FileSystemBrowser.GetFileInfo`
- `FileSystemBrowser.GetSpace`

Use this for:

- Device onboarding assistants.
- Deployment validators.
- Archive folder and filesystem checks.
- Configuration browsers.

Local findings:

- Virtual camera creation on this image uses `vendor=Virtual`, `model=Virtual`.
- `vendor=axxonsoft`, `model=Virtual` failed on this image.
- `/data` is the useful mounted data root in the container.

## Layouts, Maps, And Visual UI

Primary APIs:

- `LayoutManager.ListLayouts`
- `MapService.ListMaps`
- `MapService.BatchGetMaps`
- `MapService.GetMapsByComponent`
- `MapService.ListMapProviders`

Use this for:

- Web dashboards.
- Operator workspace export.
- Map-aware vertical integrations.

Current lab state:

- Layout listing works and returns local layouts.
- Map reads work, but image/provider lookup needs valid IDs and permissions.
- The demo stand has 20 layouts, one slideshow, five maps, and two map providers, making it the preferred fixture for UI/workspace examples.

## Security And Permissions

Primary APIs:

- `SecurityService.ListRoles`
- `SecurityService.ListUsers`
- `SecurityService.GetRestrictedConfig`
- `SecurityService.ListGlobalPermissions`
- `SecurityService.ListObjectPermissions`
- `SecurityService.ListUserGlobalPermissions`

Use this for:

- Role-aware plugin behavior.
- Current-user capability checks.
- Integration setup validation.

Security rules:

- Do not log passwords, bearer tokens, license keys, serial numbers, or full security payloads.
- Reports should store counts and response shapes, not full user/role contents.
- Password, login, TFA, permission-set, and config-change methods require explicit fixture and rollback plans.

## PTZ And Telemetry

Primary APIs:

- `TelemetryService.IsSessionAvailable`
- `TelemetryService.GetPositionInformation`
- `TelemetryService.GetPresetsInfo`
- `TelemetryService.GetAuxiliaryOperations`
- `TagAndTrackService.ListTrackers`

Use this for:

- PTZ capability checks.
- Preset/tour discovery.
- Tag-and-track integrations.

Current lab state:

- The local virtual cameras are not PTZ fixtures.
- PTZ read methods generally need a valid telemetry component access point.
- Movement/session methods are not safe for generic sweeps.

## Health And Operations

Primary APIs:

- `grpc.health.v1.Health.Check`
- `StatisticService.GetStatistics`
- `LicenseService.LicenseKeyInfo`
- `LicenseService.GetGlobalRestrictions`
- `LicenseService.GetNodeRestrictions`
- `LicenseService.IsPossibleToLaunch`

Use this for:

- Integration readiness checks.
- License-gated feature validation.
- Node resource monitoring.

Local findings:

- Health check returns `SERVING`.
- Statistics, license info, restrictions, and launch feasibility are verified in the comprehensive probe.

## Recommended Build Order For Plugins

1. Implement authentication and TLS handling.
2. Implement inventory sync with DomainService.
3. Add event search with EventHistoryService.
4. Add metadata or archive APIs only after inventory mapping is correct.
5. Add HTTP `/grpc` parity only where required by the integration runtime.
6. Add mutating APIs last, with fixtures and rollback.
