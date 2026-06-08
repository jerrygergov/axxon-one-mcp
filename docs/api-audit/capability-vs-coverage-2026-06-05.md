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
| **Live + archive view** | MediaService, ArchiveService, ExportService, StatisticService | ✅ partial | `live_view`, `snapshot_batch`, `archive_scrub/frame/mjpeg`, `stream_health`. MediaService raw RPCs 4/6 stamped (phase-44 transport probes). |
| **Events / history** | EventHistoryService, EventDescription | ✅ strong | `search_events`, `subscribe_events_bounded`, `find_event_suppliers` — 13/13 stamped. |
| **Live notifications** | DomainNotifier, NodeNotifier | ⚠️ thin | `domain_event_subscribe`/`node_event_subscribe` exist but all 11 RPCs unstamped. |
| **Detectors / analytics config** | LogicService, ExternalDetectorService, RealtimeRecognizerService, AcfaService, HeatMapService, VMDAService, MetadataService | ⚠️ partial | Rich tooling for AV/AppData detectors; LogicService 15/29, RealtimeRecognizer 6/7, HeatMap 5/6 stamped (phase-44). |
| **PTZ / telemetry** | TelemetryService, TagAndTrackService | ✅ partial | `ptz_*` tools (incl. `ptz_point_move`); TelemetryService 22/32 stamped (10 device/firmware fixture-warn). TagAndTrack 0/4. |
| **Alarms / macros** | LogicService | ✅ strong | Full alarm lifecycle + `raise_alert` + macro workflows. |
| **Layouts / maps / videowalls** | LayoutManager, LayoutImagesManager, MapService, VideowallService | ✅ partial | Reads + operator workflows; VideowallService mutations 1/7, LayoutManager 5/5. |
| **Bookmarks** | BookmarkService | ✅ strong | reads + lifecycle; UpdateBookmark/SetExportedTime/RenderTrack open. |
| **Security / users / roles** | SecurityService, AuthenticationService, GroupManager | ✅ partial | 28/35 SecurityService (7 LDAP fixture-warn); Authentication 8/12 (4 TFA/approval/public-key fixture-warn). |
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

1. ~~**AuditEventInjector (0/7)**~~ CLOSED `0c16bb2` — `audit_inject` (6/7 live-verified, see C3).
2. **EMailNotifier / GSMNotifier (0/5)** — configure email/SMS notification actions. FIXTURE-BLOCKED
   on this stand: the reads error with "Can't resolve reference to /NotifyService" (no NotifyService
   configured). Needs a stand with email/SMS notification actions wired.
3. **TextEventSupportService** — POS/ACS/text-event ingestion has no direct
   `raise_text_event` tool yet. (`ExternalDetectorService` is now CLOSED — see below.)
4. **BackupSourceService (0/5)** — archive backup source config.
5. **CloudService (0/4)** — cloud pairing. FIXTURE-BLOCKED: `GetBindingConfiguration` returns
   `CloudClient/NotFound` (stand is not cloud-paired). Needs an Axxon Cloud account to exercise.
6. **StateControlService (0/3)** — arm/disarm state control. FIXTURE-BLOCKED on this stand: the only
   StateControl endpoints are relays on the virtual `DeviceIpint.53` (`StateControl.relay0:0/1`) and
   they fail with "Can't resolve reference" (the virtual device's relays aren't instantiated, same dead
   fixture as the PTZ presets). ACFA emulator objects expose 0 actions via `AcfaService.ListUnitsActions`.
   Needs a stand with a real I/O device (relay/ray) or an action-capable ACFA controller.
