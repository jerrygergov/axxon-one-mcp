# Axxon One Read-Only gRPC Sweep

- Started: `2026-04-26T19:25:36.289508+00:00`
- Finished: `2026-04-26T19:25:46.851628+00:00`
- gRPC target: `127.0.0.1:20109`
- TLS CN override: `F4E66972EC19`
- Selected methods: `149`
- Skipped high-risk read methods: `11`

## Summary

- PASS: 113
- WARN: 36
- FAIL: 0

## Results

| Status | Method | ms | Notes |
| --- | --- | ---: | --- |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitsActions` | 3 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitsVisualizations` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitsEvents` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitsStates` | 0 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.acfa.AcfaService.ListUnitTypes` | 3 | bytes=0 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetArchiveTraits` | 5 | traits:1 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetRecordingInfo` | 2 | recording_info:object |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory` | 2 | intervals:1 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistory2` | 2 | intervals:1 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetHistoryStream` | 2 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetCalendar` | 2 | days:1 |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetSize` | 1 | size:str, duration:str |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetVolumesState` | 2 | volumes_state:object |
| PASS | `axxonsoft.bl.archive.ArchiveService.GetDiskSpace` | 5 | space:object |
| WARN | `axxonsoft.bl.archive.BackupSourceService.IsBackupInProgress` | 3 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.archive.BackupSourceService.GetRestProgress` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| PASS | `axxonsoft.bl.auth.AuthenticationService.GetSessionInfo` | 1 | expires_at:object |
| WARN | `axxonsoft.bl.cloud.CloudService.GetBindingConfiguration` | 15 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: user exception, ID 'IDL:ovsoft.ru/CloudClient/NotFound:1.0'"
	debug_error |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnits` | 2 | units:1 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnitsStream` | 0 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPoints` | 1 | not_found_objects:1 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListUnitsByAccessPointsStream` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.config.ConfigurationService.ListTemplates` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListVendors` | 2 | vendors:100, next_page_token:str |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListVendorsV2` | 1 | stream_pages_read=2 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListDevices` | 1 | devices:7 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.ListDevicesV2` | 1 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.config.DevicesCatalog.GetDevice` | 1 | device:object |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.ListDirectory` | 3 | entries:11 |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetFileInfo` | 1 | file_info:object, parent_path:str |
| PASS | `axxonsoft.bl.config.FileSystemBrowser.GetSpace` | 1 | space_info:object |
| PASS | `axxonsoft.bl.config.ServerSettings.GetLogLevel` | 4 | node_log_level:object |
| PASS | `axxonsoft.bl.config.SharedKVStorageService.ListRecords` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.config.SharedKVStorageService.BatchGetRecords` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.config.SharedKVStorageService.GetRecordsStream` | 1 | stream_pages_read=0 |
| WARN | `axxonsoft.bl.discovery.DiscoveryService.GetDiscoveryProgress` | 5010 | StatusCode.DEADLINE_EXCEEDED <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.DEADLINE_EXCEEDED
	details = "Deadline Exceeded"
	debug_error_string = "UNKNOWN:Error received from peer |
| WARN | `axxonsoft.bl.discovery.DiscoveryService.GetNodeDiscoveryProgress` | 5008 | StatusCode.DEADLINE_EXCEEDED <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.DEADLINE_EXCEEDED
	details = "Deadline Exceeded"
	debug_error_string = "UNKNOWN:Error received from peer |
| WARN | `axxonsoft.bl.discovery.DiscoveryService.Probe` | 2 | StatusCode.INVALID_ARGUMENT <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "Connection info is empty."
	debug_error_string = "UNKNOWN:Error received from peer |
