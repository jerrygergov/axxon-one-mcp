# Axxon One — Full Capability Inventory vs. MCP Coverage

**Date:** 2026-06-05
**Method:** Cross-referenced 51 gRPC services / 361 RPCs (`SERVICE_INDEX.md`,
`mcp-corpus/api_methods.json`) against the 121 MCP tools registered in
`tools/axxon_mcp_server.py`.

> **Important caveat on the numbers below.** The `live_status` field in
> `api_methods.json` was frozen on **2026-05-29** and was *not* re-stamped after
> Phases 5H/6/7/8 (2026-06-04/05). So services such as TelemetryService show
> "0% pass" in the corpus even though `axxon_mcp_ptz.py` shipped and STATUS.md
> records a live PTZ run. Two different ledgers disagree:
> - **Narrative ledger** (STATUS.md / roadmap): "every phase shipped, every gap closed."
> - **Evidence ledger** (corpus): 152/361 methods carry a live-pass stamp; 177 pending; 32 fixture-warn.
>
> The first task of any "finish coverage" effort is to **reconcile these two ledgers** —
> re-run the verified surfaces and re-stamp `live_status`, so the corpus stops
> underselling shipped work and starts honestly flagging the genuinely-missing work below.
>
> **Reconciliation pass 1 (2026-06-05, `tools/axxon_corpus_restamp.py`).** Flipped 14
> evidence-cited methods: 8 → `tested-pass` (PTZ acquire/availability/position/AbsoluteMove
> from Phase 8, VMDA `ExecuteQuery` from the 5H fix, the Google-auth TOTP trio from the
> 5F-B1 TFA lifecycle) and 6 PTZ continuous/preset verbs → `tested-warn-fixture-needed`
> (code ships + unit-tested, but the stand's emulator rejects them; they need a hardware
> PTZ camera). A new per-method `evidence` field now cites the source so the ledger cannot
> silently drift again. Post-pass: **160 tested-pass, 164 pending, 37 fixture-warn.**

---

## A. Capability map — the full surface the desktop client / gRPC API exposes

| Capability family | Services | Have MCP tools? | Notes |
| --- | --- | --- | --- |
| **Live + archive view** | MediaService, ArchiveService, ExportService, StatisticService | ✅ partial | `live_view`, `snapshot_batch`, `archive_scrub/frame/mjpeg`, `stream_health`. MediaService raw RPCs (6) unstamped. |
| **Events / history** | EventHistoryService, EventDescription | ✅ strong | `search_events`, `subscribe_events_bounded`, `find_event_suppliers` — 13/13 stamped. |
| **Live notifications** | DomainNotifier, NodeNotifier | ⚠️ thin | `domain_event_subscribe`/`node_event_subscribe` exist but all 11 RPCs unstamped. |
| **Detectors / analytics config** | LogicService, ExternalDetectorService, RealtimeRecognizerService, AcfaService, HeatMapService, VMDAService, MetadataService | ⚠️ partial | Rich tooling for AV/AppData detectors; LogicService 8/29, RealtimeRecognizer 0/7, HeatMap 0/6 stamped. |
| **PTZ / telemetry** | TelemetryService, TagAndTrackService | ⚠️ shipped, unstamped | 16 `ptz_*` tools shipped Phase 8; corpus still 0/32. TagAndTrack 0/4. |
| **Alarms / macros** | LogicService | ✅ strong | Full alarm lifecycle + `raise_alert` + macro workflows. |
| **Layouts / maps / videowalls** | LayoutManager, LayoutImagesManager, MapService, VideowallService | ✅ partial | Reads + operator workflows; VideowallService mutations 1/7, LayoutManager 1/5 stamped. |
| **Bookmarks** | BookmarkService | ✅ strong | reads + lifecycle; UpdateBookmark/SetExportedTime/RenderTrack open. |
| **Security / users / roles** | SecurityService, AuthenticationService, GroupManager | ✅ partial | 22/35 SecurityService; Authentication 2/12 (federated/TFA flows pending). |
| **System health / license / time** | LicenseService, TimeZoneManager, DomainSettingsService, ServerSettings, NgpNodeService | ✅ partial | `system_health`, `license_status`, `time_status`. License 6/11. |
| **Config tree / devices** | ConfigurationService, DomainService, DevicesCatalog, DiscoveryService, ConfigurationManager, DynamicParametersService | ✅ strong-ish | Inventory + config units + camera CRUD. DynamicParameters 0/2, Discovery 2/5. |
| **Archive storage / backup / cloud** | ArchiveVolumeService, BackupSourceService, CloudService, StateControlService | ❌ weak | `archive_policy_get` only; BackupSource 0/5, Cloud 0/4, StateControl 0/3, ArchiveVolume 0/1. |
| **Audit injection** | AuditEventInjector | ❌ none | 0/7 — no tool. |
| **External text/POS/ACS events** | TextEventSupportService, ExternalDetectorService | ❌ none | injection only via generated templates, no first-class tool. |
| **Notifier channels (email/SMS)** | EMailNotifier, GSMNotifier, GenericSettingsService | ❌ none | 0 tools — notification-action config absent. |
| **Global tracker / cross-camera** | GlobalTrackerService | ❌ weak | 1/7. |
| **Misc settings / KV / files** | SharedKVStorageService, FileSystemBrowser, InstallationPackageProvider | ✅/⚠️ | KV 4/4, FS 3/3; InstallationPackage 1/2. |