7. **GenericSettingsService (0/3)** — generic per-object settings get/set.
8. **DynamicParametersService (0/2)** — dynamic device parameter discovery (drives detector schemas).
9. **HeatMapService (5/6)** — heat-map analytics. CORRECTED 2026-06-08 (phase-44): the earlier
   "0/6 dead fixture" finding was a wrong-argument artifact. The INTERNAL "Failed to execute
   command" came from passing the detector access point as `camera_ID` and a bad builder AP. With
   the correct `camera_ID = hosts/Server/AVDetector.N/SourceEndpoint.vmda` and
   `access_point = hosts/Server/HeatMapBuilder.0/HeatMapBuilder`, BuildHeatmap / BuildEventsHeatmap
   / BuildFloorHeatmap all return result=True with image bytes, and ExecuteHeatmapQuery /
   ExecuteHeatmapQueryTyped stream responses with progress on AVDetector.1. Only BuildHeatmapTyped
   stays fixture-warn (DEADLINE_EXCEEDED >120s even at a 30-min window / 8x8 mask / DATA result —
   a server-side typed-query compile hang, distinct from the working string-query path). Shipped as
   `tools/axxon_mcp_heatmap.py` (`--enable-heatmap`).
10. **RealtimeRecognizerService (7/7 non-fixture)** — reads CLOSED `496bd70`
    (GetLists/GetListStream/GetItems); writes CLOSED phase-14 (ChangeLists/ChangeItems/Clear,
    approval-gated, live-verified incl. an authorized node wipe) and ChangeListsStream CLOSED
    phase-22 (see 10i). Only GetData stays fixture-warn (biometric, out of scope).
10b. **LogicService alerts (phase-15)** — alert lifecycle reconciled. Fixed a real shipped bug:
    `alarm_complete_review` sent invalid severity strings (confirmed_alarm/...) that the server
    500s on; now uses the valid `SV_*` ESeverity enum (proven SV_FALSE=200 vs false_alarm=500).
    RaiseAlert/GetActiveAlerts/Begin/Continue/CancelAlertReview live-exercised -> tested-pass.
    CompleteAlertReview/EscalateAlert stay fixture-warn: user-raised alerts only TTL-expire here,
    so full review-completion needs a rule-raised alert this stand cannot trigger.
10c. **LogicService control (phase-16)** — `launch_macro` + `change_arm_state` shipped behind
    `--enable-logic-control` (approval-gated). LaunchMacro ran a manual macro; ChangeArmState
    arms/disarms a camera for a bounded auto-reverting window (timeout required, capped 300s, so
    no permanent state change). Both live-verified -> tested-pass. LogicService now 15/29.
10d. **DomainSettings data-storage (phase-17)** — `get_data_storage_settings` +
    `update_data_storage_settings` shipped behind `--enable-settings` (update approval-gated).
    Update is field-masked and etag-managed (never a blind overwrite); live-verified by changing
    system-logs cleanup_period and restoring it (reversible). UpdateDataStorageSettings flipped
    pending -> tested-pass; DomainSettingsService now 6/8 (Export/GDPR/Bookmark still pending).
10e. **DomainSettings bookmark + GDPR (phase-18)** — `update_bookmark_settings` (live-verified by
    toggling mandatory_protection and restoring, reversible) -> tested-pass. `update_gdpr_settings`
    built + gated + reachable but a NO-OP on this stand (GDPR privacy-masking module not
    provisioned), so fixture-warn. DomainSettingsService now 7/8.
10f. **TimeZoneManager writes (phase-19)** — `set_timezone`, `set_ntp`, `change_timezones`
    shipped behind `--enable-timezone` (`AXXON_TIMEZONE_APPROVE=1` + `CONFIRM-timezone-set`).
    All three live round-tripped reversibly (TZ -> UTC then restored; NTP empty -> set ->
    cleared; add throwaway zone -> remove). All -> tested-pass; TimeZoneManager now 7/7.
10g. **ServerSettings writes (phase-20)** — `set_log_level`, `drop_logs` shipped behind
    `--enable-server` (`AXXON_SERVER_APPROVE=1` + `CONFIRM-server-set`). SetLogLevel live
    round-tripped reversibly (INFO -> DEBUG -> restored); DropLogs authorized irreversible
    (server healthy after). Both -> tested-pass; ServerSettings now 3/3.