| PASS | `axxonsoft.bl.domain.DomainService.GetVersion` | 1 | Version:str |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostPlatformInfo` | 2 | os_sys_name:str, os_release:str, os_version:str, os_machine:str, computer_name:str |
| PASS | `axxonsoft.bl.domain.DomainService.GetHostTimeZone` | 1 | time_zone:int |
| PASS | `axxonsoft.bl.domain.DomainService.ListCameras` | 2 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.domain.DomainService.ListArchives` | 1 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.domain.DomainService.ListControlPanels` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.BatchGetControlPanels` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListCommonDevices` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.BatchGetCommonDevices` | 0 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListComponents` | 2 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.domain.DomainService.ListGlobalTrackers` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListGlobalTrackerCameras` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListAcfaComponents` | 2 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListAcfaComponents2` | 2 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListPluginComponents` | 3 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.BatchGetAcfaComponents` | 1 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.domain.DomainService.ListNodes` | 2 | nodes:1 |
| PASS | `axxonsoft.bl.domain.DomainManager.EnumerateNodes` | 4 | domain:object, nodes:1 |
| WARN | `axxonsoft.bl.domain.TextEventSupportService.GetTextEvent` | 3 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Internal errors occurred: tracking-id:SCqc-RNuSXe@F4E66972EC19"
	debug_error_string = "UNK |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadEvents` | 11 | stream_pages_read=2 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadCount` | 5 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadTextEvents` | 4 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadTextCount` | 4 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadAlerts` | 4 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadLprEvents` | 3 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.ReadBookmarks` | 2 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindByPrompt` | 3 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindContacts` | 3 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindSimilarObjects` | 5 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindSimilarObjects2` | 3 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindStrangers` | 6 | stream_pages_read=1 |
| PASS | `axxonsoft.bl.events.EventHistoryService.FindStrangersByObjects` | 6 | stream_pages_read=1 |
| WARN | `axxonsoft.bl.globaltracker.GlobalTrackerService.GetGlobalTrackerProfiles` | 11 | StatusCode.UNIMPLEMENTED <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.UNIMPLEMENTED
	details = ""
	debug_error_string = "UNKNOWN:Error received from peer ipv4:127.0.0.1:20109 |
| PASS | `axxonsoft.bl.globaltracker.GlobalTrackerService.GetProfile` | 3 | stream_pages_read=0 |
| WARN | `axxonsoft.bl.globaltracker.GlobalTrackerService.GetGlobalTrackBestVisibilityPositions` | 2 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: system exception, ID 'IDL:omg.org/CORBA/OBJECT_NOT_EXIST:1.0'
Unknown ven |
| PASS | `axxonsoft.bl.groups.GroupManager.ListGroups` | 8 | groups:1 |
| PASS | `axxonsoft.bl.groups.GroupManager.BatchGetGroups` | 1 | bytes=0 |
| WARN | `axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages` | 5 | StatusCode.NOT_FOUND <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.NOT_FOUND
	details = "Layout not found: . User: root"
	debug_error_string = "UNKNOWN:Error received from peer i |
| PASS | `axxonsoft.bl.layout.LayoutManager.ListLayouts` | 5 | current:str, items:2, special_layouts:object |
| PASS | `axxonsoft.bl.license.LicenseService.GetGlobalRestrictions` | 2 | constraints:object |
| PASS | `axxonsoft.bl.license.LicenseService.GetDomainLicenseKeyInfo` | 2 | responses:1 |
| PASS | `axxonsoft.bl.license.LicenseService.GetHostInfo` | 1 | hwinfo:str |
| PASS | `axxonsoft.bl.logic.EventDescription.GetEventGroupingTags` | 3 | bytes=0 |
| PASS | `axxonsoft.bl.logic.LogicService.ListMacros` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.logic.LogicService.ListMacrosV2` | 0 | stream_pages_read=0 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetMacros` | 0 | bytes=0 |
| PASS | `axxonsoft.bl.logic.LogicService.GetConfig` | 1 | user_alert_ttl:object, rule_alert_ttl:object, conditional_ttl:object, required_comment:object, max_event_age:object |
| PASS | `axxonsoft.bl.logic.LogicService.ListCounters` | 0 | bytes=0 |
| PASS | `axxonsoft.bl.logic.LogicService.BatchGetCounters` | 0 | bytes=0 |
| WARN | `axxonsoft.bl.logic.LogicService.GetCounterState` | 2 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: user exception, ID 'IDL:ovsoft.ru/NVRBL/LogicServer/InvalidCounterId:1.0' |
| WARN | `axxonsoft.bl.logic.LogicService.GetCounterGroupState` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: user exception, ID 'IDL:ovsoft.ru/NVRBL/LogicServer/InvalidCounterId:1.0' |
| PASS | `axxonsoft.bl.logic.LogicService.GetUserScripts` | 0 | bytes=0 |
| PASS | `axxonsoft.bl.maintenance.ConfigurationManager.GetRevisionInfo` | 4 | info:object |
| PASS | `axxonsoft.bl.maps.MapService.ListMaps` | 11 | bytes=0 |
| PASS | `axxonsoft.bl.maps.MapService.BatchGetMaps` | 2 | bytes=0 |
| WARN | `axxonsoft.bl.maps.MapService.GetMapImage` | 1 | StatusCode.PERMISSION_DENIED <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.PERMISSION_DENIED
	details = "Insufficient privileges to access map id: "
	debug_error_string = "UNKNOWN:Error |
