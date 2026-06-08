# Coverage

Live status of each Axxon One gRPC RPC exposed by this MCP server, generated from
`docs/api-audit/mcp-corpus/api_methods.json` (the authoritative source).

**283 / 361 RPCs live-verified** across 51 services (20 pending, 58 fixture-blocked).

- **tested-pass** — exercised end-to-end against a live server, returns a valid response.
- **fixture-warn** — the RPC works but the test stand lacks a required fixture (specific device driver, hardware, or server feature), so a clean pass needs that fixture.
- **pending** — not yet exercised live; mostly destructive/irreversible operations (license, backup/restore, domain topology, cloud bind) or ones needing external infra (SMTP/GSM).

| Service | Verified | Fixture-blocked | Pending | Total |
| --- | ---: | ---: | ---: | ---: |
| SecurityService | 28 | 7 | 0 | 35 |
| LogicService | 24 | 5 | 0 | 29 |
| TelemetryService | 22 | 10 | 0 | 32 |
| DomainService | 21 | 0 | 0 | 21 |
| ArchiveService | 13 | 4 | 0 | 17 |
| EventHistoryService | 13 | 0 | 0 | 13 |
| ConfigurationService | 11 | 1 | 0 | 12 |
| MapService | 11 | 0 | 0 | 11 |
| AuthenticationService | 8 | 4 | 0 | 12 |
| LicenseService | 8 | 0 | 3 | 11 |
| AcfaService | 7 | 0 | 0 | 7 |
| BookmarkService | 7 | 0 | 0 | 7 |
| DomainSettingsService | 7 | 1 | 0 | 8 |
| RealtimeRecognizerService | 7 | 0 | 0 | 7 |
| TimeZoneManager | 7 | 0 | 0 | 7 |
| AuditEventInjector | 6 | 1 | 0 | 7 |
| ExportService | 6 | 0 | 0 | 6 |
| DevicesCatalog | 5 | 0 | 0 | 5 |
| HeatMapService | 5 | 1 | 0 | 6 |
| LayoutManager | 5 | 0 | 0 | 5 |
| MediaService | 5 | 1 | 0 | 6 |
| NodeNotifier | 5 | 0 | 1 | 6 |
| VideowallService | 5 | 2 | 0 | 7 |
| DiscoveryService | 4 | 1 | 0 | 5 |
| DomainNotifier | 4 | 0 | 1 | 5 |
| GroupManager | 4 | 0 | 0 | 4 |
| LayoutImagesManager | 4 | 0 | 0 | 4 |
| SharedKVStorageService | 4 | 0 | 0 | 4 |
| VMDAService | 4 | 0 | 0 | 4 |
| FileSystemBrowser | 3 | 0 | 0 | 3 |
| GenericSettingsService | 3 | 0 | 0 | 3 |
| ServerSettings | 3 | 0 | 0 | 3 |
| ConfigurationManager | 2 | 0 | 2 | 4 |
| DynamicParametersService | 2 | 0 | 0 | 2 |
| ExternalDetectorService | 2 | 0 | 0 | 2 |
| ArchiveVolumeService | 1 | 0 | 0 | 1 |
| DomainManager | 1 | 0 | 3 | 4 |
| EventDescription | 1 | 0 | 0 | 1 |
| GlobalTrackerService | 1 | 6 | 0 | 7 |
| InstallationPackageProvider | 1 | 0 | 1 | 2 |
| MetadataService | 1 | 0 | 0 | 1 |
| NgpNodeService | 1 | 0 | 0 | 1 |
| StatisticService | 1 | 0 | 0 | 1 |
| BackupSourceService | 0 | 2 | 3 | 5 |
| CloudService | 0 | 1 | 3 | 4 |
| EMailNotifier | 0 | 2 | 1 | 3 |
| GSMNotifier | 0 | 0 | 2 | 2 |
| RealtimeRecognizerExternalService | 0 | 1 | 0 | 1 |
| StateControlService | 0 | 3 | 0 | 3 |
| TagAndTrackService | 0 | 4 | 0 | 4 |
| TextEventSupportService | 0 | 1 | 0 | 1 |
| **Total** | **283** | **58** | **20** | **361** |

