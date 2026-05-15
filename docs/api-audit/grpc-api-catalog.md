# Axxon One API Audit Catalog

Generated from local proto files.

## Totals

- Services: 51
- RPC methods: 361
- HTTP annotations: 221
- Live-tested RPC methods recorded: 176

## Safety Buckets

- `mutating`: 147
- `read`: 157
- `review`: 54
- `stream_read`: 3

## Service Matrix

| Package | Service | RPCs | HTTP | Read | Mutating | Review | Tested | Proto |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `axxonsoft.bl.acfa` | `AcfaService` | 7 | 0 | 6 | 1 | 0 | 5 | `axxonsoft/bl/acfa/AcfaService.proto` |
| `axxonsoft.bl.archive` | `ArchiveService` | 17 | 17 | 9 | 8 | 0 | 12 | `axxonsoft/bl/archive/ArchiveSupport.proto` |
| `axxonsoft.bl.archive` | `ArchiveVolumeService` | 1 | 1 | 0 | 0 | 1 | 0 | `axxonsoft/bl/archive/ArchiveVolumeService.proto` |
| `axxonsoft.bl.archive` | `BackupSourceService` | 5 | 0 | 2 | 1 | 2 | 2 | `axxonsoft/bl/archive/BackupSource.proto` |
| `axxonsoft.bl.audit` | `AuditEventInjector` | 7 | 7 | 0 | 7 | 0 | 0 | `axxonsoft/bl/audit/Audit.proto` |
| `axxonsoft.bl.auth` | `AuthenticationService` | 12 | 9 | 1 | 7 | 4 | 2 | `axxonsoft/bl/auth/Authentication.proto` |
| `axxonsoft.bl.bookmarks` | `BookmarkService` | 7 | 7 | 0 | 5 | 2 | 0 | `axxonsoft/bl/bookmarks/BookmarkService.proto` |
| `axxonsoft.bl.cloud` | `CloudService` | 4 | 4 | 1 | 3 | 0 | 1 | `axxonsoft/bl/cloud/Cloud.proto` |
| `axxonsoft.bl.config` | `ConfigurationService` | 12 | 9 | 5 | 4 | 3 | 8 | `axxonsoft/bl/config/ConfigurationService.proto` |
| `axxonsoft.bl.config` | `DevicesCatalog` | 5 | 3 | 5 | 0 | 0 | 5 | `axxonsoft/bl/config/DevicesCatalog.proto` |
| `axxonsoft.bl.config` | `DynamicParametersService` | 2 | 2 | 2 | 0 | 0 | 0 | `axxonsoft/bl/config/DynamicParametersService.proto` |
| `axxonsoft.bl.config` | `FileSystemBrowser` | 3 | 3 | 3 | 0 | 0 | 3 | `axxonsoft/bl/config/FileSystemBrowser.proto` |
| `axxonsoft.bl.config` | `ServerSettings` | 3 | 0 | 1 | 2 | 0 | 1 | `axxonsoft/bl/config/ServerSettings.proto` |
| `axxonsoft.bl.config` | `SharedKVStorageService` | 4 | 0 | 3 | 0 | 1 | 4 | `axxonsoft/bl/config/SharedKeyValueStorage.proto` |
| `axxonsoft.bl.detectors` | `ExternalDetectorService` | 2 | 2 | 0 | 2 | 0 | 0 | `axxonsoft/bl/detectors/ExternalDetectorService.proto` |
| `axxonsoft.bl.discovery` | `DiscoveryService` | 5 | 0 | 3 | 0 | 2 | 3 | `axxonsoft/bl/discovery/Discovery.proto` |
| `axxonsoft.bl.domain` | `DomainManager` | 4 | 4 | 1 | 3 | 0 | 1 | `axxonsoft/bl/domain/DomainManager.proto` |
| `axxonsoft.bl.domain` | `DomainService` | 21 | 7 | 17 | 0 | 4 | 18 | `axxonsoft/bl/domain/Domain.proto` |
| `axxonsoft.bl.domain` | `TextEventSupportService` | 1 | 1 | 1 | 0 | 0 | 1 | `axxonsoft/bl/domain/TextEventSourceSupport.proto` |
| `axxonsoft.bl.events` | `DomainNotifier` | 5 | 4 | 0 | 4 | 1 | 0 | `axxonsoft/bl/events/Notification.proto` |
| `axxonsoft.bl.events` | `EventHistoryService` | 13 | 0 | 13 | 0 | 0 | 13 | `axxonsoft/bl/events/EventHistory.proto` |
| `axxonsoft.bl.events` | `NodeNotifier` | 6 | 4 | 0 | 4 | 2 | 0 | `axxonsoft/bl/events/Notification.proto` |
| `axxonsoft.bl.globaltracker` | `GlobalTrackerService` | 7 | 0 | 3 | 4 | 0 | 3 | `axxonsoft/bl/globalTracker/GlobalTracker.proto` |
| `axxonsoft.bl.groups` | `GroupManager` | 4 | 4 | 2 | 2 | 0 | 2 | `axxonsoft/bl/groups/GroupManager.proto` |
| `axxonsoft.bl.heatmap` | `HeatMapService` | 6 | 4 | 0 | 4 | 2 | 0 | `axxonsoft/bl/heatmap/HeatMap.proto` |
| `axxonsoft.bl.layout` | `LayoutImagesManager` | 4 | 0 | 2 | 1 | 1 | 1 | `axxonsoft/bl/layout/LayoutImagesManager.proto` |
| `axxonsoft.bl.layout` | `LayoutManager` | 5 | 3 | 1 | 1 | 3 | 1 | `axxonsoft/bl/layout/LayoutManager.proto` |
| `axxonsoft.bl.license` | `LicenseService` | 11 | 9 | 3 | 3 | 5 | 6 | `axxonsoft/bl/license/LicenseService.proto` |
| `axxonsoft.bl.logic` | `EventDescription` | 1 | 0 | 1 | 0 | 0 | 1 | `axxonsoft/bl/logic/EventDescription.proto` |
| `axxonsoft.bl.logic` | `LogicService` | 29 | 28 | 9 | 18 | 2 | 10 | `axxonsoft/bl/logic/LogicService.proto` |
| `axxonsoft.bl.maintenance` | `ConfigurationManager` | 4 | 0 | 2 | 2 | 0 | 1 | `axxonsoft/bl/maintenance/ConfigurationManager.proto` |
| `axxonsoft.bl.maps` | `MapService` | 11 | 10 | 6 | 3 | 2 | 9 | `axxonsoft/bl/maps/MapService.proto` |
| `axxonsoft.bl.media` | `MediaService` | 6 | 0 | 2 | 0 | 4 | 0 | `axxonsoft/bl/media/MediaService.proto` |
| `axxonsoft.bl.metadata` | `MetadataService` | 1 | 0 | 1 | 0 | 0 | 1 | `axxonsoft/bl/metadata/MetadataService.proto` |
| `axxonsoft.bl.mmexport` | `ExportService` | 6 | 0 | 3 | 2 | 1 | 6 | `axxonsoft/bl/mmexport/ExportService.proto` |
| `axxonsoft.bl.node.internal` | `NgpNodeService` | 1 | 0 | 1 | 0 | 0 | 1 | `axxonsoft/bl/node/Node.Ancillary.proto` |
| `axxonsoft.bl.notifications` | `EMailNotifier` | 3 | 3 | 2 | 1 | 0 | 2 | `axxonsoft/bl/notifications/EMailNotifier.proto` |
| `axxonsoft.bl.notifications` | `GSMNotifier` | 2 | 2 | 0 | 1 | 1 | 0 | `axxonsoft/bl/notifications/GSMNotifier.proto` |
| `axxonsoft.bl.package` | `InstallationPackageProvider` | 2 | 0 | 2 | 0 | 0 | 1 | `axxonsoft/bl/package/InstallationPackageProvider.proto` |
| `axxonsoft.bl.ptz` | `TagAndTrackService` | 4 | 4 | 1 | 3 | 0 | 1 | `axxonsoft/bl/ptz/TagAndTrack.proto` |
| `axxonsoft.bl.ptz` | `TelemetryService` | 32 | 32 | 7 | 24 | 1 | 6 | `axxonsoft/bl/ptz/Telemetry.proto` |
| `axxonsoft.bl.realtimerecognizer` | `RealtimeRecognizerExternalService` | 1 | 0 | 1 | 0 | 0 | 1 | `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizerExternal.proto` |
| `axxonsoft.bl.realtimerecognizer` | `RealtimeRecognizerService` | 7 | 0 | 3 | 4 | 0 | 3 | `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto` |
| `axxonsoft.bl.security` | `SecurityService` | 35 | 31 | 19 | 10 | 6 | 24 | `axxonsoft/bl/security/SecurityService.proto` |
| `axxonsoft.bl.settings` | `DomainSettingsService` | 8 | 0 | 4 | 4 | 0 | 5 | `axxonsoft/bl/settings/DomainSettingsService.proto` |
| `axxonsoft.bl.settings.generic` | `GenericSettingsService` | 3 | 0 | 1 | 1 | 1 | 1 | `axxonsoft/bl/settings/generic/GenericSettings.proto` |
| `axxonsoft.bl.state` | `StateControlService` | 3 | 0 | 2 | 1 | 0 | 2 | `axxonsoft/bl/state/StateControl.proto` |
| `axxonsoft.bl.statistics` | `StatisticService` | 1 | 0 | 1 | 0 | 0 | 1 | `axxonsoft/bl/statistics/Statistics.proto` |
| `axxonsoft.bl.tz` | `TimeZoneManager` | 7 | 7 | 4 | 3 | 0 | 4 | `axxonsoft/bl/tz/TimeZonesManager.proto` |
| `axxonsoft.bl.videowall` | `VideowallService` | 7 | 0 | 3 | 4 | 0 | 3 | `axxonsoft/bl/videowall/Videowall.proto` |
| `axxonsoft.bl.vmda` | `VMDAService` | 4 | 0 | 1 | 0 | 3 | 1 | `axxonsoft/bl/vmda/VMDA.proto` |

