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
| **Detectors / analytics config** | LogicService, ExternalDetectorService, RealtimeRecognizerService, AcfaService, HeatMapService, VMDAService, MetadataService | ⚠️ partial | Rich tooling for AV/AppData detectors; LogicService 15/29, RealtimeRecognizer 6/7, HeatMap 0/6 stamped. |
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
9. **HeatMapService (0/6)** — heat-map analytics. FIXTURE-BLOCKED: every Build* RPC
   (BuildHeatmap/BuildEventsHeatmap, all camera/db/detector bindings) returns "Failed to
   execute command". The service needs a heat-map analytics module/license not provisioned
   on this stand (same dead-fixture class as PTZ hardware / Cloud pairing).
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
    closeable only on real PTZ hardware.
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

Fixture finding: HeatMapService is dead on this stand (see B.9) — every Build* RPC returns
"Failed to execute command" regardless of binding (needs a heat-map analytics module).

---

## D. Recommended next moves (priority order)

1. ~~**Reconcile the ledger.**~~ DONE (pass 1, `a61d363`): `tools/axxon_corpus_restamp.py`
   flipped 14 evidence-cited methods and added the `evidence` field. Coverage 152 → 160 pass.
2. **Close the true zero-coverage families** that have real operator value:
   ~~AuditEventInjector~~ DONE (`0c16bb2`). Still open and live-exercisable here:
   Done: RealtimeRecognizer reads (`496bd70`), DiscoveryService (`c240043`).
   Fixture-blocked here: CloudService (not paired), HeatMapService (no analytics module).
   Fixture-blocked on this stand (defer until a richer stand): notification actions
   (email/SMS, need NotifyService), StateControl/ACFA arm-disarm (need real I/O device).
3. ~~**Promote external-event ingestion** (ExternalDetector)~~ DONE for periodical events
   (`dbaebbc`, ExternalDetectorService 2/2). Still open: a first-class `raise_text_event`
   for `TextEventSupportService` (POS/ACS text).
4. **Then** declare the roadmap's "≤20 pending" definition-of-done met — with evidence, not narrative.

Current honest coverage: **227 tested-pass / 107 pending / 27 fixture-warn** (361 total).
