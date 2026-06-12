# Axxon One All-In-One MCP Roadmap

**Reconciled:** 2026-06-11  
**Purpose:** define the full VMS/API capability surface the MCP should cover, compare it with this repository, and give future builders a task-first map without relying on chat history.

## Source Baseline

This roadmap is derived from:

- `README.md`, `docs/COVERAGE.md`, and `docs/api-audit/mcp-corpus/*.json`.
- Local Integration APIs 3.0 PDF extraction in `docs/integration-apis-3.0/` and the gitignored source PDF `Integration APIs 3.0.pdf`.
- Local gitignored proto files under `docs/grpc-proto-files/axxonsoft/`.
- Public Axxon One 3.0 documentation landing page and linked product capability pages:
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314535799/Documentation
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314536014/Searching%2Badding%2Bconfiguring%2Band%2Bremoving%2BIP%2Bdevices
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314536342/%D0%90rchive
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314536446/Detectors
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314537414/Programming
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314538496/Live%2Bvideo%2Bsurveillance
  - https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314539163/Event%2Bcontrol

The public site states that Integration API documentation is not public and must be requested through AxxonSoft. This repo must keep proto files, the PDF, CA files, tickets, and copied API source text out of git.

## Current Numbers

| Metric | Current value | Source/check |
| --- | ---: | --- |
| AxxonSoft proto files | 98 | `find docs/grpc-proto-files/axxonsoft -name '*.proto'` |
| gRPC services | 51 | `docs/grpc-proto-files/SERVICE_INDEX.md` |
| gRPC RPCs | 361 | `docs/api-audit/mcp-corpus/api_methods.json` |
| RPCs live-verified | 286 | `tested-pass*` statuses in `api_methods.json` |
| RPCs fixture-blocked | 55 | `tested-warn-fixture-needed` statuses |
| RPCs pending | 20 | deliberate destructive/infra operations |
| HTTP `/v1` endpoints cataloged | 221 | `docs/api-audit/mcp-corpus/http_endpoints.json` |
| Actual all-enabled MCP tools | 293 | 288 server-local decorators plus 5 delegated translator tools |
| Advertised capability groups | 48 | `CAPABILITY_GROUPS` in `tools/axxon_mcp_server.py` |
| Generator templates | 14 x Python + Node | `TEMPLATE_CATALOG` in `tools/axxon_mcp_generator.py` |
| Services with intent-level tool coverage | 44 / 51 | all except the seven fixture/infra tails listed below |

Important counting rule: the old AST shortcut counted only decorators in `tools/axxon_mcp_server.py` and reported 286 tools. The runtime all-enabled server also registers five delegated translator tools from `tools/axxon_mcp_translator.py`: `assemble_recipe`, `validate_recipe`, `explain_recipe`, `resolve_device`, and `run_recipe`.

## Target Architecture

The all-in-one MCP should stay layered:

| Layer | Target behavior |
| --- | --- |
| Knowledge | Search API corpus, docs, endpoint catalog, verified examples, fixtures, known behaviors, safety policies, and task recipes with no server connection. |
| Runtime client | One shared `AxxonApiClient` path for direct gRPC with TLS CN override, HTTP `/grpc`, legacy HTTP, `/v1`, auth/session handling, retries, redaction, and caps. |
| Live read-only | Inventory, states, events, archive intervals, statistics, metadata samples, media/export probes, layouts/maps/walls, security/license summaries, and bounded subscriptions. |
| Controlled operator | Plan/apply/verify/rollback workflows with confirmation tokens for every mutation; dry-run by default for high-risk or destructive classes. |
| Partner authoring | Python/Node generators, plugin scaffold/lint/package, natural-language recipe assembly, and runnable examples for integrations. |
| Safety/audit | Read-only mode, per-group enable flags, per-tool risk classes, rollback classification, stream/file caps, no secret/media-byte leakage, and sanitized evidence. |

## Product Capability Map