## RPC Matrix

### `axxonsoft.bl.acfa.AcfaService`

Proto: `axxonsoft/bl/acfa/AcfaService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListUnitsActions` | `ListUnitsActionsRequest` | `ListUnitsActionsResponse` | `server` | `read` |  | `tested-pass` |
| `ListUnitsVisualizations` | `ListUnitsVisualizationsRequest` | `ListUnitsVisualizationsResponse` | `server` | `read` |  | `tested-pass` |
| `ListUnitsEvents` | `ListUnitsEventsRequest` | `ListUnitsEventsResponse` | `server` | `read` |  | `tested-pass` |
| `ListUnitsStates` | `ListUnitsStatesRequest` | `ListUnitsStatesResponse` | `server` | `read` |  | `tested-pass` |
| `ListUnitTypes` | `ListUnitTypesRequest` | `ListUnitTypesResponse` | `none` | `read` |  | `tested-pass` |
| `PerformAction` | `PerformActionRequest` | `PerformActionResponse` | `none` | `mutating` |  | `pending` |
| `DownloadData` | `DownloadDataRequest` | `DownloadDataResponse` | `server` | `read` |  | `pending` |

### `axxonsoft.bl.archive.ArchiveService`

Proto: `axxonsoft/bl/archive/ArchiveSupport.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetArchiveTraits` | `GetArchiveTraitsRequest` | `GetArchiveTraitsResponse` | `none` | `read` | `GET /v1/archive/traits` | `tested-pass` |
| `ChangeBookmarks` | `ChangeBookmarksRequest` | `ChangeBookmarksResponse` | `none` | `mutating` | `POST /v1/archive/action:makeUserComment` | `pending` |
| `GetRecordingInfo` | `RecInfoRequest` | `RecInfoResponse` | `none` | `read` | `GET /v1/archive/recordingInfo` | `tested-pass` |
| `CreateReaderEndpoint` | `CreateReaderEndpointRequest` | `CreateReaderEndpointResponse` | `none` | `mutating` | `POST /v1/archive/action:createEndpoint` | `pending` |
| `GetHistory` | `GetHistoryRequest` | `GetHistoryResponse` | `none` | `read` | `GET /v1/archive/history` | `tested-pass` |
| `GetHistory2` | `GetHistory2Request` | `GetHistory2Response` | `none` | `read` | `GET /v1/archive/history2` | `tested-pass` |
| `GetHistoryStream` | `GetHistory2Request` | `GetHistoryResponse` | `server` | `read` | `GET /v1/archive/historyStream` | `tested-pass` |
| `GetCalendar` | `GetCalendarRequest` | `GetCalendarResponse` | `none` | `read` | `GET /v1/archive/calendar` | `tested-pass` |
| `GetSize` | `GetSizeRequest` | `GetSizeResponse` | `none` | `read` | `GET /v1/archive/size` | `tested-pass` |
| `Seek` | `SeekRequest` | `SeekResponse` | `none` | `mutating` | `POST /v1/archive/action:seek` | `pending` |
| `Resize` | `ResizeRequest` | `ResizeResponse` | `none` | `mutating` | `POST /v1/archive/action:resize` | `pending` |
| `ClearInterval` | `ClearIntervalRequest` | `ClearIntervalResponse` | `none` | `mutating` | `POST /v1/archive/action:clearInterval` | `pending` |
| `GetVolumesState` | `GetVolumesStateRequest` | `GetVolumesStateResponse` | `none` | `read` | `GET /v1/archive/volumes/state` | `tested-pass` |
| `FormatVolumes` | `FormatVolumesRequest` | `FormatVolumesResponse` | `none` | `mutating` | `POST /v1/archive/volumes/format` | `tested-pass-safe-record` |
| `GetDiskSpace` | `GetDiskSpaceRequest` | `GetDiskSpaceResponse` | `none` | `read` | `GET /v1/archive/volumes/diskSpace` | `tested-pass` |
| `Reindex` | `ReindexRequest` | `ReindexResponse` | `none` | `mutating` | `GET /v1/archive/volumes/reindex` | `tested-pass-safe-record` |
| `CancelReindex` | `CancelReindexRequest` | `CancelReindexResponse` | `none` | `mutating` | `GET /v1/archive/volumes/cancel_reindex` | `tested-pass-safe-record` |

### `axxonsoft.bl.archive.ArchiveVolumeService`

Proto: `axxonsoft/bl/archive/ArchiveVolumeService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ProbeVolume` | `ProbeVolumeRequest` | `ProbeVolumeResponse` | `none` | `review` | `POST /v1/archive/volumes:probe` | `pending` |

### `axxonsoft.bl.archive.BackupSourceService`

Proto: `axxonsoft/bl/archive/BackupSource.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `BundleBackup` | `BundleBackupRequest` | `BundleBackupResponse` | `server` | `review` |  | `pending` |
| `MakeBackup` | `MakeBackupRequest` | `MakeBackupResponse` | `none` | `review` |  | `pending` |
| `CancelBackup` | `CancelBackupRequest` | `CancelBackupResponse` | `none` | `mutating` |  | `pending` |
| `IsBackupInProgress` | `IsBackupInProgressRequest` | `IsBackupInProgressResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |
| `GetRestProgress` | `GetRestProgressRequest` | `GetRestProgressResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.audit.AuditEventInjector`

Proto: `axxonsoft/bl/audit/Audit.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `InjectClientAppOptionEvent` | `InjectClientAppOptionEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectClientAppOptionEvent` | `pending` |
| `InjectArchiveViewingEvent` | `InjectArchiveViewingEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectArchiveViewingEvent` | `pending` |
| `InjectCameraViewingEvent` | `InjectCameraViewingEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectCameraViewingEvent` | `pending` |
| `InjectNgpJournalExportEvent` | `InjectNgpJournalExportEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectNgpJournalExportEvent` | `pending` |
| `InjectPtzControlEvent` | `InjectPtzControlEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectPtzControlEvent` | `pending` |
| `InjectMMExportEvent` | `InjectMMExportEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectMMExportEvent` | `pending` |
| `InjectLdapSetupEvent` | `InjectLdapSetupEventRequest` | `AuditClientResponse` | `none` | `mutating` | `POST /v1/audit/injectLdapSetupEvent` | `pending` |

### `axxonsoft.bl.auth.AuthenticationService`

Proto: `axxonsoft/bl/auth/Authentication.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `Authenticate` | `AuthenticateRequest` | `AuthenticateResponse` | `none` | `review` | `GET /v1/authentication/authenticate` | `pending` |
| `Authenticate2` | `AuthenticateRequest` | `AuthenticateResponse` | `none` | `mutating` | `POST /v1/authentication/authenticate2` | `pending` |
| `AuthenticateEx` | `AuthenticateRequest` | `AuthenticateResponseEx` | `none` | `review` | `GET /v1/authentication/authenticate_ex` | `pending` |
| `AuthenticateEx2` | `AuthenticateRequest` | `AuthenticateResponseEx` | `none` | `mutating` | `POST /v1/authentication/authenticate_ex2` | `tested-pass` |
| `ApproveAuthentication` | `ApproveAuthenticationRequest` | `ApproveAuthenticationResponse` | `none` | `mutating` | `POST /v1/authentication:approve` | `pending` |
| `DeclineAuthentication` | `DeclineAuthenticationRequest` | `DeclineAuthenticationResponse` | `none` | `mutating` | `POST /v1/authentication:decline` | `pending` |
| `AuthenticateBySecondFactor` | `AuthenticateBySecondFactorRequest` | `AuthenticateResponseEx` | `none` | `review` |  | `pending` |
| `AuthenticateWithPublicKey` | `AuthenticateTokenRequest` | `AuthenticateResponseEx` | `none` | `review` |  | `pending` |
| `GetSessionInfo` | `GetSessionInfoRequest` | `GetSessionInfoResponse` | `none` | `read` |  | `tested-pass` |
| `RenewSession` | `RenewSessionRequest` | `AuthenticateResponseEx` | `none` | `mutating` | `GET /v1/authentication/renew` | `pending` |
| `RenewSession2` | `RenewSessionRequest` | `AuthenticateResponseEx` | `none` | `mutating` | `GET /v1/authentication/renew2` | `pending` |
| `CloseSession` | `CloseSessionRequest` | `CloseSessionResponse` | `none` | `mutating` | `GET /v1/authentication/close` | `pending` |

### `axxonsoft.bl.bookmarks.BookmarkService`

