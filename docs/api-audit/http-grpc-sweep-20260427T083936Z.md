# Axxon One HTTP /grpc Sweep

- Started: `2026-04-27T08:39:36.979790+00:00`
- Finished: `2026-04-27T08:39:37.500126+00:00`
- HTTP target: `http://127.0.0.1:8000`
- Selected methods: `73`
- Skipped high-risk read methods: `11`

## Summary

- PASS: 65
- WARN: 8
- FAIL: 0

## Results

| Status | Method | ms | Notes |
| --- | --- | ---: | --- |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitTypes` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetArchiveTraits` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetRecordingInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory2` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetCalendar` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetSize` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetVolumesState` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetDiskSpace` | 6 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.auth.AuthenticationService.GetSessionInfo` | 2 | HTTP 500  |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnits` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPoints` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListTemplates` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListVendors` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListDevices` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.GetDevice` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.ListDirectory` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetFileInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetSpace` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.config.ServerSettings.GetLogLevel` | 2 | HTTP 500  |
| WARN | `axxonsoft.bl.config.SharedKVStorageService.ListRecords` | 3 | HTTP 500  |
| WARN | `axxonsoft.bl.config.SharedKVStorageService.BatchGetRecords` | 1 | HTTP 500  |
| PASS | `axxonsoft.bl.domain.DomainService.GetVersion` | 1 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostPlatformInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostTimeZone` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.ListNodes` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainManager.EnumerateNodes` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.groups.GroupManager.ListGroups` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.groups.GroupManager.BatchGetGroups` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.layout.LayoutManager.ListLayouts` | 13 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.license.LicenseService.GetGlobalRestrictions` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo` | 3 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.license.LicenseService.GetHostInfo` | 1 | transport RemoteDisconnected: Remote end closed connection without response |
| WARN | `axxonsoft.bl.logic.EventDescription.GetEventGroupingTags` | 4 | HTTP 500  |
| PASS | `axxonsoft.bl.logic.LogicService.ListMacros` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetMacros` | 1 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.GetConfig` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.ListCounters` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetCounters` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.GetUserScripts` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maintenance.ConfigurationManager.GetRevisionInfo` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.ListMaps` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.BatchGetMaps` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.GetMapsByComponent` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.ListMapProviders` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.node.internal.NgpNodeService.ListSceneDescription` | 3 | HTTP 500  |
| WARN | `axxonsoft.bl.package.InstallationPackageProvider.CheckPackageAvailability` | 2 | HTTP 500  |
| PASS | `axxonsoft.bl.security.SecurityService.ListConfig` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListRoles` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUsers` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListLDAPServers` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetLDAPSynchronization` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetPolicies` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetCloudConfig` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGlobalPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissions` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListObjectPermissions` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissions` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.CheckLogin` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUserGlobalPermissions` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetRestrictedConfig` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetDataStorageSettings` | 8 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetExportSettings` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetGDPRSettings` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetBookmarkSettings` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.statistics.StatisticService.GetStatistics` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.ListTimeZones` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.BatchGetZones` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetNTP` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetTimeZone` | 47 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.vmda.VMDAService.EnumerateSchemes` | 8 | HTTP 200 application/json; charset=utf-8 |
