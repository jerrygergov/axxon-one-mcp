# Axxon One HTTP /grpc Sweep

- Started: `2026-04-27T08:56:37.491757+00:00`
- Finished: `2026-04-27T08:56:38.095964+00:00`
- HTTP target: `http://127.0.0.1:8000`
- Selected methods: `75`
- Skipped high-risk read methods: `11`

## Summary

- PASS: 66
- WARN: 9
- FAIL: 0

## Results

| Status | Method | ms | Notes |
| --- | --- | ---: | --- |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitTypes` | 12 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetArchiveTraits` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetRecordingInfo` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory2` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetCalendar` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetSize` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetVolumesState` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetDiskSpace` | 8 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.auth.AuthenticationService.GetSessionInfo` | 3 | HTTP 500  |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnits` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPoints` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListTemplates` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListVendors` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListDevices` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.GetDevice` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.ListDirectory` | 7 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetFileInfo` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetSpace` | 5 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.config.ServerSettings.GetLogLevel` | 2 | HTTP 500  |
| WARN | `axxonsoft.bl.config.SharedKVStorageService.ListRecords` | 3 | HTTP 500  |
| WARN | `axxonsoft.bl.config.SharedKVStorageService.BatchGetRecords` | 1 | HTTP 500  |
| PASS | `axxonsoft.bl.domain.DomainService.GetVersion` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostPlatformInfo` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostTimeZone` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainService.ListNodes` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.domain.DomainManager.EnumerateNodes` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.groups.GroupManager.ListGroups` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.groups.GroupManager.BatchGetGroups` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages` | 9 | HTTP 500  |
| PASS | `axxonsoft.bl.layout.LayoutManager.ListLayouts` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.license.LicenseService.GetGlobalRestrictions` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo` | 6 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.license.LicenseService.GetHostInfo` | 3 | transport RemoteDisconnected: Remote end closed connection without response |
| WARN | `axxonsoft.bl.logic.EventDescription.GetEventGroupingTags` | 5 | HTTP 500  |
| PASS | `axxonsoft.bl.logic.LogicService.ListMacros` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetMacros` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.GetConfig` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.ListCounters` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetCounters` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.logic.LogicService.GetUserScripts` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maintenance.ConfigurationManager.GetRevisionInfo` | 12 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.ListMaps` | 9 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.BatchGetMaps` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.GetMapsByComponent` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.maps.MapService.ListMapProviders` | 2 | HTTP 200 application/json; charset=utf-8 |
| WARN | `axxonsoft.bl.node.internal.NgpNodeService.ListSceneDescription` | 4 | HTTP 500  |
| WARN | `axxonsoft.bl.package.InstallationPackageProvider.CheckPackageAvailability` | 3 | HTTP 500  |
| PASS | `axxonsoft.bl.security.SecurityService.ListConfig` | 8 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListRoles` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUsers` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListLDAPServers` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetLDAPSynchronization` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetPolicies` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetCloudConfig` | 5 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGlobalPermissions` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissions` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListObjectPermissions` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissions` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged` | 1 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.CheckLogin` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUserGlobalPermissions` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.security.SecurityService.GetRestrictedConfig` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetDataStorageSettings` | 6 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetExportSettings` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetGDPRSettings` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetBookmarkSettings` | 2 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.statistics.StatisticService.GetStatistics` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.ListTimeZones` | 8 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.BatchGetZones` | 4 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetNTP` | 3 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetTimeZone` | 19 | HTTP 200 application/json; charset=utf-8 |
| PASS | `axxonsoft.bl.vmda.VMDAService.EnumerateSchemes` | 6 | HTTP 200 application/json; charset=utf-8 |