Proto: `axxonsoft/bl/bookmarks/BookmarkService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListBookmarks` | `ListBookmarksRequest` | `ListBookmarksResponse` | `none` | `review` | `POST /v1/bookmarks:list` | `pending` |
| `GetBookmark` | `GetBookmarkRequest` | `GetBookmarkResponse` | `none` | `review` | `POST /v1/bookmarks:get` | `pending` |
| `CreateBookmark` | `CreateBookmarkRequest` | `CreateBookmarkResponse` | `none` | `mutating` | `POST /v1/bookmarks:create` | `pending` |
| `UpdateBookmark` | `UpdateBookmarkRequest` | `UpdateBookmarkResponse` | `none` | `mutating` | `POST /v1/bookmarks:update` | `pending` |
| `DeleteBookmark` | `DeleteBookmarkRequest` | `DeleteBookmarkResponse` | `none` | `mutating` | `POST /v1/bookmarks:delete` | `pending` |
| `SetExportedTime` | `SetExportedTimeRequest` | `SetExportedTimeResponse` | `none` | `mutating` | `POST /v1/bookmarks:setExportedTime` | `pending` |
| `RenderTrack` | `RenderTrackRequest` | `RenderTrackResponse` | `none` | `mutating` | `POST /v1/bookmarks:renderTrack` | `pending` |

### `axxonsoft.bl.cloud.CloudService`

Proto: `axxonsoft/bl/cloud/Cloud.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetBindingConfiguration` | `GetBindingConfigurationRequest` | `GetBindingConfigurationResponse` | `none` | `read` | `GET /v1/cloud/config` | `tested-warn-fixture-needed` |
| `ChangeBindingConfiguration` | `ChangeBindingConfigurationRequest` | `ChangeBindingConfigurationResponse` | `none` | `mutating` | `POST /v1/cloud/config:change` | `pending` |
| `Bind` | `BindRequest` | `BindResponse` | `none` | `mutating` | `GET /v1/cloud/bind` | `pending` |
| `Unbind` | `UnbindRequest` | `UnbindResponse` | `none` | `mutating` | `GET /v1/cloud/unbind` | `pending` |

### `axxonsoft.bl.config.ConfigurationService`

Proto: `axxonsoft/bl/config/ConfigurationService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListUnits` | `ListUnitsRequest` | `ListUnitsResponse` | `none` | `read` | `GET /v1/configurator/list` | `tested-pass` |
| `ListUnitsStream` | `ListUnitsStreamRequest` | `ListUnitsResponse` | `server` | `read` |  | `tested-pass` |
| `ListUnitsByAccessPoints` | `ListUnitsByAccessPointsRequest` | `ListUnitsResponse` | `none` | `read` | `GET /v1/configurator/get` | `tested-pass` |
| `ListUnitsByAccessPointsStream` | `ListUnitsByAccessPointsStreamRequest` | `ListUnitsResponse` | `server` | `read` |  | `tested-pass` |
| `ChangeConfig` | `ChangeConfigRequest` | `ChangeConfigResponse` | `none` | `mutating` | `POST /v1/configurator:change` | `pending` |
| `ChangeConfigStream` | `ChangeConfigRequest` | `ChangeConfigResponse` | `server` | `mutating` |  | `pending` |
| `ListTemplates` | `ListTemplatesRequest` | `ListTemplatesResponse` | `none` | `read` | `GET /v1/configurator/templates` | `tested-pass` |
| `ChangeTemplates` | `ChangeTemplatesRequest` | `ChangeTemplatesResponse` | `none` | `mutating` | `POST /v1/configurator/templates:change` | `tested-pass-safe-record` |
| `SetTemplateAssignments` | `SetTemplateAssignmentsRequest` | `SetTemplateAssignmentsResponse` | `none` | `mutating` | `POST /v1/configurator/assignments` | `tested-pass-safe-record` |
| `BatchGetTemplates` | `BatchGetTemplatesRequest` | `BatchGetTemplatesResponse` | `none` | `review` | `POST /v1/configurator/templates:batchGet` | `tested-pass-safe-record` |
| `BatchGetFactories` | `BatchGetFactoriesRequest` | `BatchGetFactoriesResponse` | `none` | `review` | `POST /v1/configurator/factories:batchGet` | `pending` |
| `ListSimilarUnits` | `ListSimilarUnitsRequest` | `ListSimilarUnitsResponse` | `none` | `review` | `POST /v1/configurator/units:listSimilar` | `pending` |

### `axxonsoft.bl.config.DevicesCatalog`

Proto: `axxonsoft/bl/config/DevicesCatalog.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListVendors` | `ListVendorsRequest` | `ListVendorsResponse` | `none` | `read` | `GET /v1/configurator/devices_catalog/vendors` | `tested-pass` |
| `ListVendorsV2` | `ListVendorsRequest` | `ListVendorsResponse` | `server` | `read` |  | `tested-pass` |
| `ListDevices` | `ListDevicesRequest` | `ListDevicesResponse` | `none` | `read` | `GET /v1/configurator/devices_catalog/devices` | `tested-pass` |
| `ListDevicesV2` | `ListDevicesRequest` | `ListDevicesResponse` | `server` | `read` |  | `tested-pass` |
| `GetDevice` | `GetDeviceRequest` | `GetDeviceResponse` | `none` | `read` | `GET /v1/configurator/devices_catalog/device` | `tested-pass` |

### `axxonsoft.bl.config.DynamicParametersService`

Proto: `axxonsoft/bl/config/DynamicParametersService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `AcquireDynamicParameters` | `AcquireDynamicParametersRequest` | `AcquireDynamicParametersResponse` | `none` | `read` | `GET /v1/configurator/dynamic-parameters:acquire` | `pending` |
| `AcquireDeviceAdditionalData` | `AcquireDeviceAdditionalDataRequest` | `AcquireDeviceAdditionalDataResponse` | `none` | `read` | `GET /v1/configurator/device-additional-data:acquire` | `pending` |

### `axxonsoft.bl.config.FileSystemBrowser`

Proto: `axxonsoft/bl/config/FileSystemBrowser.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListDirectory` | `ListDirectoryRequest` | `ListDirectoryResponse` | `none` | `read` | `GET /v1/fs/list` | `tested-pass` |
| `GetFileInfo` | `GetFileInfoRequest` | `GetFileInfoResponse` | `none` | `read` | `GET /v1/fs/file` | `tested-pass` |
| `GetSpace` | `GetSpaceRequest` | `GetSpaceResponse` | `none` | `read` | `GET /v1/fs/space` | `tested-pass` |

### `axxonsoft.bl.config.ServerSettings`

Proto: `axxonsoft/bl/config/ServerSettings.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetLogLevel` | `GetLogLevelRequest` | `GetLogLevelResponse` | `none` | `read` |  | `tested-pass` |
| `SetLogLevel` | `SetLogLevelRequest` | `SetLogLevelResponse` | `none` | `mutating` |  | `pending` |
| `DropLogs` | `DropLogsRequest` | `DropLogsResponse` | `none` | `mutating` |  | `pending` |

### `axxonsoft.bl.config.SharedKVStorageService`

Proto: `axxonsoft/bl/config/SharedKeyValueStorage.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListRecords` | `ListRecordsRequest` | `ListRecordsResponse` | `none` | `read` |  | `tested-pass` |
| `BatchGetRecords` | `BatchGetRecordsRequest` | `BatchGetRecordsResponse` | `none` | `read` |  | `tested-pass` |
| `Commit` | `SharedKVCommitRequest` | `SharedKVCommitResponse` | `none` | `review` |  | `tested-pass-safe-record` |
| `GetRecordsStream` | `GetRecordsStreamRequest` | `GetRecordsStreamResponse` | `server` | `read` |  | `tested-pass` |

### `axxonsoft.bl.detectors.ExternalDetectorService`

Proto: `axxonsoft/bl/detectors/ExternalDetectorService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `RaiseOccasionalEvent` | `RaiseOccasionalEventRequest` | `RaiseOccasionalEventResponse` | `none` | `mutating` | `POST /v1/detectors/external:raiseOccasionalEvent` | `pending` |
| `RaisePeriodicalEvent` | `RaisePeriodicalEventRequest` | `RaisePeriodicalEventResponse` | `none` | `mutating` | `POST /v1/detectors/external:raisePeriodicalEvent` | `pending` |

### `axxonsoft.bl.discovery.DiscoveryService`

Proto: `axxonsoft/bl/discovery/Discovery.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `Discover` | `google.protobuf.Empty` | `google.protobuf.Empty` | `none` | `review` |  | `pending` |
| `DiscoverNode` | `DiscoveryRequest` | `google.protobuf.Empty` | `none` | `review` |  | `pending` |
| `GetDiscoveryProgress` | `google.protobuf.Empty` | `GetDiscoveryProgressResponse` | `server` | `read` |  | `tested-pass` |
| `GetNodeDiscoveryProgress` | `DiscoveryRequest` | `GetDiscoveryProgressResponse` | `server` | `read` |  | `tested-pass` |
| `Probe` | `ProbeRequest` | `ProbeResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.domain.DomainManager`

Proto: `axxonsoft/bl/domain/DomainManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `EnumerateNodes` | `EnumerateNodesRequest` | `EnumerateNodesResponse` | `none` | `read` | `GET /v1/domain/nodes:enumerate` | `tested-pass` |
| `AddNode` | `AddNodeRequest` | `AddNodeResponse` | `none` | `mutating` | `POST /v1/domain/nodes:add` | `pending` |
| `DropNode` | `DropNodeRequest` | `DropNodeResponse` | `none` | `mutating` | `POST /v1/domain/nodes:drop` | `pending` |
| `ProclaimDomain` | `ProclaimDomainRequest` | `ProclaimDomainResponse` | `none` | `mutating` | `POST /v1/domain:proclaim` | `pending` |