| PASS | `axxonsoft.bl.maps.MapService.GetMapsByComponent` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.maps.MapService.ListMapProviders` | 1 | bytes=0 |
| WARN | `axxonsoft.bl.maps.MapService.GetMapProvider` | 2 | StatusCode.NOT_FOUND <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.NOT_FOUND
	details = "Requested provider not found"
	debug_error_string = "UNKNOWN:Error received from peer ipv |
| PASS | `axxonsoft.bl.mmexport.ExportService.ListSessions` | 3 | stream_pages_read=0 |
| WARN | `axxonsoft.bl.mmexport.ExportService.GetSessionState` | 2 | StatusCode.NOT_FOUND <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.NOT_FOUND
	details = "There is no session with provided ID"
	debug_error_string = "UNKNOWN:Error received from |
| PASS | `axxonsoft.bl.node.internal.NgpNodeService.ListSceneDescription` | 2 | scene_descriptions:2 |
| WARN | `axxonsoft.bl.notifications.EMailNotifier.GetActionState` | 3 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to /NotifyService"
	debug_error_string = "UNKNOWN:Error received f |
| WARN | `axxonsoft.bl.notifications.EMailNotifier.GetSendMode` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to /NotifyService"
	debug_error_string = "UNKNOWN:Error received f |
| PASS | `axxonsoft.bl.package.InstallationPackageProvider.CheckPackageAvailability` | 3 | bytes=0 |
| WARN | `axxonsoft.bl.ptz.TagAndTrackService.ListTrackers` | 6 | StatusCode.NOT_FOUND <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.NOT_FOUND
	details = "Can't find specified component:"
	debug_error_string = "UNKNOWN:Error received from peer |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetPositionInformation` | 2 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetPositionInformationNormalized` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetPresetsInfo` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetAuxiliaryOperations` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetTours` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Failed to execute command, can not resolve access point."
	debug_error_string = "UNKNOWN:E |
| WARN | `axxonsoft.bl.ptz.TelemetryService.GetTourPoints` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Failed to execute command, can not resolve access point."
	debug_error_string = "UNKNOWN:E |
| WARN | `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerService.GetLists` | 3 | StatusCode.UNAVAILABLE <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Can't resolve reference to RealtimeRecognizer.0/Recognizer"
	debug_error_string = "UNKN |
| WARN | `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerService.GetListStream` | 1 | StatusCode.UNAVAILABLE <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Can't resolve reference to RealtimeRecognizer.0/Recognizer"
	debug_error_string |
| WARN | `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerService.GetItems` | 1 | StatusCode.UNAVAILABLE <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Can't resolve reference to RealtimeRecognizer.0/Recognizer"
	debug_error_string |