10h. **GroupManager writes (phase-21)** — `change_groups`, `set_objects_membership`
    shipped behind `--enable-groups` (`AXXON_GROUPS_APPROVE=1` + `CONFIRM-groups-set`).
    Both live round-tripped reversibly (add throwaway group -> remove; add object
    membership -> remove). Both -> tested-pass; GroupManager now 4/4.
10i. **RealtimeRecognizer ChangeListsStream (phase-22)** — `recognizer_change_lists_stream`
    added to the existing gated write module (`--enable-recognizer-write`). The
    proto-preferred bidirectional streaming replacement for the deprecated unary
    ChangeLists; live round-tripped reversibly (stream-add throwaway LPR list ->
    stream-remove). -> tested-pass; all 7 non-fixture recognizer methods now pass
    (only GetData stays fixture-warn, biometric, out of scope).
10j. **DiscoveryService DiscoverNode (phase-23)** — `discover_node_devices` added to the
    existing read-only discovery module (`--enable-discovery`). Node-scoped twin of
    Discover; live-verified read-only (started a scan on node "Server", found devices via
    GetNodeDiscoveryProgress). Shares the progress-drain helper with discover_devices and
    tolerates a slow-stream DEADLINE_EXCEEDED (`progress_timed_out`). -> tested-pass; all 4
    non-fixture DiscoveryService methods now pass (only Probe stays fixture-warn).
10k. **LayoutImagesManager DownloadLayoutImage (phase-24)** — `download_layout_image`
    added to the view-objects module (read), with a `download_layout_image_grpc` client
    helper for the server-streaming chunk download (the HTTP /grpc bridge 500s here).
    Live round-tripped (uploaded a 1x1 PNG fixture, downloaded it via the streaming RPC,
    bytes matched, removed). Returns metadata only (etag/size/chunks, no raw bytes), like
    get_map_image. -> tested-pass; LayoutImagesManager now 4/4.
10l. **UpdateSubscription (phase-25)** — `update_event_subscription` added to the admin
    notifier layer, backed by `update_subscription_bounded`. UpdateSubscription only targets
    a live PullEvents stream, so the self-contained tool opens a short-lived subscription on a
    background thread, applies UpdateSubscription with new filters (Bookmark -> Alert), then
    disconnects. Live-verified for BOTH DomainNotifier and NodeNotifier (same helper via the
    notifier param). Both -> tested-pass (only PushDiagnosticEvents / NodeNotifier.Ping remain).
10m. **DomainService batch reads (phase-26)** — `get_cameras_by_components`,
    `batch_get_archives`, `search_maps` added to the view module (read-only batch lookups by
    ResourceLocator access point), backed by a shared `_domain_batch_read` client helper.
    Live-verified with real camera/archive access points (each returned its entity). All three
    -> tested-pass; DomainService now 21/21 (complete). AcfaService PerformAction/DownloadData
    were probed and rejected first (no configured ACFA units on the stand; PerformAction is a
    non-reversible physical action).
10n. **VMDAService ExecuteQueryTyped (phase-27)** — `vmda_query` switched from the deprecated
    ExecuteQuery (MomentQuest query string) to the non-deprecated ExecuteQueryTyped with a typed
    `QueryDescription(motion_in_area=MotionInArea(area=Polyline))`, fixing a real code/docstring
    mismatch. Live-verified read-only against a real VMDA database + source. -> tested-pass;
    VMDAService now 3/4 (only the destructive Cleanup stays pending).
10o. **ConfigurationManager CollectBackup (phase-28)** — `collect_config_backup` added to the
    admin layer; drains the CollectBackup config-export stream and returns size/chunk metadata
    only (raw backup bytes never surfaced). Read-only (the inverse of RestoreBackup), the safe
    member of the backup/restore cluster. Live-verified LOCAL export (28 chunks / 1.82 MB);
    unknown type / empty node -> gap with no wire call. -> tested-pass.
