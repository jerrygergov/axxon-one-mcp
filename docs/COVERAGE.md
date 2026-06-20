# Coverage

Live status of each Axxon One gRPC RPC exposed by this MCP server, generated from
`docs/api-audit/mcp-corpus/api_methods.json` (the authoritative source).

**288 / 363 RPCs live-verified** across 52 services (20 pending, 55 fixture-blocked).

- **tested-pass** — exercised end-to-end against a live server and returned a valid response.
- **fixture-blocked** — exercised live, but the stand lacked required hardware, configuration, or infrastructure.
- **pending** — not yet exercised live.

| Service | Verified | Fixture-blocked | Pending | Total |
| --- | ---: | ---: | ---: | ---: |
| SecurityService | 28 | 7 | 0 | 35 |
| TelemetryService | 22 | 10 | 0 | 32 |
| LogicService | 24 | 5 | 0 | 29 |
| DomainService | 21 | 0 | 0 | 21 |
| ArchiveService | 13 | 4 | 0 | 17 |
| EventHistoryService | 13 | 0 | 0 | 13 |
| ConfigurationService | 11 | 1 | 0 | 12 |
| AuthenticationService | 8 | 4 | 0 | 12 |
| MapService | 11 | 0 | 0 | 11 |
| LicenseService | 8 | 0 | 3 | 11 |
| DomainSettingsService | 7 | 1 | 0 | 8 |
| AcfaService | 7 | 0 | 0 | 7 |
| BookmarkService | 7 | 0 | 0 | 7 |
| RealtimeRecognizerService | 7 | 0 | 0 | 7 |
| TimeZoneManager | 7 | 0 | 0 | 7 |
| AuditEventInjector | 6 | 1 | 0 | 7 |
| VideowallService | 5 | 2 | 0 | 7 |
| GlobalTrackerService | 1 | 6 | 0 | 7 |
| ExportService | 6 | 0 | 0 | 6 |
| HeatMapService | 5 | 1 | 0 | 6 |
| MediaService | 5 | 1 | 0 | 6 |
| NodeNotifier | 5 | 0 | 1 | 6 |
| DevicesCatalog | 5 | 0 | 0 | 5 |
| LayoutManager | 5 | 0 | 0 | 5 |
| DiscoveryService | 4 | 1 | 0 | 5 |
| DomainNotifier | 4 | 0 | 1 | 5 |
| BackupSourceService | 0 | 2 | 3 | 5 |
| GroupManager | 4 | 0 | 0 | 4 |
| LayoutImagesManager | 4 | 0 | 0 | 4 |
| SharedKVStorageService | 4 | 0 | 0 | 4 |
| VMDAService | 4 | 0 | 0 | 4 |
| ConfigurationManager | 2 | 0 | 2 | 4 |
| DomainManager | 1 | 0 | 3 | 4 |
| CloudService | 0 | 1 | 3 | 4 |
| TagAndTrackService | 0 | 4 | 0 | 4 |
| FileSystemBrowser | 3 | 0 | 0 | 3 |
| GenericSettingsService | 3 | 0 | 0 | 3 |
| ServerSettings | 3 | 0 | 0 | 3 |
| StateControlService | 3 | 0 | 0 | 3 |
| EMailNotifier | 0 | 2 | 1 | 3 |
| DynamicParametersService | 2 | 0 | 0 | 2 |
| ExternalDetectorService | 2 | 0 | 0 | 2 |
| Health | 2 | 0 | 0 | 2 |
| InstallationPackageProvider | 1 | 0 | 1 | 2 |
| GSMNotifier | 0 | 0 | 2 | 2 |
| ArchiveVolumeService | 1 | 0 | 0 | 1 |
| EventDescription | 1 | 0 | 0 | 1 |
| MetadataService | 1 | 0 | 0 | 1 |
| NgpNodeService | 1 | 0 | 0 | 1 |
| StatisticService | 1 | 0 | 0 | 1 |
| RealtimeRecognizerExternalService | 0 | 1 | 0 | 1 |
| TextEventSupportService | 0 | 1 | 0 | 1 |
| **Total** | **288** | **55** | **20** | **363** |