| Product/API area | Full MCP capability target | Current project status | Next gap |
| --- | --- | --- | --- |
| Domain and inventory | Discover nodes, servers, cameras, archives, devices, components, access points, capabilities, maps, and object relationships. | Strong via `live`, `view`, `admin`, `domain_topology`, `devices_catalog`, and Phase 1 `site_graph`. | Add richer planner recipes that consume the site graph for onboarding, search, and integration generation. |
| IP device onboarding | Discover devices, browse supported vendors/models, probe devices, create cameras, apply templates, bulk import, set archive recording, assign coordinates. | Strong for catalog/discovery and operator camera/template workflows; partial for bulk CSV/import UX. | Add a bulk onboarding planner that validates CSV/JSON and emits one rollbackable plan per camera. |
| Configuration tree | List units/templates/factories, inspect properties, change unit properties, create/remove devices/detectors/archives/layouts/maps/macros. | Strong generic config and many intent workflows. | Add schema-first config assistant that exposes property descriptors, constraints, defaults, and before/after diff. |
| Detectors and analytics | Configure AVDetector/AppDataDetector/RealtimeRecognizer/GlobalTracker, detector masks/areas, metadata schemas, tracks, heatmaps, archive analytics search. | Strong common detector workflows and reads; partial for GlobalTracker and RealtimeRecognizerExternal fixtures. | Add detector playbooks for every documented detector family and fixture-gated global tracking profile workflows. |
| Live video and snapshots | Produce safe live stream URLs, snapshots, stream health, GreenStream/high-low quality hints, media transport probes, bounded media samples. | Strong for safe URLs/snapshots/probes; raw streaming is capped. | Add embeddable video component and web-client helper docs/templates. |
| Archive viewing | Archive history, calendars, intervals, scrub/frame/MJPEG, stream info, bookmarks, protected clips, delete intervals, reindex/format/resize. | Strong for safe reads and bookmark lifecycle; partial for destructive archive maintenance. | Put clear/format/reindex/delete under explicit destructive Phase C plans with throwaway fixtures. |
| Search | Event search, LPR/text/alert/bookmark search, VMDA/object/prompt/similar/stranger search, heatmap searches. | Strong for event and VMDA/heatmap paths when fixtures exist. | Add task-first search tools that hide RPC shape and return dashboard-ready aggregates. |
| Events and alarms | Historical event reads/counts, bounded live subscriptions, detector/external events, alarm lifecycle, alert review/escalation, dashboards. | Strong via `live`, `alarms`, `logic_alerts`, `admin`, `audit`, external event workflows. | Add WebSocket `/events` parity when a Web server fixture is available. |
| Macros and automation | Create/edit/run macros, start conditions, actions, counters, arm-state rules, notification actions, web queries, external app actions. | Strong for macros, counters, arm state, alert lifecycle; partial for email/GSM notifier infra. | Add macro action catalog and notification fixture-gated send tools. |
| PTZ, telemetry, tag-and-track | Sessions, movement, zoom/focus/iris, presets, tours, auxiliary ops, PTZ priority, Tag&Track mode/follow/move. | Strong PTZ core; Tag&Track fixture-blocked. | Add Tag&Track first-class group once a configured component and non-production PTZ fixture exist. |
| ACFA and device control | ACFA action/state/event/visualization catalogs, perform actions, download data, state control. | Strong ACFA and StateControl tools; control-panel/water-level fixtures still needed. | Add device-control discovery that explains missing fixtures and safe actions before execution. |
| Layouts, maps, videowalls, client UI | Layout CRUD, map CRUD/images/markers/providers, videowall register/change/control data, Client HTTP API screen/layout control. | Strong server-side layout/map/wall coverage; partial for Client HTTP API target. | Add client-local HTTP API profile and remote operator-screen helpers when a client fixture is reachable. |
| Security and identity | Auth sessions, users, roles, permissions, LDAP, policies, IP filters, TFA, password/login changes, current-user capability checks. | Strong reads and some gated credential/admin workflows; TFA/LDAP advanced paths fixture-blocked. | Add isolated test-user fixture playbooks for TFA, LDAP sync/search, and permission mutation evidence. |
| License and restrictions | Key/restriction reads, launch checks, host info, distribute/drop keys, license documents. | Strong reads; distribute/drop/document creation pending by design. | Phase C destructive license tools with explicit throwaway license policy and irreversible labeling. |
| Settings/time/server | Domain storage/export/GDPR/bookmark settings, generic settings, time zones, NTP, log level/drop logs. | Strong with gated mutations. | Add grouped "configuration posture" report and rollback snapshots for every settings group. |
| Maintenance and backup | Config revision info, collect backup, set revision, restore backup, archive backup bundle/make/cancel/progress. | Partial: backup collect probe exists; restore/set revision/BackupSource pending. | Phase C maintenance tools with backup target fixtures and "irreversible" warnings. |
| Cloud and packages | Cloud binding config/bind/unbind, installation package availability/download. | Partial reads/checks; cloud bind and package download pending. | Add fixture-gated cloud binding planner and package download cap/path controls. |
| Notifications | Email/SMS notifier state/mode and send operations; macro notification actions. | Missing first-class intent tools; pending or fixture-blocked. | Add notification preflight and gated send tools once SMTP/GSM fixtures exist. |
| HTTP, WebSocket, embeddable video | `/v1` endpoint lookup, legacy HTTP examples, HTTP `/grpc`, WebSocket camera events, Client HTTP API, embeddable video component. | Strong docs/generator support; partial live verification for WebSocket/client/video component. | Add dedicated `client_api` and `web_api` groups for reachable client/Web server fixtures. |
| Partner/plugin generation | Python/Node code generation, templates, plugin scaffold/lint/package, NL recipe translator. | Strong: 14 templates in both languages, partner packaging, translator tools. | Add C# only when compile-verifiable; add signed package distribution only when a real untrusted channel exists. |