10p. **TelemetryService Zoom (phase-29)** — the existing `zoom` ptz tool live-verified reversibly
    on DeviceIpint.53/TelemetryControl.0: capture position -> Zoom(absolute,0.4)=ok -> AbsoluteMove
    restore to the captured pan/tilt/zoom -> exact match. continuous mode is rejected (error 2) by
    this simulated source; absolute is the supported mode. -> tested-pass (no new tool; restamp +
    focused regression test).
10q. **GDPR user-data cleanup (phase-30)** — new gated module `axxon_mcp_gdpr_cleanup.py` with
    `layout_user_data_cleanup` / `map_user_data_cleanup` (LayoutManager + MapService UserDataCleanup),
    approval-gated (AXXON_GDPR_APPROVE=1 + CONFIRM-gdpr-cleanup). Live-verified with a throwaway,
    nonexistent user id -> status applied, nothing real deleted; gate matrix (disabled/gap/error)
    holds with no wire call. Both -> tested-pass.
10r. **ACFA PerformAction + VMDA Cleanup (phase-31)** — new gated module
    `axxon_mcp_acfa_vmda_control.py` (AXXON_CONTROL_APPROVE=1 + CONFIRM-control-action) with read
    `list_unit_actions` plus gated `perform_unit_action` and `vmda_cleanup`. AcfaService.PerformAction
    live-verified reversibly on the ACFA emulator loop: capture DISARM -> ARM (applied) -> DISARM
    restore -> original state. VMDAService.Cleanup live-verified on a camera with 0 analytics intervals
    (verified empty first) -> result=True, nothing real deleted. Both -> tested-pass; VMDAService now
    4/4 complete, AcfaService 6/7 (only DownloadData pending).
10s. **ACFA DownloadData (phase-32)** — extended the control module with read tools
    `list_unit_visualizations` (surfaces icon image data_ids) and `download_unit_data` (drains
    AcfaService.DownloadData, returns size metadata only, never the raw blob). Live-verified on the
    emulator lock: 2 icon images, 344 bytes each; error matrix (empty uid/ids) holds with no wire
    call. -> tested-pass; AcfaService now 7/7 COMPLETE.
10t. **TelemetryService device-supported full (phase-33)** — added ptz tools
    `get_position_normalized`, `absolute_move_normalized`, `save_preset` (bare SetPreset),
    `configure_preset`, `get_tours`, `get_tour_points`; live-verified reversibly on
    DeviceIpint.53/TelemetryControl.0 (presets created+removed, position restored, session released).
    14 methods -> tested-pass (KeepAlive, ReleaseSessionId, Move, GetPositionInformationNormalized,
    AbsoluteMoveNormalized, GetPresetsInfo, SetPreset, SetPreset2, GoPreset, RemovePreset,
    ConfigurePreset, GetTours, GetTourPoints, GetAuxiliaryOperations); TelemetryService now 19/32.
    The 13 unsupported by the simulated source (Focus/FocusAuto/Iris/IrisAuto/PointMove/AreaZoom/
    PerformAuxiliaryOperation + tour writes) stay pending: rejected with error 2 / GeneralError,
    closeable only on real PTZ hardware. [Superseded by phase-44 (item 10ae): Focus/Iris service
    OK on TelemetryControl.0 and PointMove on TelemetryControl.2; only the other 10 are genuinely
    device/firmware-walled. TelemetryService is now 22/32.]
10u. **MapService providers complete (phase-34)** - new gated module `axxon_mcp_map_providers.py`
    (AXXON_MAP_APPROVE=1 + CONFIRM-map-providers) with gated `configure_map_providers`
    (ConfigureMapProviders) and read `get_map_provider` (GetMapProvider). Live-verified reversibly:
    create a throwaway provider -> get -> remove -> NOT_FOUND. The tool normalizes provider ids to
    uppercase (the server stores them uppercase and Get/remove are case-sensitive). Both -> tested-pass;
    MapService now 11/11 COMPLETE.