### `axxonsoft.bl.domain.DomainService`

Proto: `axxonsoft/bl/domain/Domain.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetVersion` | `GetVersionRequest` | `GetVersionResponse` | `none` | `read` |  | `tested-pass` |
| `GetHostPlatformInfo` | `GetHostPlatformInfoRequest` | `GetHostPlatformInfoResponse` | `none` | `read` |  | `tested-pass` |
| `GetHostTimeZone` | `GetHostTimeZoneRequest` | `GetHostTimeZoneResponse` | `none` | `read` |  | `tested-pass` |
| `ListCameras` | `ListCamerasRequest` | `ListCamerasResponse` | `server` | `read` | `GET /v1/domain/cameras` | `tested-pass` |
| `BatchGetCameras` | `BatchGetCamerasRequest` | `BatchGetCamerasResponse` | `server` | `review` | `POST /v1/domain/cameras:batchGet` | `tested-pass` |
| `GetCamerasByComponents` | `GetCamerasByComponentsRequest` | `GetCamerasByComponentsResponse` | `server` | `review` | `POST /v1/domain/cameras:getByComponents` | `pending` |
| `ListArchives` | `ListArchivesRequest` | `ListArchivesResponse` | `server` | `read` | `GET /v1/domain/archives` | `tested-pass` |
| `BatchGetArchives` | `BatchGetArchivesRequest` | `BatchGetArchivesResponse` | `server` | `review` | `POST /v1/domain/archives:batchGet` | `pending` |
| `ListControlPanels` | `ListControlPanelsRequest` | `ListControlPanelsResponse` | `server` | `read` |  | `tested-pass` |
| `BatchGetControlPanels` | `BatchGetControlPanelsRequest` | `BatchGetControlPanelsResponse` | `server` | `read` |  | `tested-pass` |
| `ListCommonDevices` | `ListCommonDevicesRequest` | `ListCommonDevicesResponse` | `server` | `read` |  | `tested-pass` |
| `BatchGetCommonDevices` | `BatchGetCommonDevicesRequest` | `BatchGetCommonDevicesResponse` | `server` | `read` |  | `tested-pass` |
| `ListComponents` | `ListComponentsRequest` | `ListComponentsResponse` | `server` | `read` |  | `tested-pass` |
| `ListGlobalTrackers` | `ListGlobalTrackersRequest` | `ListGlobalTrackersResponse` | `server` | `read` |  | `tested-pass` |
| `ListGlobalTrackerCameras` | `ListGlobalTrackerCamerasRequest` | `ListGlobalTrackerCamerasResponse` | `server` | `read` |  | `tested-pass` |
| `ListAcfaComponents` | `ListAcfaComponentsRequest` | `ListAcfaComponentsResponse` | `server` | `read` |  | `tested-pass` |
| `ListAcfaComponents2` | `ListAcfaComponentsRequest` | `ListAcfaComponentsResponse` | `server` | `read` |  | `tested-pass` |
| `ListPluginComponents` | `ListPluginComponentsRequest` | `ListPluginComponentsResponse` | `server` | `read` |  | `tested-pass` |
| `BatchGetAcfaComponents` | `BatchGetAcfaComponentsRequest` | `BatchGetAcfaComponentsResponse` | `server` | `read` |  | `tested-pass` |
| `ListNodes` | `ListNodesRequest` | `ListNodesResponse` | `none` | `read` | `GET /v1/domain/nodes` | `tested-pass` |
| `SearchMaps` | `SearchMapsRequest` | `SearchMapsResponse` | `server` | `review` | `POST /v1/domain/maps:search` | `pending` |

### `axxonsoft.bl.domain.TextEventSupportService`

Proto: `axxonsoft/bl/domain/TextEventSourceSupport.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetTextEvent` | `GetTextEventRequest` | `GetTextEventResponse` | `none` | `read` | `GET /v1/domain/textEvent` | `tested-warn-fixture-needed` |

### `axxonsoft.bl.events.DomainNotifier`

Proto: `axxonsoft/bl/events/Notification.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `PullEvents` | `PullEventsRequest` | `Events` | `server` | `mutating` | `POST /v1/notifier/subscriptions` | `pending` |
| `PullDetailedEvents` | `PullEventsRequest` | `Events` | `server` | `mutating` | `POST /v1/notifier/subscriptions:pull` | `pending` |
| `UpdateSubscription` | `UpdateSubscriptionRequest` | `UpdateSubscriptionResponse` | `none` | `mutating` | `POST /v1/notifier/subscriptions:update` | `pending` |
| `DisconnectEventChannel` | `DisconnectEventChannelRequest` | `DisconnectEventChannelResponse` | `none` | `mutating` | `POST /v1/notifier/subscriptions:disconnect` | `pending` |
| `PushDiagnosticEvents` | `PushDiagnosticEventsRequest` | `PushDiagnosticEventsResponse` | `none` | `review` |  | `pending` |

### `axxonsoft.bl.events.EventHistoryService`

Proto: `axxonsoft/bl/events/EventHistory.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ReadEvents` | `ReadEventsRequest` | `ReadEventsResponse` | `server` | `read` |  | `tested-pass` |
| `ReadCount` | `ReadCountRequest` | `ReadCountResponse` | `server` | `read` |  | `tested-pass` |
| `ReadTextEvents` | `ReadTextEventsRequest` | `ReadTextEventsResponse` | `server` | `read` |  | `tested-pass` |
| `ReadTextCount` | `ReadTextCountRequest` | `ReadTextCountResponse` | `server` | `read` |  | `tested-pass` |
| `ReadAlerts` | `ReadAlertsRequest` | `ReadAlertsResponse` | `server` | `read` |  | `tested-pass` |
| `ReadLprEvents` | `ReadLprEventsRequest` | `ReadLprEventsResponse` | `server` | `read` |  | `tested-pass-empty` |
| `ReadBookmarks` | `ReadBookmarksRequest` | `ReadBookmarksResponse` | `server` | `read` |  | `tested-pass` |
| `FindByPrompt` | `FindByPromptRequest` | `FindByPromptResponse` | `server` | `read` |  | `tested-pass` |
| `FindContacts` | `FindContactsRequest` | `FindContactsResponse` | `server` | `read` |  | `tested-pass` |
| `FindSimilarObjects` | `FindSimilarObjectsRequest` | `FindSimilarObjectsResponse` | `server` | `read` |  | `tested-pass` |
| `FindSimilarObjects2` | `FindSimilarObjectsRequest` | `FindSimilarObjectsResponse` | `server` | `read` |  | `tested-pass` |
| `FindStrangers` | `FindStrangersRequest` | `FindStrangersResponse` | `server` | `read` |  | `tested-pass` |
| `FindStrangersByObjects` | `FindStrangersByObjectsRequest` | `FindStrangersByObjectsResponse` | `server` | `read` |  | `tested-pass` |

### `axxonsoft.bl.events.NodeNotifier`

Proto: `axxonsoft/bl/events/Notification.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `PullEvents` | `PullEventsRequest` | `Events` | `server` | `mutating` | `POST /v1/node-notifier/subscriptions` | `pending` |
| `PullDetailedEvents` | `PullEventsRequest` | `Events` | `server` | `mutating` | `POST /v1/node-notifier/subscriptions:pull` | `pending` |
| `UpdateSubscription` | `UpdateSubscriptionRequest` | `UpdateSubscriptionResponse` | `none` | `mutating` | `POST /v1/node-notifier/subscriptions:update` | `pending` |
| `DisconnectEventChannel` | `DisconnectEventChannelRequest` | `DisconnectEventChannelResponse` | `none` | `mutating` | `POST /v1/node-notifier/subscriptions:disconnect` | `pending` |
| `PushDiagnosticEvents` | `PushDiagnosticEventsRequest` | `PushDiagnosticEventsResponse` | `none` | `review` |  | `pending` |
| `Ping` | `PingRequest` | `PingResponse` | `server` | `review` |  | `pending` |

### `axxonsoft.bl.globaltracker.GlobalTrackerService`

Proto: `axxonsoft/bl/globalTracker/GlobalTracker.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ChangeGlobalTrackerProfiles` | `ChangeGlobalTrackerProfilesRequest` | `ChangeGlobalTrackerProfilesResponse` | `none` | `mutating` |  | `pending` |
| `ChangeProfiles` | `ChangeProfilesRequest` | `ChangeProfilesResponse` | `bidi` | `mutating` |  | `pending` |
| `GetGlobalTrackerProfiles` | `GetGlobalTrackerProfilesRequest` | `GetGlobalTrackerProfilesResponse` | `server` | `read` |  | `tested-warn-fixture-needed` |
| `GetProfile` | `GetProfileRequest` | `GetProfileResponse` | `server` | `read` |  | `tested-pass` |
| `ClearProfiles` | `ClearProfilesRequest` | `ClearProfilesResponse` | `none` | `mutating` |  | `pending` |
| `BindGlobalTrackProfile` | `BindGlobalTrackProfileRequest` | `BindGlobalTrackProfileResponse` | `none` | `mutating` |  | `pending` |
| `GetGlobalTrackBestVisibilityPositions` | `GetGlobalTrackBestVisibilityPositionsRequest` | `GetGlobalTrackBestVisibilityPositionsResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.groups.GroupManager`