## Service-By-Service Coverage Matrix

| Service | Desired MCP surface | Current coverage | Remaining work |
| --- | --- | --- | --- |
| `AcfaService` | ACFA actions, visualizations, events, states, unit types, data download. | Covered by `control` plus inventory reads. | More hardware-specific action playbooks. |
| `ArchiveService` | Traits, recording info, history/calendar/size, seek, resize, clear, format, reindex, disk/volume state, archive bookmarks. | Safe reads, archive intervals, archive policy, views, volume state. | Destructive maintenance plans for clear/format/reindex/delete with throwaway archive fixtures. |
| `ArchiveVolumeService` | Probe archive volume suitability. | Covered by `archive_volume` and `misc_reads`. | Promote into onboarding/archive planner. |
| `BackupSourceService` | Bundle/make/cancel backup and progress. | Missing first-class group. | Phase C gated backup tools with target path and rollback/cancel semantics. |
| `AuditEventInjector` | Inject audit events for client actions, archive/camera viewing, export, PTZ, LDAP setup. | Covered by `audit`. | Add stricter audit-kind schema examples. |
| `AuthenticationService` | Authenticate variants, MFA/approval, public key, session info/renew/close. | Basic session tools covered by `auth_sessions`; advanced MFA fixture-blocked. | TFA/supervisor/public-key fixture playbooks. |
| `BookmarkService` | List/get/create/update/delete, exported time, render track. | Covered by `bookmarks` and `bookmark_extras`. | Add higher-level incident bookmark recipes. |
| `CloudService` | Binding config, bind, unbind. | Missing mutating group; read fixture gap. | Phase C cloud-binding planner with irreversible/secrets policy. |
| `ConfigurationService` | Units/templates/factories, ChangeConfig, ChangeTemplates, assignments, similar units. | Strong via `live`, `operator`, `config_change`, `devices_catalog`. | Schema-first diff/planner for arbitrary config edits. |
| `DevicesCatalog` | Vendors, devices, traits. | Covered by `devices_catalog`. | Use catalog in bulk camera onboarding validation. |
| `DynamicParametersService` | Dynamic config parameter/device data acquisition. | Covered by `misc_reads`. | Surface as device wizard helper. |
| `FileSystemBrowser` | Directory/file/space reads. | Covered by `filesystem_browser`. | Add path allow/deny policy for locked deployments. |
| `ServerSettings` | Log level and log cleanup. | Covered by `server_settings`. | Add log drop irreversible labeling to docs output. |
| `SharedKVStorageService` | List/get/stream/commit shared records. | Covered by `shared_kv`. | Add plugin-state recipes. |
| `ExternalDetectorService` | Raise occasional/periodical external detector events. | Covered indirectly by operator workflows and generator templates. | Add first-class external detector group with periodical event lifecycle. |
| `DiscoveryService` | Discover/probe devices and progress streams. | Covered by `discovery`. | Add discovery-to-camera-onboarding flow. |
| `DomainService` | Domain topology, host info, cameras, archives, devices, components, maps, access-point mapping. | Strong via `live`, `view`, `admin`, `domain_topology`, and the Phase 1 `site_graph` join. | Add planner-specific graph slices once downstream planners need smaller views. |
| `DomainManager` | Enumerate/add/drop nodes, proclaim domain. | Read enumeration covered. | Phase C destructive multi-node domain tools only with throwaway targets. |
| `TextEventSupportService` | Resolve text-event details. | Missing first-class group. | Add POS/text-event group when fixture exists. |
| `EventHistoryService` | Events/counts/text/LPR/alerts/bookmarks/prompt/similar/stranger searches. | Strong via `live`, `alarms`, `metadata`, `heatmap`. | Add dashboard-ready aggregate wrappers. |
| `DomainNotifier` | Domain live event subscriptions, details, update/disconnect, diagnostics push. | Bounded event subscriptions covered. | Diagnostic push/detail lifecycle behind review gates. |
| `NodeNotifier` | Node live event subscriptions, details, update/disconnect, diagnostics, ping. | Bounded subscriptions and ping/health pieces covered. | Diagnostic push/detail lifecycle behind review gates. |
| `GlobalTrackerService` | Profiles, binding, clearing, best visibility positions. | `GetProfile` covered; rest fixture-blocked. | GlobalTracker profile fixture and image/privacy policy. |
| `GroupManager` | Group list/batch/change and object membership. | Covered by `groups`. | Bulk membership planner. |
| `HeatMapService` | Build/query heatmaps. | Covered by `heatmap`. | More typed query recipes per detector/search use case. |
| `LayoutImagesManager` | List/upload/download/remove layout images. | List/download covered through `view_objects`; upload/remove partial. | Add upload/remove with size/type caps and rollback. |
| `LayoutManager` | Layout list/batch/update/on-view/cleanup. | Covered by `layout_manager`, `view_objects`, `operator`, `gdpr_cleanup`. | Rich visual layout diff and cell editor recipes. |
| `LicenseService` | License reads/restrictions/launch checks, distribute/drop, documents. | Reads covered by `admin`/`license_reads`. | Phase C destructive/license-document tools. |
| `EventDescription` | Event grouping and field descriptors. | Covered by `event_taxonomy`. | Use descriptors in event query builder. |
| `LogicService` | Macros, alerts, arm state, counters, config, scripts. | Strong via `logic_control`, `alarms`, `logic_alerts`, `operator`. | Full macro action/condition catalog and script fixtures. |
| `ConfigurationManager` | Revision info, set revision, collect backup, restore backup. | Revision/read/collect probe covered. | Phase C set/restore backup client-stream tools. |
| `MapService` | Maps, images, markers, providers, cleanup. | Covered by `view_objects`, `map_providers`, `operator`, `gdpr_cleanup`. | Add map image upload and marker bulk planner. |
| `MediaService` | Bidi stream, connection/QoS/tunnel, endpoint bridging. | Covered as capped probes by `media`; live/archive view wraps safe paths. | Add production stream adapters outside MCP response body. |
| `MetadataService` | Bidi metadata stream. | Covered by `metadata` and live metadata sample. | Add typed track normalization for dashboards. |
| `ExportService` | Export sessions, state, stop/destroy, download stream. | Generator/export smokes exist; not a first-class live MCP group. | Add `export` group with job caps, download path policy, cleanup. |
| `NgpNodeService` | Scene description. | Covered by `scene_description`. | Merge scene geometry with detector/map planners. |
| `EMailNotifier` | Send email, state, send mode. | Missing first-class group. | SMTP fixture-gated notification group. |
| `GSMNotifier` | Send SMS, state. | Missing first-class group. | GSM fixture-gated notification group. |
| `InstallationPackageProvider` | Check/download installer packages. | Availability covered. | Download package stream with cap and destination policy. |
| `TagAndTrackService` | List trackers, set mode, follow track, move to coordinates. | Missing first-class group; fixture-blocked. | Add `tag_and_track` group after configured component and PTZ fixture exist. |
| `TelemetryService` | PTZ session, move/zoom/focus/iris, presets, tours, aux ops. | Strong PTZ group; some modes fixture-blocked. | More device-mode fixtures and safe tour/patrol rollback. |
| `RealtimeRecognizerService` | Recognition lists/items reads/writes/clear. | Covered by `recognizer` and `recognizer_write`. | Biometric/image privacy-safe import/export policy. |
| `RealtimeRecognizerExternalService` | External recognizer data retrieval. | Missing first-class group; fixture-blocked. | Add read-only retrieval once fixture exists. |
| `SecurityService` | Users, roles, LDAP, policies, permissions, passwords/logins, TFA. | Strong reads and selected gated mutations. | TFA/LDAP/permissions mutation evidence with isolated users. |
| `DomainSettingsService` | Data storage, export, GDPR, bookmark settings. | Covered by `settings`. | Settings posture report with rollback snapshots. |
| `GenericSettingsService` | Get/save/remove generic settings. | Covered by `misc_reads`. | Namespace allowlist guidance. |
| `StateControlService` | Current/default state reads and gated state writes. | Covered by `state_control`; live-verified with reversible SetState evidence. | Discover state-controllable APs automatically. |
| `StatisticService` | Statistics reads. | Covered by `statistics`. | Dashboard aggregation recipes. |
| `TimeZoneManager` | Timezones, NTP, set/get/change. | Covered by `timezone`. | Multi-node time drift report. |
| `VideowallService` | Register/change/unregister, control data, list/get walls. | Covered by `videowall` and view reads. | Client/display orchestration recipes. |
| `VMDAService` | Enumerate schemes, typed queries, cleanup. | Covered by `metadata`, `heatmap`, `control`. | More query builders and cleanup safeguards. |