10v. **LogicService batch alerts (phase-35)** - new module `axxon_mcp_logic_alerts.py` with read
    `batch_get_active_alerts` / `batch_filter_active_alerts` and gated batch reviews
    (AXXON_LOGIC_ALERTS_APPROVE=1 + CONFIRM-batch-alerts): begin/continue/cancel/escalate. These are
    node+filter-scoped, so they run as a clean no-op against 0 active alerts. Live-verified on node
    Server (unreachable_nodes empty). 6 -> tested-pass; LogicService now 21/29. BatchCompleteAlertsReview
    is left fixture-warn (reports unreachable_nodes=['Server'] - cannot complete with no reviewable
    alert, same wall as the single CompleteAlertReview); counter ops stay fixture-walled (no counter
    configured on the stand).
11. **GlobalTrackerService (1/7)** — cross-camera tracking / Tag&Track topology.
12. **TagAndTrackService (0/4)** — PTZ auto-follow.

---

## C. Shipped-but-unstamped (reconcile, don't rebuild)

Re-run + re-stamp; the code already exists:

- **TelemetryService / PTZ** — `axxon_mcp_ptz.py`, 16 tools, Phase 8 live run on `DeviceIpint.53`.
- ~~**DomainNotifier / NodeNotifier**~~ RECONCILED `bc27e3e` — `domain_event_subscribe` /
  `node_event_subscribe` exercise PullEvents/PullDetailedEvents/DisconnectEventChannel.
  UpdateSubscription CLOSED phase-25 (both notifiers, see 10l). Only
  PushDiagnosticEvents (both) and NodeNotifier.Ping stay pending.
- **MediaService** — exercised by `live_view` / metadata, raw RPCs unstamped.

---

## C2. Build pass 1 — ExternalDetectorService closed (2026-06-05, `dbaebbc`)

`raise_periodical_event` operator workflow added (`tools/axxon_mcp_operator.py`):
pushes a `PeriodicalEventData.TargetList` of tracklets via
`POST /v1/detectors/external:raisePeriodicalEvent`. ExternalDetectorService moved
**0/2 → 2/2** (both `RaiseOccasionalEvent` and `RaisePeriodicalEvent` now tested-pass).

Live verification surfaced a real latent bug: the external-detector endpoints return
**HTTP 200 even on rejection**, with the real outcome in the body
`{"error": "OK" | "BAD_EVENT_TYPE" | ...}`. The operator `http_post` apply handler
only checked `status >= 400`, so it would have reported a rejected event as
`applied`. Fixed: the handler now treats a non-`OK` body error as an apply failure,
which also hardens the pre-existing `external_event_inject`. The accepted periodical
event type on this stand is `TargetList` (vs `Event1` for occasional events).

---

## C3. Build pass 2 — AuditEventInjector closed (2026-06-05, `0c16bb2`)

`tools/axxon_mcp_audit.py` (`--enable-audit`) adds `audit_inject` for audit-trail
writes: camera/ptz/archive viewing, journal export, client-app option, LDAP setup.
AuditEventInjector moved **0/7 → 6/7** (all 6 supported kinds live-verified;
`InjectMMExportEvent` stays fixture-warn, needs a live MM export job). Write-only and
irreversible, so it is approval-gated (`AXXON_AUDIT_INJECT_APPROVE=1` +
`CONFIRM-audit-inject`) rather than plan/apply/verify/rollback.

Fixture findings this pass (recorded so they aren't re-probed): StateControlService
and ACFA actions are dead on this stand (see B.6); EMail/GSM notifiers need a
`NotifyService` (see B.2).

---

## C4. Build pass 3 — RealtimeRecognizer reads closed (2026-06-05, `496bd70`)

`tools/axxon_mcp_recognizer.py` (`--enable-recognizer`, read-only) adds
`list_recognizer_lists` / `get_recognizer_list` / `list_recognizer_items` for face/LPR
watchlist inspection. The three read RPCs (GetLists/GetListStream/GetItems) moved
`fixture-warn → tested-pass` against the stand's real "Intersec Face List" (6 enrolled
faces). Privacy-first: items load metadata only, never face images or biometric vectors;
committed evidence redacts enrolled-person names. Mutations stay out of scope (bidi-stream).