Proto: `axxonsoft/bl/groups/GroupManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListGroups` | `ListGroupsRequest` | `ListGroupsResponse` | `none` | `read` | `GET /v1/groups/list` | `tested-pass` |
| `BatchGetGroups` | `BatchGetGroupsRequest` | `BatchGetGroupsResponse` | `none` | `read` | `GET /v1/groups:batchGet` | `tested-pass` |
| `ChangeGroups` | `ChangeGroupsRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/groups:change` | `pending` |
| `SetObjectsMembership` | `SetObjectsMembershipRequest` | `SetObjectsMembershipResponse` | `none` | `mutating` | `POST /v1/groups/membership` | `pending` |

### `axxonsoft.bl.heatmap.HeatMapService`

Proto: `axxonsoft/bl/heatmap/HeatMap.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `BuildHeatmap` | `BuildHeatmapRequest` | `BuildHeatmapResponse` | `none` | `mutating` | `POST /v1/heatmap:build` | `pending` |
| `BuildHeatmapTyped` | `BuildHeatmapTypedRequest` | `BuildHeatmapResponse` | `none` | `mutating` | `POST /v1/heatmap:buildTyped` | `pending` |
| `BuildEventsHeatmap` | `BuildEventsHeatmapRequest` | `BuildEventsHeatmapResponse` | `none` | `mutating` | `POST /v1/events-heatmap:build` | `pending` |
| `BuildFloorHeatmap` | `BuildFloorHeatmapRequest` | `BuildFloorHeatmapResponse` | `none` | `mutating` | `POST /v1/floor-heatmap:build` | `pending` |
| `ExecuteHeatmapQuery` | `ExecuteHeatmapQueryRequest` | `ExecuteHeatmapQueryResponse` | `server` | `review` |  | `pending` |
| `ExecuteHeatmapQueryTyped` | `ExecuteHeatmapQueryTypedRequest` | `ExecuteHeatmapQueryResponse` | `server` | `review` |  | `pending` |

### `axxonsoft.bl.layout.LayoutImagesManager`

Proto: `axxonsoft/bl/layout/LayoutImagesManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListLayoutImages` | `ListLayoutImagesRequest` | `ListLayoutImagesResponse` | `none` | `read` |  | `tested-pass` |
| `RemoveLayoutImages` | `RemoveLayoutImagesRequest` | `RemoveLayoutImagesResponse` | `none` | `mutating` |  | `pending` |
| `UploadLayoutImage` | `UploadLayoutImageRequest` | `UploadLayoutImageResponse` | `client` | `review` |  | `pending` |
| `DownloadLayoutImage` | `DownloadLayoutImageRequest` | `DownloadLayoutImageResponse` | `server` | `read` |  | `pending` |

### `axxonsoft.bl.layout.LayoutManager`

Proto: `axxonsoft/bl/layout/LayoutManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListLayouts` | `ListLayoutsRequest` | `ListLayoutsResponse` | `none` | `read` | `GET /v1/layouts` | `tested-pass` |
| `BatchGetLayouts` | `BatchGetLayoutsRequest` | `BatchGetLayoutsResponse` | `none` | `review` | `POST /v1/layouts:batchGet` | `pending` |
| `Update` | `UpdateRequest` | `UpdateResponse` | `none` | `mutating` | `POST /v1/layouts:update` | `pending` |
| `LayoutsOnView` | `LayoutsOnViewRequest` | `LayoutsOnViewResponse` | `none` | `review` |  | `pending` |
| `UserDataCleanup` | `UserDataCleanupRequest` | `UserDataCleanupResponse` | `none` | `review` |  | `pending` |

### `axxonsoft.bl.license.LicenseService`

Proto: `axxonsoft/bl/license/LicenseService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `LicenseKey` | `LicenseKeyRequest` | `LicenseKeyResponse` | `none` | `review` | `GET /v1/license` | `pending` |
| `Restrictions` | `RestrictionsRequest` | `RestrictionsResponse` | `none` | `review` | `GET /v1/license/restrictions` | `pending` |
| `GetGlobalRestrictions` | `GetGlobalRestrictionsRequest` | `GetGlobalRestrictionsResponse` | `none` | `read` | `GET /v1/license/globalRestrictions` | `tested-pass` |
| `GetNodeRestrictions` | `GetNodeRestrictionsRequest` | `GetNodeRestrictionsResponse` | `server` | `review` | `POST /v1/license/nodeRestrictions` | `tested-pass` |
| `DistributeLicenseKey` | `DistributeLicenseKeyRequest` | `DistributeLicenseKeyResponse` | `none` | `mutating` | `POST /v1/license:distribute` | `pending` |
| `DropLicenseKey` | `DropLicenseKeyRequest` | `DropLicenseKeyResponse` | `none` | `mutating` | `POST /v1/license:drop` | `pending` |
| `IsPossibleToLaunch` | `IsPossibleToLaunchRequest` | `IsPossibleToLaunchResponse` | `none` | `review` | `POST /v1/license:verifyLaunchPossibility` | `tested-pass` |
| `LicenseKeyInfo` | `LicenseKeyInfoRequest` | `LicenseKeyInfoResponse` | `none` | `review` | `GET /v1/license:info` | `tested-pass` |
| `GetDomainLicenseKeyInfo` | `GetDomainLicenseKeyInfoRequest` | `GetDomainLicenseKeyInfoResponse` | `none` | `read` | `GET /v1/license/domain` | `tested-pass` |
| `CreateLicenseDocument` | `CreateLicenseDocumentRequest` | `CreateLicenseDocumentResponse` | `server` | `mutating` |  | `pending` |
| `GetHostInfo` | `GetHostInfoRequest` | `GetHostInfoResponse` | `none` | `read` |  | `tested-pass` |

### `axxonsoft.bl.logic.EventDescription`

Proto: `axxonsoft/bl/logic/EventDescription.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetEventGroupingTags` | `GetEventGroupingTagsRequest` | `GetEventGroupingTagsResponse` | `none` | `read` |  | `tested-pass` |

### `axxonsoft.bl.logic.LogicService`

Proto: `axxonsoft/bl/logic/LogicService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListMacros` | `ListMacrosRequest` | `ListMacrosResponse` | `none` | `read` | `GET /v1/logic_service/macros` | `tested-pass` |
| `ListMacrosV2` | `ListMacrosRequest` | `ListMacrosResponse` | `server` | `read` |  | `tested-pass` |
| `BatchGetMacros` | `BatchGetMacrosRequest` | `BatchGetMacrosResponse` | `none` | `read` | `GET /v1/logic_service/macros:batchGet` | `tested-pass` |
| `ChangeMacros` | `ChangeMacrosRequest` | `ChangeMacrosResponse` | `none` | `mutating` | `POST /v1/logic_service/macros:change` | `tested-pass-safe-record` |
| `LaunchMacro` | `LaunchMacroRequest` | `LaunchMacroResponse` | `none` | `mutating` | `POST /v1/logic_service/macros:launch` | `pending` |
| `ChangeArmState` | `ChangeArmStateRequest` | `ChangeArmStateResponse` | `none` | `mutating` | `POST /v1/logic_service/armstate` | `pending` |
| `GetActiveAlerts` | `GetActiveAlertsRequest` | `GetActiveAlertsResponse` | `none` | `review` | `POST /v1/logic_service/getactivealerts` | `pending` |
| `BatchGetActiveAlerts` | `BatchGetActiveAlertsRequest` | `BatchGetActiveAlertsResponse` | `server` | `review` | `POST /v1/logic_service/batchgetactivealerts` | `pending` |
| `BatchFilterActiveAlerts` | `BatchFilterActiveAlertsRequest` | `BatchFilterActiveAlertsResponse` | `server` | `mutating` | `POST /v1/logic_service/batchfilteractivealerts` | `pending` |
| `BatchBeginAlertsReview` | `BatchBeginAlertsReviewRequest` | `BatchBeginAlertsReviewResponse` | `server` | `mutating` | `POST /v1/logic_service/batchbeginalertsreview` | `pending` |
| `BatchContinueAlertsRewiew` | `BatchContinueAlertsRewiewRequest` | `BatchContinueAlertsRewiewResponse` | `server` | `mutating` | `POST /v1/logic_service/batchcontinuealertsreview` | `pending` |
| `BatchCancelAlertsReview` | `BatchCancelAlertsReviewRequest` | `BatchCancelAlertsReviewResponse` | `server` | `mutating` | `POST /v1/logic_service/batchcancelalertsreview` | `pending` |
| `BatchCompleteAlertsReview` | `BatchCompleteAlertsReviewRequest` | `BatchCompleteAlertsReviewResponse` | `server` | `mutating` | `POST /v1/logic_service/batchcompletealertsreview` | `pending` |
| `BatchEscalateAlerts` | `BatchEscalateAlertsRequest` | `BatchEscalateAlertsResponse` | `server` | `mutating` | `POST /v1/logic_service/batchescalatealerts` | `pending` |
| `RaiseAlert` | `RaiseAlertRequest` | `RaiseAlertResponse` | `none` | `mutating` | `POST /v1/logic_service/raisealert` | `pending` |
| `BeginAlertReview` | `BeginAlertReviewRequest` | `BeginAlertReviewResponse` | `none` | `mutating` | `POST /v1/logic_service/beginalert` | `pending` |
| `CancelAlertReview` | `CancelAlertReviewRequest` | `CancelAlertReviewResponse` | `none` | `mutating` | `POST /v1/logic_service/cancelalert` | `pending` |
| `ContinueAlertReview` | `ContinueAlertReviewRequest` | `ContinueAlertReviewResponse` | `none` | `mutating` | `POST /v1/logic_service/continuealert` | `pending` |
| `CompleteAlertReview` | `CompleteAlertReviewRequest` | `CompleteAlertReviewResponse` | `none` | `mutating` | `POST /v1/logic_service/completealert` | `pending` |
| `EscalateAlert` | `EscalateAlertRequest` | `EscalateAlertResponse` | `none` | `mutating` | `POST /v1/logic_service/escalatealert` | `pending` |
| `ChangeConfig` | `ChangeConfigRequest` | `ChangeConfigResponse` | `none` | `mutating` | `PUT /v1/logic_service/config` | `pending` |
| `GetConfig` | `GetConfigRequest` | `GetConfigResponse` | `none` | `read` | `GET /v1/logic_service/config` | `tested-pass` |
| `ListCounters` | `ListCountersRequest` | `ListCountersResponse` | `none` | `read` | `GET /v1/logic_service/counters` | `tested-pass` |
| `BatchGetCounters` | `BatchGetCountersRequest` | `ListCountersResponse` | `none` | `read` | `GET /v1/logic_service/counters:batchGet` | `tested-pass` |
| `ChangeCounters` | `ChangeCountersRequest` | `ChangeCountersResponse` | `none` | `mutating` | `POST /v1/logic_service/counters:change` | `pending` |
| `CounterAction` | `CounterActionRequest` | `CounterActionResponse` | `none` | `mutating` | `POST /v1/logic_service/counters:action` | `pending` |
| `GetCounterState` | `GetCounterStateRequest` | `GetCounterStateResponse` | `none` | `read` | `GET /v1/logic_service/counters:getState` | `tested-warn-fixture-needed` |
| `GetCounterGroupState` | `GetCounterGroupStateRequest` | `GetCounterGroupStateResponse` | `none` | `read` | `GET /v1/logic_service/counters:getGroupState` | `tested-warn-fixture-needed` |
| `GetUserScripts` | `GetUserScriptsRequest` | `GetUserScriptsResponse` | `none` | `read` | `GET /v1/logic_service/user_scripts` | `tested-pass` |