## HTTP, Client, And Web API Surface

The local HTTP corpus catalogs 221 annotated `/v1` endpoints. Exact paths live in `docs/api-audit/mcp-corpus/http_endpoints.json`; this roadmap groups them by partner task:

| HTTP/API family | Desired MCP/tool support |
| --- | --- |
| Server info/statistics/version | Health and readiness dashboards. |
| Cameras/live streams/snapshots | HLS/RTSP/HTTP URL helpers, snapshot batch, high/low quality selection. |
| HTTP PTZ | Telemetry sessions, movement, presets, coordinates, error info where direct gRPC is not available. |
| Archives/bookmarks/archive stream | Timeline, stream control, frame-by-frame helpers, bookmark lifecycle, safe delete plans. |
| Archive search | Face, LPR, VMDA, familiar/stranger, heatmap, calendar searches. |
| Events and alarms | Detector events, external virtual trigger events, audit events, alarm lists. |
| Export | Start/status/download/complete export through HTTP when gRPC is unavailable. |
| Macros | List and execute macros. |
| WebSocket events | Bounded camera/config/event subscriptions for web integrations. |
| Client HTTP API | Layout/videowall switching, current layout cameras, add/remove cameras, display selection, archive/search/immersion modes. |
| Embeddable video component | Web-server video component commands and examples for partner frontends. |
| HTTP `/grpc` bridge | Fallback transport for gRPC methods without requiring local proto compilation at runtime. |

