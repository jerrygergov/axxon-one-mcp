# Axxon One HTTP /v1 Sweep

- Started: `2026-04-27T08:56:37.490750+00:00`
- Finished: `2026-04-27T08:56:38.087029+00:00`
- HTTP target: `http://127.0.0.1:8000`
- Selected endpoints: `78`

## Summary

- PASS: 70
- WARN: 8
- FAIL: 0

## Results

| Status | Endpoint | Method | ms | Notes |
| --- | --- | --- | ---: | --- |
| PASS | `GET /v1/archive/traits` | `axxonsoft.bl.archive.ArchiveService.GetArchiveTraits` | 10 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/recordingInfo` | `axxonsoft.bl.archive.ArchiveService.GetRecordingInfo` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/history` | `axxonsoft.bl.archive.ArchiveService.GetHistory` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/history2` | `axxonsoft.bl.archive.ArchiveService.GetHistory2` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/historyStream` | `axxonsoft.bl.archive.ArchiveService.GetHistoryStream` | 4 | HTTP 200 text/event-stream |
| PASS | `GET /v1/archive/calendar` | `axxonsoft.bl.archive.ArchiveService.GetCalendar` | 4 | HTTP 200 application/json; charset=utf-8 |
| WARN | `GET /v1/archive/size` | `axxonsoft.bl.archive.ArchiveService.GetSize` | 4 | HTTP 500 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/volumes/state` | `axxonsoft.bl.archive.ArchiveService.GetVolumesState` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/archive/volumes/diskSpace` | `axxonsoft.bl.archive.ArchiveService.GetDiskSpace` | 8 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/bookmarks:list` | `axxonsoft.bl.bookmarks.BookmarkService.ListBookmarks` | 8 | HTTP 200 application/json; charset=utf-8 |
| WARN | `POST /v1/bookmarks:get` | `axxonsoft.bl.bookmarks.BookmarkService.GetBookmark` | 7 | HTTP 500 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/list` | `axxonsoft.bl.config.ConfigurationService.ListUnits` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/get` | `axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPoints` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/templates` | `axxonsoft.bl.config.ConfigurationService.ListTemplates` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/configurator/templates:batchGet` | `axxonsoft.bl.config.ConfigurationService.BatchGetTemplates` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/configurator/factories:batchGet` | `axxonsoft.bl.config.ConfigurationService.BatchGetFactories` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `POST /v1/configurator/units:listSimilar` | `axxonsoft.bl.config.ConfigurationService.ListSimilarUnits` | 3 | HTTP 400 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/devices_catalog/vendors` | `axxonsoft.bl.config.DevicesCatalog.ListVendors` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/devices_catalog/devices` | `axxonsoft.bl.config.DevicesCatalog.ListDevices` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/configurator/devices_catalog/device` | `axxonsoft.bl.config.DevicesCatalog.GetDevice` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/fs/list` | `axxonsoft.bl.config.FileSystemBrowser.ListDirectory` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/fs/file` | `axxonsoft.bl.config.FileSystemBrowser.GetFileInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/fs/space` | `axxonsoft.bl.config.FileSystemBrowser.GetSpace` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/domain/cameras` | `axxonsoft.bl.domain.DomainService.ListCameras` | 5 | HTTP 200 text/event-stream |
| PASS | `POST /v1/domain/cameras:batchGet` | `axxonsoft.bl.domain.DomainService.BatchGetCameras` | 4 | HTTP 200 text/event-stream |
| PASS | `POST /v1/domain/cameras:getByComponents` | `axxonsoft.bl.domain.DomainService.GetCamerasByComponents` | 4 | HTTP 200 text/event-stream |
| PASS | `GET /v1/domain/archives` | `axxonsoft.bl.domain.DomainService.ListArchives` | 2 | HTTP 200 text/event-stream |
| PASS | `POST /v1/domain/archives:batchGet` | `axxonsoft.bl.domain.DomainService.BatchGetArchives` | 3 | HTTP 200 text/event-stream |
| PASS | `GET /v1/domain/nodes` | `axxonsoft.bl.domain.DomainService.ListNodes` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/domain/maps:search` | `axxonsoft.bl.domain.DomainService.SearchMaps` | 2 | HTTP 200 text/event-stream |
| PASS | `GET /v1/domain/nodes:enumerate` | `axxonsoft.bl.domain.DomainManager.EnumerateNodes` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/groups/list` | `axxonsoft.bl.groups.GroupManager.ListGroups` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/groups:batchGet` | `axxonsoft.bl.groups.GroupManager.BatchGetGroups` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/layouts` | `axxonsoft.bl.layout.LayoutManager.ListLayouts` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/layouts:batchGet` | `axxonsoft.bl.layout.LayoutManager.BatchGetLayouts` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/license/globalRestrictions` | `axxonsoft.bl.license.LicenseService.GetGlobalRestrictions` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/license/nodeRestrictions` | `axxonsoft.bl.license.LicenseService.GetNodeRestrictions` | 4 | HTTP 200 text/event-stream |
| PASS | `POST /v1/license:verifyLaunchPossibility` | `axxonsoft.bl.license.LicenseService.IsPossibleToLaunch` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/license/domain` | `axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/logic_service/macros` | `axxonsoft.bl.logic.LogicService.ListMacros` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/logic_service/macros:batchGet` | `axxonsoft.bl.logic.LogicService.BatchGetMacros` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/logic_service/getactivealerts` | `axxonsoft.bl.logic.LogicService.GetActiveAlerts` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/logic_service/batchgetactivealerts` | `axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts` | 11 | HTTP 200 text/event-stream |
| PASS | `GET /v1/logic_service/config` | `axxonsoft.bl.logic.LogicService.GetConfig` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/logic_service/counters` | `axxonsoft.bl.logic.LogicService.ListCounters` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/logic_service/counters:batchGet` | `axxonsoft.bl.logic.LogicService.BatchGetCounters` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/logic_service/user_scripts` | `axxonsoft.bl.logic.LogicService.GetUserScripts` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/maps/list` | `axxonsoft.bl.maps.MapService.ListMaps` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/maps:batchGet` | `axxonsoft.bl.maps.MapService.BatchGetMaps` | 3 | HTTP 200 application/json; charset=utf-8 |
| WARN | `POST /v1/maps/markers` | `axxonsoft.bl.maps.MapService.GetMarkers` | 4 | HTTP 403 application/json; charset=utf-8 |
| PASS | `GET /v1/maps:getByComponent` | `axxonsoft.bl.maps.MapService.GetMapsByComponent` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/maps/providers` | `axxonsoft.bl.maps.MapService.ListMapProviders` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `POST /v1/notifier/sms/actionstate` | `axxonsoft.bl.notifications.GSMNotifier.GetActionStateGSM` | 4 | HTTP 500 application/json; charset=utf-8 |
| WARN | `POST /v1/telemetry/sessions:checkAvailability` | `axxonsoft.bl.ptz.TelemetryService.IsSessionAvailable` | 6 | HTTP 500 application/json; charset=utf-8 |
| PASS | `GET /v1/security/config` | `axxonsoft.bl.security.SecurityService.ListConfig` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/roles` | `axxonsoft.bl.security.SecurityService.ListRoles` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/users` | `axxonsoft.bl.security.SecurityService.ListUsers` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/ldapservers` | `axxonsoft.bl.security.SecurityService.ListLDAPServers` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/ldapsynchronization` | `axxonsoft.bl.security.SecurityService.GetLDAPSynchronization` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/policies` | `axxonsoft.bl.security.SecurityService.GetPolicies` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/cloud/config` | `axxonsoft.bl.security.SecurityService.GetCloudConfig` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `POST /v1/security/checkpass` | `axxonsoft.bl.security.SecurityService.CheckPassword` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/global` | `axxonsoft.bl.security.SecurityService.ListGlobalPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/groups` | `axxonsoft.bl.security.SecurityService.ListGroupsPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/groupsInfo` | `axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/objects` | `axxonsoft.bl.security.SecurityService.ListObjectPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/objectsInfo` | `axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/macros` | `axxonsoft.bl.security.SecurityService.ListMacrosPermissions` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/macrosPaged` | `axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `POST /v1/security/ldap:search` | `axxonsoft.bl.security.SecurityService.SearchLDAP2` | 3 | HTTP 500 application/json; charset=utf-8 |
| WARN | `POST /v1/security/ldap/groups:search` | `axxonsoft.bl.security.SecurityService.SearchLDAPGroups` | 3 | HTTP 500 application/json; charset=utf-8 |
| PASS | `GET /v1/security/checklogin` | `axxonsoft.bl.security.SecurityService.CheckLogin` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/permissions/global/user` | `axxonsoft.bl.security.SecurityService.ListUserGlobalPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/security/config/user` | `axxonsoft.bl.security.SecurityService.GetRestrictedConfig` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/time_zones` | `axxonsoft.bl.tz.TimeZoneManager.ListTimeZones` | 8 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/time_zones:batchGet` | `axxonsoft.bl.tz.TimeZoneManager.BatchGetZones` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/time_sync/ntp_server` | `axxonsoft.bl.tz.TimeZoneManager.GetNTP` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `GET /v1/time_zone` | `axxonsoft.bl.tz.TimeZoneManager.GetTimeZone` | 19 | HTTP 200 application/json; charset=utf-8 |