Fixture finding: CloudService is not cloud-paired here (see B.5).

---

## C5. Build pass 4 — DiscoveryService device discovery (2026-06-05, `c240043`)

`tools/axxon_mcp_discovery.py` (`--enable-discovery`, read-only) adds `discover_devices`:
starts a network scan (`Discover`) and consumes the `GetDiscoveryProgress` stream,
returning found IP cameras (driver/vendor/model/mac/ip), bounded by device/time caps with
the stream cancelled on exit. Live-verified: found 3 real cameras (Hikvision/Dahua) on the
stand's LAN. `Discover` flipped `pending → tested-pass`; DiscoveryService now 4/5.

Correction (phase-44, 2026-06-08): the earlier "HeatMapService is dead on this stand" finding was
a wrong-argument artifact, not a fixture wall — with the correct VMDA `camera_ID` + HeatMapBuilder
access point, 5/6 HeatMap RPCs return real results (see B.9).

---

## D. Recommended next moves (priority order)

1. ~~**Reconcile the ledger.**~~ DONE (pass 1, `a61d363`): `tools/axxon_corpus_restamp.py`
   flipped 14 evidence-cited methods and added the `evidence` field. Coverage 152 → 160 pass.
2. **Close the true zero-coverage families** that have real operator value:
   ~~AuditEventInjector~~ DONE (`0c16bb2`). Still open and live-exercisable here:
   Done: RealtimeRecognizer reads (`496bd70`), DiscoveryService (`c240043`).
   Fixture-blocked here: CloudService (not paired). HeatMapService now 5/6 (phase-44, was
   mis-flagged as a dead fixture).
   Fixture-blocked on this stand (defer until a richer stand): notification actions
   (email/SMS, need NotifyService), StateControl/ACFA arm-disarm (need real I/O device).
3. ~~**Promote external-event ingestion** (ExternalDetector)~~ DONE for periodical events
   (`dbaebbc`, ExternalDetectorService 2/2). Still open: a first-class `raise_text_event`
   for `TextEventSupportService` (POS/ACS text).
4. **Then** declare the roadmap's "≤20 pending" definition-of-done met — with evidence, not narrative.

Current honest coverage: **275 tested-pass / 36 pending / 50 fixture-warn** (361 total).

### Item 10ae (Phase 44): Telemetry + HeatMap + Media physical/hardware batch -> +12 tested-pass

Closed the three "physical/hardware" clusters by live-probing what the demo stand actually
services. TelemetryService Focus/Iris (Empty OK on TelemetryControl.0) and PointMove (OK on
TelemetryControl.2) added to `tools/axxon_mcp_ptz.py` (`ptz_point_move`); TelemetryService is now
22/32 with the remaining 10 honestly fixture-warn (FocusAuto/IrisAuto UNIMPLEMENTED, AreaZoom
INTERNAL error 2, PerformAuxiliaryOperation has no aux ops, and 6 tour ops return GeneralError —
firmware does not support on-device tours). New read-only `tools/axxon_mcp_heatmap.py`
(`--enable-heatmap`) ships build_heatmap / build_events_heatmap / build_floor_heatmap (result=True
with image bytes) and execute_heatmap_query / execute_heatmap_query_typed (streamed responses with
progress); HeatMapService 5/6 (BuildHeatmapTyped fixture-warn, server-side compile hang). New
read-only `tools/axxon_mcp_media.py` (`--enable-media`) ships request_connection / request_qos /
request_tunnel / stream_probe (MediaService 4/6; AwaitConnection and ConnectEndpoint need a
peer/speaker sink). All tools are metadata-only — never returning raw image bytes, media samples,
cookies, or tokens. Also corrected the stale B.9 "HeatMapService is a dead fixture" claim, which
was a wrong-argument artifact (detector AP passed as camera_ID), not a provisioning wall.

### Item 10w (Phase 36): ConfigurationService unit changes