## Missing Or Partial Priority Backlog

1. **Phase C destructive/infra tools:** `BackupSourceService`, `CloudService`, license distribute/drop/document creation, `DomainManager.AddNode/DropNode/ProclaimDomain`, `ConfigurationManager.SetRevision/RestoreBackup`, email/SMS send, installer package download, archive clear/format/reindex/delete. These require explicit throwaway targets, irreversible labels, confirmation tokens, and sanitized evidence.
2. **Fixture procurement:** Tag&Track component, non-production PTZ modes/tours, TFA/OTP and LDAP server, GlobalTracker profile fixtures, RealtimeRecognizerExternal fixture, POS/text-event source, SMTP/GSM, isolated archive volume, client-local HTTP API target, WebSocket/Web server fixture, control panels/water-level devices.
3. **Intent polish:** first-class `export`, `notification`, `tag_and_track`, `client_api`, `web_api`, and `bulk_onboarding` groups. Phase 1 added the read-only `site_graph` group; future work should consume it from planners and generators rather than rejoining inventory ad hoc.
4. **Partner depth:** add richer generated examples for dashboards, CSV camera import, archive retention policy, map/layout editing, and event-to-third-party bridges. Defer C# until compile-verifiable.

## Safety Policy Requirements

| Risk area | Required behavior |
| --- | --- |
| Secrets | Never return passwords, tokens, cookies, CA material, license keys, raw biometric vectors, or raw media bytes in tool responses/evidence. |
| Mutations | Require enable flag/env approval and a per-call confirmation token. Prefer plan/apply/verify/rollback. |
| Irreversible actions | Mark explicitly as irreversible or no-rollback before apply. Require a second acknowledgement for destructive archive/license/domain/config restore operations. |
| Streams/downloads | Enforce count, time, byte, and destination caps. Return metadata or saved artifact path, not unbounded payloads. |
| Live stand evidence | Sanitize host/user/password/token/CA. `AXXON_TLS_CN=Server` and intrinsic `hosts/Server/...` UIDs may remain. Retry transient remote stand timeouts up to three times. |
| Generated code | Use env credentials only, include safe defaults, no committed secrets, and tests/lint scaffolds. |