### `axxonsoft.bl.maintenance.ConfigurationManager`

Proto: `axxonsoft/bl/maintenance/ConfigurationManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetRevisionInfo` | `GetRevisionInfoRequest` | `GetRevisionInfoResponse` | `none` | `read` |  | `tested-pass` |
| `SetRevision` | `SetRevisionRequest` | `SetRevisionResponse` | `none` | `mutating` |  | `pending` |
| `CollectBackup` | `CollectBackupRequest` | `CollectBackupResponse` | `server` | `read` |  | `pending` |
| `RestoreBackup` | `RestoreBackupRequest` | `RestoreBackupResponse` | `client` | `mutating` |  | `pending` |

### `axxonsoft.bl.maps.MapService`

Proto: `axxonsoft/bl/maps/MapService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListMaps` | `ListMapsRequest` | `ListMapsResponse` | `none` | `read` | `GET /v1/maps/list` | `tested-pass` |
| `BatchGetMaps` | `BatchGetMapsRequest` | `BatchGetMapsResponse` | `none` | `read` | `GET /v1/maps:batchGet` | `tested-pass` |
| `ChangeMaps` | `ChangeMapsRequest` | `ChangeMapsResponse` | `none` | `mutating` | `POST /v1/maps:change` | `tested-pass-safe-record` |
| `GetMapImage` | `GetMapImageRequest` | `GetMapImageResponse` | `none` | `read` | `GET /v1/maps/image` | `tested-pass-safe-record` |
| `GetMarkers` | `GetMarkersRequest` | `GetMarkersResponse` | `none` | `review` | `POST /v1/maps/markers` | `tested-pass-safe-record` |
| `UpdateMarkers` | `UpdateMarkersRequest` | `UpdateMarkersResponse` | `none` | `mutating` | `POST /v1/maps/markers:update` | `tested-pass-safe-record` |
| `GetMapsByComponent` | `GetMapsByComponentRequest` | `GetMapsByComponentResponse` | `none` | `read` | `GET /v1/maps:getByComponent` | `tested-pass` |
| `ConfigureMapProviders` | `ConfigureMapProvidersRequest` | `ConfigureMapProvidersResponse` | `none` | `mutating` | `POST /v1/maps/providers` | `pending` |
| `ListMapProviders` | `ListMapProvidersRequest` | `ListMapProvidersResponse` | `none` | `read` | `GET /v1/maps/providers` | `tested-pass` |
| `GetMapProvider` | `GetMapProviderRequest` | `GetMapProviderResponse` | `none` | `read` | `GET /v1/maps/provider` | `tested-warn-fixture-needed` |
| `UserDataCleanup` | `UserDataCleanupRequest` | `UserDataCleanupResponse` | `none` | `review` |  | `pending` |

### `axxonsoft.bl.media.MediaService`

Proto: `axxonsoft/bl/media/MediaService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `Stream` | `MediaRequest` | `MediaSample` | `bidi` | `stream_read` |  | `pending` |
| `RequestConnection` | `RequestConnectionRequest` | `RequestConnectionResponse` | `none` | `review` |  | `pending` |
| `RequestQoS` | `RequestQoSRequest` | `RequestQoSResponse` | `none` | `review` |  | `pending` |
| `AwaitConnection` | `AwaitConnectionRequest` | `AwaitConnectionResponse` | `bidi` | `stream_read` |  | `pending` |
| `ConnectEndpoint` | `ConnectEndpointRequest` | `ConnectEndpointResponse` | `bidi` | `review` |  | `pending` |
| `RequestTunnel` | `TunnelRequest` | `TunnelResponse` | `none` | `review` |  | `pending` |

### `axxonsoft.bl.metadata.MetadataService`

Proto: `axxonsoft/bl/metadata/MetadataService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `PullMetadata` | `PullMetadataRequest` | `PullMetadataResponse` | `bidi` | `stream_read` |  | `tested-pass` |

### `axxonsoft.bl.mmexport.ExportService`

Proto: `axxonsoft/bl/mmexport/ExportService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListSessions` | `ListSessionsRequest` | `ListSessionsResponse` | `server` | `read` |  | `tested-pass` |
| `StartSession` | `StartSessionRequest` | `StartSessionResponse` | `none` | `mutating` |  | `tested-pass-safe-record` |
| `GetSessionState` | `GetSessionStateRequest` | `GetSessionStateResponse` | `none` | `read` |  | `tested-pass` |
| `StopSession` | `StopSessionRequest` | `StopSessionResponse` | `none` | `mutating` |  | `tested-pass-safe-record` |
| `DestroySession` | `DestroySessionRequest` | `DestroySessionResponse` | `none` | `review` |  | `tested-pass-safe-record` |
| `DownloadFile` | `DownloadFileRequest` | `FileChunk` | `server` | `read` |  | `tested-pass` |

### `axxonsoft.bl.node.internal.NgpNodeService`

Proto: `axxonsoft/bl/node/Node.Ancillary.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListSceneDescription` | `ListSceneDescriptionRequest` | `ListSceneDescriptionResponse` | `none` | `read` |  | `tested-pass` |

### `axxonsoft.bl.notifications.EMailNotifier`

Proto: `axxonsoft/bl/notifications/EMailNotifier.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `SendEMail` | `SendEMailRequest` | `SendEMailResponse` | `none` | `mutating` | `POST /v1/notifier/email:send` | `pending` |
| `GetActionState` | `GetActionStateRequest` | `GetActionStateResponse` | `none` | `read` | `GET /v1/notifier/email/actionstate` | `tested-warn-fixture-needed` |
| `GetSendMode` | `GetSendModeRequest` | `GetSendModeResponse` | `none` | `read` | `GET /v1/notifier/email/sendmode` | `tested-warn-fixture-needed` |

### `axxonsoft.bl.notifications.GSMNotifier`

Proto: `axxonsoft/bl/notifications/GSMNotifier.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `SendSMS` | `SendSMSRequest` | `SendSMSResponse` | `none` | `mutating` | `POST /v1/notifier/sms:send` | `pending` |
| `GetActionStateGSM` | `GetActionStateGSMRequest` | `GetActionStateGSMResponse` | `none` | `review` | `POST /v1/notifier/sms/actionstate` | `pending` |

### `axxonsoft.bl.package.InstallationPackageProvider`