`tools/axxon_mcp_config_change.py` (gated, `AXXON_CONFIG_CHANGE_APPROVE=1`,
`--enable-config-change`). Live-verified on the demo stand:
- **ChangeConfig** and **ChangeConfigStream** — reversible single-property change on
  `hosts/Server/DeviceIpint.1` `display_name` (Tracker -> probe -> Tracker), failed=0
  both directions. tested-pass.
- **ListSimilarUnits** — valid paginated response (next_page_token). tested-pass.
- **BatchGetFactories** — RPC reachable but returns `NOT_FOUND` for every unit_type /
  parent_uid on this build; factory metadata is instead exposed via ListUnits
  `display_mode=VM_WITH_FACTORY` (already pass). Left tested-warn-fixture-needed, honest.

ConfigurationService now 11/12 (only BatchGetFactories outstanding, environment-walled).

### Item 10x (Phase 37): ArchiveService volume resize

`tools/axxon_mcp_archive_volume.py` (gated, `AXXON_ARCHIVE_VOLUME_APPROVE=1`,
`--enable-archive-volume`). Live-verified on the demo stand:
- **Resize** — `list_volume_states` on standalone storage
  `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage` returns one MOUNTED volume
  (capacity 107374182400); resizing to that same capacity returns EStatusCode `DONE` and
  leaves capacity unchanged (reversible no-op). tested-pass.
- **ChangeBookmarks** — server returns UNIMPLEMENTED "ChangeBookmarks deprecated"; the
  live replacement is BookmarkService.CreateBookmark (already pass). fixture-warn.
- **CreateReaderEndpoint / Seek / ClearInterval** — CORBA INTERNAL on every source/storage
  AP form; the reader and recorded-source subsystem is not serviceable for the virtual
  sources on this stand. fixture-warn (honest, not faked).

ArchiveService now 13/17 (Resize closed; the reader chain + ClearInterval are
environment-walled, ChangeBookmarks is deprecated server-side).

Coverage after Phase 37: **239 tested-pass / 91 pending / 31 fixture-warn** (361 total).

### Item 10y (Phase 38): BookmarkService extras -> 7/7

`tools/axxon_mcp_bookmark_extras.py` (gated, `AXXON_BOOKMARK_EXTRAS_APPROVE=1`,
`--enable-bookmark-extras`). Live-verified on the demo stand via a reversible
Create -> Update -> SetExportedTime -> RenderTrack -> Delete round-trip on a throwaway
bookmark (DeviceIpint.1):
- **UpdateBookmark** — message updated, confirmed via GetBookmark. tested-pass.
- **SetExportedTime** — exported_time set, confirmed via GetBookmark HasField. tested-pass.
- **RenderTrack** — returned a bookmark for the fixture. tested-pass.
The throwaway bookmark was deleted (GetBookmark afterward errors = gone), no residual state.

BookmarkService now **7/7 complete**.

Coverage after Phase 38: **242 tested-pass / 90 pending / 29 fixture-warn** (361 total).

### Item 10z (Phase 39): SecurityService credentials -> 28/35

`tools/axxon_mcp_security_credentials.py` (gated, `AXXON_SECURITY_CREDENTIALS_APPROVE=1`,
`--enable-security-credentials`). Live-verified on the demo stand:
- **CheckPassword** — read-only uniqueness/policy pre-check (NOT an auth check): the current
  password returns NOT_UNIQUE, an unused password returns OK. tested-pass.
- **ChangePassword / ChangeLogin** — act on the connected session's own user. Verified -> OK
  each on a SEPARATE throwaway admin user (created via ChangeConfig with an admin role
  assignment, then removed; ListUsers confirms gone). The shared root account is never
  touched. Separate users are used because the module re-authenticates per call.
- **LDAP cluster** (TestLDAPConnection, Start/StopLDAPSynchronization, SearchLDAP,
  SearchLDAP2, SearchLDAPGroups, GetLDAPSynchronizationState) — no LDAP server on this stand
  (GetLDAPSynchronizationState returns UNAVAILABLE). All 7 restamped tested-warn-fixture-needed
  (5 were previously still `pending`), honest.