## AxxonSoft Proto Inventory

All AxxonSoft proto files inspected for this roadmap:

- `axxonsoft/bl/acfa/AcfaService.proto`
- `axxonsoft/bl/archive/ArchiveSupport.proto`
- `axxonsoft/bl/archive/ArchiveVolumeService.proto`
- `axxonsoft/bl/archive/BackupSource.proto`
- `axxonsoft/bl/audit/Audit.proto`
- `axxonsoft/bl/auth/Authentication.proto`
- `axxonsoft/bl/bookmarks/Bookmark.proto`
- `axxonsoft/bl/bookmarks/BookmarkService.proto`
- `axxonsoft/bl/cloud/Cloud.proto`
- `axxonsoft/bl/config/ConfigurationService.proto`
- `axxonsoft/bl/config/DevicesCatalog.proto`
- `axxonsoft/bl/config/DynamicParametersService.proto`
- `axxonsoft/bl/config/Errors.proto`
- `axxonsoft/bl/config/FileSystemBrowser.proto`
- `axxonsoft/bl/config/Property.proto`
- `axxonsoft/bl/config/PropertyAttribute.proto`
- `axxonsoft/bl/config/PropertyCategoryDescriptor.proto`
- `axxonsoft/bl/config/PropertyDescriptor.proto`
- `axxonsoft/bl/config/ServerSettings.proto`
- `axxonsoft/bl/config/SharedKeyValueStorage.proto`
- `axxonsoft/bl/config/Values.proto`
- `axxonsoft/bl/detectors/ExternalDetectorService.proto`
- `axxonsoft/bl/detectors/PeriodicalEventData.proto`
- `axxonsoft/bl/detectors/Tracklet.proto`
- `axxonsoft/bl/discovery/Discovery.proto`
- `axxonsoft/bl/domain/Domain.proto`
- `axxonsoft/bl/domain/DomainManager.proto`
- `axxonsoft/bl/domain/OverlayText.proto`
- `axxonsoft/bl/domain/TextEventSourceSupport.proto`
- `axxonsoft/bl/errors/DetectorError.proto`
- `axxonsoft/bl/events/EventHistory.proto`
- `axxonsoft/bl/events/Events.proto`
- `axxonsoft/bl/events/Notification.proto`
- `axxonsoft/bl/globalTracker/GlobalTracker.proto`
- `axxonsoft/bl/groups/GroupManager.proto`
- `axxonsoft/bl/heatmap/HeatMap.proto`
- `axxonsoft/bl/layout/LayoutImagesManager.proto`
- `axxonsoft/bl/layout/LayoutManager.proto`
- `axxonsoft/bl/license/LicenseService.proto`
- `axxonsoft/bl/license/Status.proto`
- `axxonsoft/bl/logic/CounterConfigEvent.proto`
- `axxonsoft/bl/logic/EventDescription.proto`
- `axxonsoft/bl/logic/LogicService.proto`
- `axxonsoft/bl/logic/Macro.proto`
- `axxonsoft/bl/logic/MacroConfigEvent.proto`
- `axxonsoft/bl/maintenance/ConfigurationManager.proto`
- `axxonsoft/bl/maps/MapProvider.proto`
- `axxonsoft/bl/maps/MapService.proto`
- `axxonsoft/bl/media/Media.proto`
- `axxonsoft/bl/media/MediaService.proto`
- `axxonsoft/bl/media/TextRenderingInfo.proto`
- `axxonsoft/bl/metadata/MetadataService.proto`
- `axxonsoft/bl/mmexport/Export.proto`
- `axxonsoft/bl/mmexport/ExportEvent.proto`
- `axxonsoft/bl/mmexport/ExportService.proto`
- `axxonsoft/bl/node/Node.Ancillary.proto`
- `axxonsoft/bl/notifications/EMailNotifier.proto`
- `axxonsoft/bl/notifications/GSMNotifier.proto`
- `axxonsoft/bl/package/InstallationPackageProvider.proto`
- `axxonsoft/bl/primitive/Color.proto`
- `axxonsoft/bl/primitive/Font.proto`
- `axxonsoft/bl/primitive/KeyWords.proto`
- `axxonsoft/bl/primitive/OSDSettings.proto`
- `axxonsoft/bl/primitive/Primitives.proto`
- `axxonsoft/bl/primitive/StructFieldMask.proto`
- `axxonsoft/bl/ptz/TagAndTrack.proto`
- `axxonsoft/bl/ptz/Telemetry.proto`
- `axxonsoft/bl/ptz/TelemetryHelper.proto`
- `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto`
- `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizerExternal.proto`
- `axxonsoft/bl/security/EventPermissions.proto`
- `axxonsoft/bl/security/GlobalPermissions.proto`
- `axxonsoft/bl/security/GlobalRestrictions.proto`
- `axxonsoft/bl/security/GroupsPermissions.proto`
- `axxonsoft/bl/security/GroupsPermissionsInfo.proto`
- `axxonsoft/bl/security/ObjectPermissionsInfo.proto`
- `axxonsoft/bl/security/ObjectsPermissions.proto`
- `axxonsoft/bl/security/Restrictions.proto`
- `axxonsoft/bl/security/SecurityService.proto`
- `axxonsoft/bl/settings/BookmarkSettings.proto`
- `axxonsoft/bl/settings/BookmarkSettingsChanged.proto`
- `axxonsoft/bl/settings/DataStorageSettings.proto`
- `axxonsoft/bl/settings/DataStorageSettingsChanged.proto`
- `axxonsoft/bl/settings/DomainSettingsService.proto`
- `axxonsoft/bl/settings/ExportSettings.proto`
- `axxonsoft/bl/settings/ExportSettingsChanged.proto`
- `axxonsoft/bl/settings/GDPRSettings.proto`
- `axxonsoft/bl/settings/GDPRSettingsChanged.proto`
- `axxonsoft/bl/settings/generic/GenericSettings.proto`
- `axxonsoft/bl/settings/generic/Settings.proto`
- `axxonsoft/bl/settings/generic/SettingsInfo.proto`
- `axxonsoft/bl/state/StateControl.proto`
- `axxonsoft/bl/statistics/Statistics.proto`
- `axxonsoft/bl/tz/TimeZoneEvent.proto`
- `axxonsoft/bl/tz/TimeZonesManager.proto`
- `axxonsoft/bl/videowall/Videowall.proto`
- `axxonsoft/bl/vmda/Query.proto`
- `axxonsoft/bl/vmda/VMDA.proto`