---

## B. Genuinely-missing capabilities (no MCP tool exists at all)

These have **zero** MCP surface — not stale evidence, actually absent:

1. **AuditEventInjector (0/7)** — programmatic audit-log writes; needed for compliance integrations.
2. **EMailNotifier / GSMNotifier (0/5)** — configure email/SMS notification actions. A desktop
   operator can wire "on alarm → send email"; the MCP cannot.
3. **TextEventSupportService / ExternalDetectorService first-class tools** — POS/ACS/text-event
   ingestion is only reachable through generated code templates, not a direct `raise_text_event` tool.
4. **BackupSourceService (0/5)** — archive backup source config.
5. **CloudService (0/4)** — cloud connection / Axxon Cloud pairing.
6. **StateControlService (0/3)** — arm/disarm state control of objects.
7. **GenericSettingsService (0/3)** — generic per-object settings get/set.
8. **DynamicParametersService (0/2)** — dynamic device parameter discovery (drives detector schemas).
9. **HeatMapService (0/6)** — heat-map analytics retrieval (only referenced in detector_archive).
10. **RealtimeRecognizerService (0/7)** — face/LPR realtime recognizer config + result streams.
11. **GlobalTrackerService (1/7)** — cross-camera tracking / Tag&Track topology.
12. **TagAndTrackService (0/4)** — PTZ auto-follow.

---

## C. Shipped-but-unstamped (reconcile, don't rebuild)

Re-run + re-stamp; the code already exists:

- **TelemetryService / PTZ** — `axxon_mcp_ptz.py`, 16 tools, Phase 8 live run on `DeviceIpint.53`.
- **DomainNotifier / NodeNotifier** — `domain_event_subscribe` / `node_event_subscribe` shipped.
- **MediaService** — exercised by `live_view` / metadata, raw RPCs unstamped.

---

## D. Recommended next moves (priority order)

1. **Reconcile the ledger.** Add an `axxon_corpus_restamp.py` pass that flips `live_status`
   for every method already covered by a passing smoke/MCP tool, so the corpus matches STATUS.md.
   This alone likely moves ~30-40 methods from `pending` → `tested-pass`.
2. **Close the true zero-coverage families** that have real operator value:
   notification actions (email/SMS), StateControl (arm/disarm), CloudService (pairing),
   RealtimeRecognizer (face/LPR), HeatMapService, AuditEventInjector.
3. **Promote external-event ingestion** (Text/ExternalDetector) from template-only to a
   first-class `raise_text_event` / `external_detector_push` tool pair.
4. **Then** declare the roadmap's "≤20 pending" definition-of-done met — with evidence, not narrative.