Proto: `axxonsoft/bl/package/InstallationPackageProvider.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `CheckPackageAvailability` | `CheckPackageAvailabilityRequest` | `CheckPackageAvailabilityResponse` | `none` | `read` |  | `tested-pass` |
| `DownloadInstallerPackage` | `DownloadInstallerPackageRequest` | `DownloadInstallerPackageResponse` | `server` | `read` |  | `pending` |

### `axxonsoft.bl.ptz.TagAndTrackService`

Proto: `axxonsoft/bl/ptz/TagAndTrack.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListTrackers` | `ListTnTTrackersRequest` | `ListTnTTrackersResponse` | `none` | `read` | `GET /v1/tag_and_track/trackers` | `tested-warn-fixture-needed` |
| `SetMode` | `SetModeRequest` | `SetModeResponse` | `none` | `mutating` | `POST /v1/tag_and_track/action:mode` | `pending` |
| `FollowTrack` | `TnTFollowTrackRequest` | `TnTFollowTrackResponse` | `none` | `mutating` | `POST /v1/tag_and_track/action:follow` | `pending` |
| `MoveToCoords` | `TnTMoveToCoordsRequest` | `TnTMoveToCoordsResponse` | `none` | `mutating` | `POST /v1/tag_and_track/action:move` | `pending` |

### `axxonsoft.bl.ptz.TelemetryService`

Proto: `axxonsoft/bl/ptz/Telemetry.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `AcquireSessionId` | `AcquireSessionRequest` | `AcquireSessionResponse` | `none` | `read` | `GET /v1/telemetry/sessions` | `pending` |
| `KeepAlive` | `SessionRequest` | `KeepAliveResponse` | `none` | `mutating` | `POST /v1/telemetry/sessions:keepAlive` | `pending` |
| `ReleaseSessionId` | `SessionRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry/sessions:release` | `pending` |
| `IsSessionAvailable` | `IsSessionAvailableRequest` | `IsSessionAvailableResponse` | `none` | `review` | `POST /v1/telemetry/sessions:checkAvailability` | `pending` |
| `Move` | `MoveRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:move` | `pending` |
| `Zoom` | `CommonRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:zoom` | `pending` |
| `Focus` | `CommonRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:focus` | `pending` |
| `FocusAuto` | `SessionID` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:focusAuto` | `pending` |
| `Iris` | `CommonRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:iris` | `pending` |
| `IrisAuto` | `SessionID` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:irisAuto` | `pending` |
| `AbsoluteMove` | `AbsoluteMoveRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:absoluteMove` | `pending` |
| `AbsoluteMoveNormalized` | `AbsoluteMoveNormalizedRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:absoluteMoveN` | `pending` |
| `GetPositionInformation` | `GetPositionInformationRequest` | `GetPositionInformationResponse` | `none` | `read` | `GET /v1/telemetry/position` | `tested-warn-fixture-needed` |
| `GetPositionInformationNormalized` | `GetPositionInformationRequest` | `GetPositionInformationNormalizedResponse` | `none` | `read` | `GET /v1/telemetry/position_n` | `tested-warn-fixture-needed` |
| `SetPreset` | `SetPresetRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry/presets:set` | `pending` |
| `SetPreset2` | `SetPresetRequest` | `SetPresetResponse` | `none` | `mutating` | `POST /v1/telemetry/presets:set2` | `pending` |
| `ConfigurePreset` | `ConfigurePresetRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:configure` | `pending` |
| `GoPreset` | `GoPresetRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry/presets:go` | `pending` |
| `RemovePreset` | `RemovePresetRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry/presets:remove` | `pending` |
| `PointMove` | `PointMoveRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:pointMove` | `pending` |
| `AreaZoom` | `AreaZoomRequest` | `google.protobuf.Empty` | `none` | `mutating` | `POST /v1/telemetry:areaZoom` | `pending` |
| `GetPresetsInfo` | `GetPresetsInfoRequest` | `PresetCollectionResponse` | `none` | `read` | `GET /v1/telemetry/presets` | `tested-warn-fixture-needed` |
| `GetAuxiliaryOperations` | `GetAuxiliaryOperationsRequest` | `GetAuxiliaryOperationsResponse` | `none` | `read` | `GET /v1/telemetry/operations` | `tested-warn-fixture-needed` |
| `PerformAuxiliaryOperation` | `PerformAuxiliaryOperationRequest` | `PerformAuxiliaryOperationResponse` | `none` | `mutating` | `POST /v1/telemetry:performOperations` | `pending` |
| `GetTours` | `GetToursRequest` | `GetToursResponse` | `none` | `read` | `GET /v1/telemetry/tours` | `tested-warn-fixture-needed` |
| `GetTourPoints` | `GetTourPointsRequest` | `GetTourPointsResponse` | `none` | `read` | `GET /v1/telemetry/tours/points` | `tested-warn-fixture-needed` |
| `PlayTour` | `PlayTourRequest` | `PlayTourResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:play` | `pending` |
| `StopTour` | `StopTourRequest` | `StopTourResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:stop` | `pending` |
| `StartFillTour` | `StartFillTourRequest` | `StartFillTourResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:startFill` | `pending` |
| `SetTourPoint` | `SetTourPointRequest` | `SetTourPointResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:setPoint` | `pending` |
| `StopFillTour` | `StopFillTourRequest` | `StopFillTourResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:stopFill` | `pending` |
| `RemoveTour` | `RemoveTourRequest` | `RemoveTourResponse` | `none` | `mutating` | `POST /v1/telemetry/tours:remove` | `pending` |

### `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerExternalService`

Proto: `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizerExternal.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetData` | `GetDataRequest` | `GetDataResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerService`

Proto: `axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ChangeLists` | `ChangeListsRequest` | `ChangeListsResponse` | `none` | `mutating` |  | `pending` |
| `ChangeListsStream` | `ChangeListsStreamRequest` | `ChangeListsStreamResponse` | `bidi` | `mutating` |  | `pending` |
| `ChangeItems` | `ChangeItemsRequest` | `ChangeItemsResponse` | `bidi` | `mutating` |  | `pending` |
| `GetLists` | `GetListsRequest` | `GetListsResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |
| `GetListStream` | `GetListStreamRequest` | `GetListStreamResponse` | `server` | `read` |  | `tested-warn-fixture-needed` |
| `GetItems` | `GetItemsRequest` | `GetItemsResponse` | `server` | `read` |  | `tested-warn-fixture-needed` |
| `Clear` | `ClearRequest` | `ClearResponse` | `none` | `mutating` |  | `pending` |

### `axxonsoft.bl.security.SecurityService`

Proto: `axxonsoft/bl/security/SecurityService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListConfig` | `ListConfigRequest` | `ListConfigResponse` | `none` | `read` | `GET /v1/security/config` | `tested-pass` |
| `ListRoles` | `ListRolesRequest` | `ListRolesResponse` | `none` | `read` | `GET /v1/security/roles` | `tested-pass` |
| `ListUsers` | `ListUsersRequest` | `ListUsersResponse` | `none` | `read` | `GET /v1/security/users` | `tested-pass` |
| `ListLDAPServers` | `ListLDAPServersRequest` | `ListLDAPServersResponse` | `none` | `read` | `GET /v1/security/ldapservers` | `tested-pass` |
| `TestLDAPConnection` | `TestLDAPConnectionRequest` | `TestLDAPConnectionResponse` | `none` | `mutating` | `POST /v1/security/ldap:testConnection` | `pending` |
| `GetLDAPSynchronization` | `GetLDAPSynchronizationRequest` | `LDAPSynchronization` | `none` | `read` | `GET /v1/security/ldapsynchronization` | `tested-pass` |
| `GetLDAPSynchronizationState` | `GetLDAPSynchronizationStateRequest` | `LDAPSynchronizationState` | `none` | `read` | `GET /v1/security/ldapsynchronization/state` | `tested-warn-fixture-needed` |
| `StartLDAPSynchronization` | `StartLDAPSynchronizationRequest` | `StartLDAPSynchronizationResponse` | `none` | `mutating` | `POST /v1/security/ldapsynchronization:start` | `pending` |
| `StopLDAPSynchronization` | `StopLDAPSynchronizationRequest` | `StopLDAPSynchronizationResponse` | `none` | `mutating` | `POST /v1/security/ldapsynchronization:stop` | `pending` |
| `GetPolicies` | `GetPoliciesRequest` | `GetPoliciesResponse` | `none` | `read` | `GET /v1/security/policies` | `tested-pass` |
| `GetCloudConfig` | `GetCloudConfigRequest` | `GetCloudConfigResponse` | `none` | `read` | `GET /v1/security/cloud/config` | `tested-pass` |
| `ChangeConfig` | `ChangeConfigRequest` | `ChangeConfigResponse` | `none` | `mutating` | `POST /v1/security/config:change` | `tested-pass-safe-record` |
| `CheckPassword` | `CheckPasswordRequest` | `CheckPasswordResponse` | `none` | `review` | `POST /v1/security/checkpass` | `pending` |
| `ListGlobalPermissions` | `ListGlobalPermissionsRequest` | `ListGlobalPermissionsResponse` | `none` | `read` | `GET /v1/security/permissions/global` | `tested-pass` |
| `SetGlobalPermissions` | `SetGlobalPermissionsRequest` | `SetGlobalPermissionsResponse` | `none` | `mutating` | `POST /v1/security/permissions/global:update` | `tested-pass-safe-record` |
| `ListGroupsPermissions` | `ListGroupsPermissionsRequest` | `ListGroupsPermissionsResponse` | `none` | `read` | `GET /v1/security/permissions/groups` | `tested-pass` |
| `ListGroupsPermissionsInfo` | `ListGroupsPermissionsInfoRequest` | `ListGroupsPermissionsInfoResponse` | `none` | `read` | `GET /v1/security/permissions/groupsInfo` | `tested-pass` |
| `SetGroupsPermissions` | `SetGroupsPermissionsRequest` | `SetGroupsPermissionsResponse` | `none` | `mutating` | `POST /v1/security/permissions/groups:update` | `tested-pass-safe-record` |
| `ListObjectPermissions` | `ListObjectPermissionsRequest` | `ListObjectPermissionsResponse` | `none` | `read` | `GET /v1/security/permissions/objects` | `tested-pass` |
| `ListObjectsPermissionsInfo` | `ListObjectsPermissionsInfoRequest` | `ListObjectsPermissionsInfoResponse` | `none` | `read` | `GET /v1/security/permissions/objectsInfo` | `tested-pass` |
| `SetObjectPermissions` | `SetObjectPermissionsRequest` | `SetObjectPermissionsResponse` | `none` | `mutating` | `POST /v1/security/permissions/objects:update` | `tested-pass-safe-record` |
| `ListMacrosPermissions` | `ListMacrosPermissionsRequest` | `ListMacrosPermissionsResponse` | `none` | `read` | `GET /v1/security/permissions/macros` | `tested-pass` |
| `ListMacrosPermissionsPaged` | `ListMacrosPermissionsPagedRequest` | `ListMacrosPermissionsPagedResponse` | `none` | `read` | `GET /v1/security/permissions/macrosPaged` | `tested-pass` |
| `SetMacrosPermissions` | `SetMacrosPermissionsRequest` | `SetMacrosPermissionsResponse` | `none` | `mutating` | `POST /v1/security/permissions/macros:update` | `tested-pass-safe-record` |
| `SearchLDAP` | `SearchLDAPRequest` | `SearchLDAPResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |
| `SearchLDAP2` | `SearchLDAPRequest2` | `SearchLDAPResponse2` | `none` | `review` | `POST /v1/security/ldap:search` | `pending` |
| `SearchLDAPGroups` | `SearchLDAPGroupsRequest` | `SearchLDAPGroupsResponse` | `none` | `review` | `POST /v1/security/ldap/groups:search` | `pending` |
| `GenGoogleAuthSecret` | `GenGoogleAuthSecretRequest` | `GenGoogleAuthSecretResponse` | `none` | `review` |  | `pending` |
| `EnableGoogleAuth` | `EnableGoogleAuthRequest` | `EnableGoogleAuthResponse` | `none` | `review` |  | `pending` |
| `DisableGoogleAuth` | `DisableGoogleAuthRequest` | `DisableGoogleAuthResponse` | `none` | `review` |  | `pending` |
| `CheckLogin` | `CheckLoginRequest` | `CheckLoginResponse` | `none` | `read` | `GET /v1/security/checklogin` | `tested-pass` |
| `ListUserGlobalPermissions` | `google.protobuf.Empty` | `ListUserGlobalPermissionsResponse` | `none` | `read` | `GET /v1/security/permissions/global/user` | `tested-pass` |
| `GetRestrictedConfig` | `GetRestrictedConfigRequest` | `GetRestrictedConfigResponse` | `none` | `read` | `GET /v1/security/config/user` | `tested-pass` |
| `ChangePassword` | `ChangePasswordRequest` | `ChangePasswordResponse` | `none` | `mutating` | `POST /v1/security/password:change` | `pending` |
| `ChangeLogin` | `ChangeLoginRequest` | `ChangeLoginResponse` | `none` | `mutating` | `POST /v1/security/login:change` | `pending` |