SecurityService now 28/35 (28 tested-pass + 7 LDAP fixture-warn, environment-walled).

Coverage after Phase 39: **245 tested-pass / 82 pending / 34 fixture-warn** (361 total).

### Item 10aa (Phase 40): AuthenticationService sessions -> 8/12

`tools/axxon_mcp_auth_sessions.py` (gated close, `AXXON_AUTH_SESSIONS_APPROVE=1`,
`--enable-auth-sessions`). Tools never return raw token values (token_present boolean only).
Live-verified on the demo stand:
- **Authenticate / Authenticate2 / AuthenticateEx** — each mints a valid token
  (expires_in 300). tested-pass.
- **RenewSession / RenewSession2** — error_code 0 with a fresh token on the authenticated
  channel. tested-pass.
- **CloseSession** — OK (0) on a SEPARATE throwaway session; the main session stays usable.
  tested-pass.
- **ApproveAuthentication / DeclineAuthentication / AuthenticateBySecondFactor /
  AuthenticateWithPublicKey** — need supervisor-approval / TFA / public-key flows not
  configured on this stand. fixture-warn, honest.

AuthenticationService now 8/12 (4 remaining are TFA/approval/public-key, environment-walled);
no pending rows left.

Coverage after Phase 40: **251 tested-pass / 72 pending / 38 fixture-warn** (361 total).

### Item 10ab (Phase 41): LayoutManager -> 5/5

`tools/axxon_mcp_layout_manager.py` (gated rename, `AXXON_LAYOUT_MANAGER_APPROVE=1`,
`--enable-layout-manager`). Live-verified on the demo stand:
- **BatchGetLayouts** — etag-conditional read: empty/stale etag returns the layout body,
  matching etag returns nothing, bogus id returns not_found. tested-pass.
- **LayoutsOnView** — pushes a layout to the view, OK. tested-pass.
- **Update** — reversible display_name rename on a writable layout (Fire -> probe -> Fire),
  using the live etag. tested-pass.

LayoutManager now **5/5 complete**.

Coverage after Phase 41: **254 tested-pass / 69 pending / 38 fixture-warn** (361 total).

### Item 10ac (Phase 42): LicenseService reads -> 8/11

`tools/axxon_mcp_license_reads.py` (read-only, `--enable-license-reads`, no gate).
Live-verified on the demo stand:
- **LicenseKey** — returns the current license key; the tool reports key_present True and
  key_length 50992 only, never the raw key (metadata-only surface). tested-pass.
- **Restrictions** — deprecated proto but still serviceable; returns restrictions +
  available_restrictions. tested-pass.
- **DistributeLicenseKey / DropLicenseKey / CreateLicenseDocument** — license mutations that
  would change the stand's licensing state; out of scope on a shared stand, left pending.

LicenseService now 8/11.

Coverage after Phase 42: **256 tested-pass / 67 pending / 38 fixture-warn** (361 total).

### Item 10ad (Phase 43): cross-service batch (4 services)

`tools/axxon_mcp_misc_reads.py` (gated settings writes, `AXXON_MISC_WRITE_APPROVE=1`,
`--enable-misc-reads`). Live-verified on the demo stand:
- **DynamicParametersService** — AcquireDynamicParameters + AcquireDeviceAdditionalData
  return status DONE on DeviceIpint.1. **2/2 complete.**
- **ArchiveVolumeService** — ProbeVolume returns a structured NOT_A_VOLUME result.
  **1/1 complete.**
- **GenericSettingsService** — GetSettings/SaveSettings/RemoveSettings verified via a
  reversible round-trip on a throwaway GUID context (saved -> read back -> removed ->
  NOT_FOUND). **3/3 complete.**
- **NodeNotifier.Ping** — stream returned >=1 response. NodeNotifier now 5/6
  (PushDiagnosticEvents remains).

Coverage after Phase 43: **263 tested-pass / 61 pending / 37 fixture-warn** (361 total).