| WARN | `axxonsoft.bl.realtimerecognizer.RealtimeRecognizerExternalService.GetData` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| PASS | `axxonsoft.bl.security.SecurityService.ListConfig` | 5 | roles:2, users:1, user_assignments:1, pwd_policy:1, ldap_synchronization:object |
| PASS | `axxonsoft.bl.security.SecurityService.ListRoles` | 1 | roles:2 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUsers` | 1 | users:1, user_assignments:1 |
| PASS | `axxonsoft.bl.security.SecurityService.ListLDAPServers` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.GetLDAPSynchronization` | 1 | period_minutes:int |
| WARN | `axxonsoft.bl.security.SecurityService.GetLDAPSynchronizationState` | 2 | StatusCode.UNAVAILABLE <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Can't get connection channel!"
	debug_error_string = "UNKNOWN:Error received from peer |
| PASS | `axxonsoft.bl.security.SecurityService.GetPolicies` | 1 | pwd_policy:1 |
| PASS | `axxonsoft.bl.security.SecurityService.GetCloudConfig` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGlobalPermissions` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissions` | 3 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.ListGroupsPermissionsInfo` | 1 | items:1 |
| PASS | `axxonsoft.bl.security.SecurityService.ListObjectPermissions` | 2 | permissions:object |
| WARN | `axxonsoft.bl.security.SecurityService.ListObjectsPermissionsInfo` | 4 | StatusCode.INVALID_ARGUMENT <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "Incorrect role id."
	debug_error_string = "UNKNOWN:Error received from peer ipv4:1 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissions` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.ListMacrosPermissionsPaged` | 2 | bytes=0 |
| WARN | `axxonsoft.bl.security.SecurityService.SearchLDAP` | 8 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: system exception, ID 'IDL:omg.org/CORBA/UNKNOWN:1.0'
TAO exception, minor |
| PASS | `axxonsoft.bl.security.SecurityService.CheckLogin` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.security.SecurityService.ListUserGlobalPermissions` | 1 | permissions:object |
| PASS | `axxonsoft.bl.security.SecurityService.GetRestrictedConfig` | 2 | current_user:object, current_roles:1, all_roles:2, all_users:1, pwd_policy:1 |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetDataStorageSettings` | 12 | system_logs_settings:object |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetExportSettings` | 1 | settings:object, etag:str |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetGDPRSettings` | 0 | settings:object |
| PASS | `axxonsoft.bl.settings.DomainSettingsService.GetBookmarkSettings` | 0 | bytes=0 |
| WARN | `axxonsoft.bl.settings.generic.GenericSettingsService.GetSettings` | 3 | StatusCode.INVALID_ARGUMENT <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "Invalid settings context. Must be GUID"
	debug_error_string = "UNKNOWN:Error recei |
| WARN | `axxonsoft.bl.state.StateControlService.GetDefaultState` | 2 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| WARN | `axxonsoft.bl.state.StateControlService.GetCurrentState` | 1 | StatusCode.INTERNAL <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "Can't resolve reference to "
	debug_error_string = "UNKNOWN:Error received from peer ipv4: |
| PASS | `axxonsoft.bl.statistics.StatisticService.GetStatistics` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.ListTimeZones` | 4 | bytes=0 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.BatchGetZones` | 2 | bytes=0 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetNTP` | 1 | bytes=0 |
| PASS | `axxonsoft.bl.tz.TimeZoneManager.GetTimeZone` | 10 | bytes=0 |
| PASS | `axxonsoft.bl.videowall.VideowallService.ListWalls` | 7 | stream_pages_read=1 |
| WARN | `axxonsoft.bl.videowall.VideowallService.BatchGetWalls` | 1 | StatusCode.INVALID_ARGUMENT <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "Empty access point information."
	debug_error_string = "UNKNOWN:Error recei |
| WARN | `axxonsoft.bl.videowall.VideowallService.GetMyControlData` | 0 | StatusCode.INVALID_ARGUMENT <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "Empty cookie information."
	debug_error_string = "UNKNOWN:Error received fr |
| PASS | `axxonsoft.bl.vmda.VMDAService.EnumerateSchemes` | 4 | cs_IDs:1 |