### `axxonsoft.bl.settings.DomainSettingsService`

Proto: `axxonsoft/bl/settings/DomainSettingsService.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetDataStorageSettings` | `GetDataStorageSettingsRequest` | `DataStorageSettings` | `none` | `read` |  | `tested-pass` |
| `UpdateDataStorageSettings` | `UpdateDataStorageSettingsRequest` | `DataStorageSettings` | `none` | `mutating` |  | `pending` |
| `GetExportSettings` | `GetExportSettingsRequest` | `GetExportSettingsResponse` | `none` | `read` |  | `tested-pass` |
| `UpdateExportSettings` | `UpdateExportSettingsRequest` | `UpdateExportSettingsResponse` | `none` | `mutating` |  | `tested-pass-safe-record` |
| `GetGDPRSettings` | `GetGDPRSettingsRequest` | `GetGDPRSettingsResponse` | `none` | `read` |  | `tested-pass` |
| `UpdateGDPRSettings` | `UpdateGDPRSettingsRequest` | `UpdateGDPRSettingsResponse` | `none` | `mutating` |  | `pending` |
| `GetBookmarkSettings` | `GetBookmarkSettingsRequest` | `GetBookmarkSettingsResponse` | `none` | `read` |  | `tested-pass` |
| `UpdateBookmarkSettings` | `UpdateBookmarkSettingsRequest` | `UpdateBookmarkSettingsResponse` | `none` | `mutating` |  | `pending` |

### `axxonsoft.bl.settings.generic.GenericSettingsService`

Proto: `axxonsoft/bl/settings/generic/GenericSettings.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetSettings` | `GetSettingsRequest` | `GetSettingsResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |
| `SaveSettings` | `SaveSettingsRequest` | `SaveSettingsResponse` | `none` | `review` |  | `pending` |
| `RemoveSettings` | `RemoveSettingsRequest` | `RemoveSettingsResponse` | `none` | `mutating` |  | `pending` |

### `axxonsoft.bl.state.StateControlService`

Proto: `axxonsoft/bl/state/StateControl.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `SetState` | `SetStateRequest` | `SetStateResponse` | `none` | `mutating` |  | `pending` |
| `GetDefaultState` | `GetDefaultStateRequest` | `GetDefaultStateResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |
| `GetCurrentState` | `GetCurrentStateRequest` | `GetCurrentStateResponse` | `none` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.statistics.StatisticService`

Proto: `axxonsoft/bl/statistics/Statistics.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `GetStatistics` | `StatsRequest` | `StatsResponse` | `none` | `read` |  | `tested-pass` |

### `axxonsoft.bl.tz.TimeZoneManager`

Proto: `axxonsoft/bl/tz/TimeZonesManager.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `ListTimeZones` | `ListTimeZonesRequest` | `ListTimeZonesResponse` | `none` | `read` | `GET /v1/time_zones` | `tested-pass` |
| `BatchGetZones` | `BatchGetTimeZonesRequest` | `BatchGetTimeZonesResponse` | `none` | `read` | `GET /v1/time_zones:batchGet` | `tested-pass` |
| `ChangeTimeZones` | `ChangeTimeZonesRequest` | `ChangeTimeZonesResponse` | `none` | `mutating` | `POST /v1/time_zones:change` | `pending` |
| `GetNTP` | `ListNTPRequest` | `ListNTPResponse` | `none` | `read` | `GET /v1/time_sync/ntp_server` | `tested-pass` |
| `SetNTP` | `SetNTPRequest` | `SetNTPResponse` | `none` | `mutating` | `POST /v1/time_sync/ntp_server:update` | `pending` |
| `SetTimeZone` | `SetTimeZoneRequest` | `SetTimeZoneResponse` | `none` | `mutating` | `POST /v1/time_zone:set` | `pending` |
| `GetTimeZone` | `GetTimeZoneRequest` | `GetTimeZoneResponse` | `none` | `read` | `GET /v1/time_zone` | `tested-pass` |

### `axxonsoft.bl.videowall.VideowallService`

Proto: `axxonsoft/bl/videowall/Videowall.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `RegisterWall` | `RegisterWallRequest` | `RegisterWallResponse` | `none` | `mutating` |  | `pending` |
| `UnregisterWall` | `UnregisterWallRequest` | `UnregisterWallResponse` | `none` | `mutating` |  | `pending` |
| `ChangeWall` | `ChangeWallRequest` | `ChangeWallResponse` | `none` | `mutating` |  | `pending` |
| `ListWalls` | `ListWallsRequest` | `ListWallsResponse` | `server` | `read` |  | `tested-pass` |
| `BatchGetWalls` | `BatchGetWallsRequest` | `BatchGetWallsResponse` | `server` | `read` |  | `tested-warn-fixture-needed` |
| `SetControlData` | `SetControlDataRequest` | `SetControlDataResponse` | `none` | `mutating` |  | `pending` |
| `GetMyControlData` | `GetMyControlDataRequest` | `GetMyControlDataResponse` | `server` | `read` |  | `tested-warn-fixture-needed` |

### `axxonsoft.bl.vmda.VMDAService`

Proto: `axxonsoft/bl/vmda/VMDA.proto`

| Method | Request | Response | Stream | Safety | HTTP | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `EnumerateSchemes` | `EnumerateSchemesRequest` | `EnumerateSchemesResponse` | `none` | `read` |  | `tested-pass` |
| `Cleanup` | `CleanupRequest` | `CleanupResponse` | `none` | `review` |  | `pending` |
| `ExecuteQuery` | `ExecuteQueryRequest` | `ExecuteQueryResponse` | `server` | `review` |  | `pending` |
| `ExecuteQueryTyped` | `ExecuteQueryTypedRequest` | `ExecuteQueryResponse` | `server` | `review` |  | `pending` |
