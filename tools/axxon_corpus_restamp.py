"""Reconcile api_methods.json live_status with shipped, live-verified evidence.

The corpus live_status field was frozen 2026-05-29 and never re-stamped after
Phases 5H/6/7/8 (2026-06-04/05), so it underreports coverage for work that did
ship and was live-verified. This pass flips only the methods backed by explicit
live-pass evidence (cited per method) and records that citation in a new
`evidence` field so the ledger cannot silently drift again.

It is deliberately conservative: methods whose code shipped but whose live run
was rejected by the stand's driver/emulator (PTZ continuous Move/Zoom/GoPreset/
Release) stay fixture-needed, not pass.

Run: python3.12 tools/axxon_corpus_restamp.py [--write]
Without --write it prints the diff and exits without touching the file.
"""

import argparse
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "docs/api-audit/mcp-corpus/api_methods.json"

# Evidence-backed restamps. Each entry: (service, method) -> (new_status, evidence).
# Only methods with an explicit live-pass record are promoted to tested-pass.
# Driver/emulator-rejected PTZ verbs are noted but kept fixture-needed.
RESTAMP = {
    # Phase 42 LicenseService reads. LicenseKey returns the current key (verified metadata-only:
    # key_present True, key_length 50992; the raw key is never returned). Restrictions
    # (deprecated proto, still serviceable) returns restrictions + available_restrictions. The
    # three license-mutation methods (DistributeLicenseKey, DropLicenseKey,
    # CreateLicenseDocument) are out of scope on a shared stand and left pending.
    ("LicenseService", "LicenseKey"): (
        "tested-pass", ".agent/tasks/phase-42-license-reads/evidence.md AC4 (key_present True, key_length 50992, value never returned)"),
    ("LicenseService", "Restrictions"): (
        "tested-pass", ".agent/tasks/phase-42-license-reads/evidence.md AC4 (restrictions + available_restrictions present)"),
    # Phase 41 LayoutManager. BatchGetLayouts is an etag-conditional read (empty/stale etag
    # returns the body, matching etag returns nothing, bogus id returns not_found);
    # LayoutsOnView pushes a layout to the view (OK); Update renames a layout reversibly
    # (display_name -> probe -> restored via the live etag). Closes LayoutManager 5/5.
    ("LayoutManager", "BatchGetLayouts"): (
        "tested-pass", ".agent/tasks/phase-41-layout-manager/evidence.md AC4 (etag-conditional read; body + not_found verified)"),
    ("LayoutManager", "LayoutsOnView"): (
        "tested-pass", ".agent/tasks/phase-41-layout-manager/evidence.md AC4 (pushed a layout to the view, OK)"),
    ("LayoutManager", "Update"): (
        "tested-pass", ".agent/tasks/phase-41-layout-manager/evidence.md AC4 (reversible display_name rename)"),
    # Phase 40 AuthenticationService sessions. Authenticate/Authenticate2/AuthenticateEx each
    # mint a valid token (expires_in 300); RenewSession/RenewSession2 each return error_code 0
    # with a fresh token on the authenticated channel; CloseSession returns OK (0) on a
    # SEPARATE throwaway session (the main session stays usable). The four TFA/public-key
    # methods need flows not configured on this stand -> stay fixture-warn.
    ("AuthenticationService", "Authenticate"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (minted a valid token)"),
    ("AuthenticationService", "Authenticate2"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (minted a valid token)"),
    ("AuthenticationService", "AuthenticateEx"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (minted a valid token)"),
    ("AuthenticationService", "RenewSession"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (error_code 0, fresh token)"),
    ("AuthenticationService", "RenewSession2"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (error_code 0, fresh token)"),
    ("AuthenticationService", "CloseSession"): (
        "tested-pass", ".agent/tasks/phase-40-auth-sessions/evidence.md AC4 (OK on throwaway session, main session unaffected)"),
    ("AuthenticationService", "ApproveAuthentication"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-40-auth-sessions/evidence.md AC5 (needs a supervisor-approval flow not configured on this stand)"),
    ("AuthenticationService", "DeclineAuthentication"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-40-auth-sessions/evidence.md AC5 (needs a supervisor-approval flow not configured on this stand)"),
    ("AuthenticationService", "AuthenticateBySecondFactor"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-40-auth-sessions/evidence.md AC5 (needs TFA enabled on the account)"),
    ("AuthenticationService", "AuthenticateWithPublicKey"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-40-auth-sessions/evidence.md AC5 (needs a registered public-key credential)"),
    # Phase 39 SecurityService credentials. CheckPassword is a read-only uniqueness/policy
    # pre-check (current pw -> NOT_UNIQUE, unused pw -> OK). ChangePassword and ChangeLogin
    # act on the authenticated session's own user; verified -> OK each on a SEPARATE
    # throwaway admin user (created via ChangeConfig with an admin role assignment, then
    # removed; ListUsers confirms gone). The shared root account is never touched. The six
    # LDAP methods stay fixture-warn: no LDAP server on this stand (GetLDAPSynchronizationState
    # returns UNAVAILABLE).
    ("SecurityService", "CheckPassword"): (
        "tested-pass", ".agent/tasks/phase-39-security-credentials/evidence.md AC4 (uniqueness pre-check: current pw NOT_UNIQUE, unused pw OK)"),
    ("SecurityService", "ChangePassword"): (
        "tested-pass", ".agent/tasks/phase-39-security-credentials/evidence.md AC4 (OK on throwaway admin user, then user removed)"),
    ("SecurityService", "ChangeLogin"): (
        "tested-pass", ".agent/tasks/phase-39-security-credentials/evidence.md AC4 (OK on throwaway admin user, then user removed)"),
    # LDAP cluster: probed live, GetLDAPSynchronizationState returns UNAVAILABLE ("Can't get
    # connection channel") -> no LDAP server on this stand. All seven stay fixture-warn.
    ("SecurityService", "TestLDAPConnection"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-39-security-credentials/evidence.md AC5 (no LDAP server on this stand; GetLDAPSynchronizationState returns UNAVAILABLE)"),
    ("SecurityService", "StartLDAPSynchronization"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-39-security-credentials/evidence.md AC5 (no LDAP server on this stand)"),
    ("SecurityService", "StopLDAPSynchronization"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-39-security-credentials/evidence.md AC5 (no LDAP server on this stand)"),
    ("SecurityService", "SearchLDAP2"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-39-security-credentials/evidence.md AC5 (no LDAP server on this stand)"),
    ("SecurityService", "SearchLDAPGroups"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-39-security-credentials/evidence.md AC5 (no LDAP server on this stand)"),
    # Phase 38 BookmarkService: reversible Create -> Update -> SetExportedTime ->
    # RenderTrack -> Delete round-trip on camera DeviceIpint.1. The throwaway bookmark was
    # created, the three target methods exercised (message updated, exported_time set and
    # confirmed via GetBookmark, track rendered), then deleted (GetBookmark afterward
    # errors = gone). Closes BookmarkService 7/7.
    ("BookmarkService", "UpdateBookmark"): (
        "tested-pass", ".agent/tasks/phase-38-bookmark-extras/evidence.md AC4 (message updated on throwaway bookmark, then deleted)"),
    ("BookmarkService", "SetExportedTime"): (
        "tested-pass", ".agent/tasks/phase-38-bookmark-extras/evidence.md AC4 (exported_time set, confirmed via GetBookmark)"),
    ("BookmarkService", "RenderTrack"): (
        "tested-pass", ".agent/tasks/phase-38-bookmark-extras/evidence.md AC4 (RenderTrack returned a bookmark for the throwaway fixture)"),
    # Phase 37 ArchiveService: Resize live-verified on standalone storage
    # hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage volume 4b025154-... by
    # resizing to its current capacity (107374182400) -> EStatusCode DONE, capacity
    # unchanged (reversible no-op). The other four pending methods are not serviceable
    # on this stand: ChangeBookmarks returns UNIMPLEMENTED "deprecated";
    # CreateReaderEndpoint/Seek/ClearInterval throw CORBA INTERNAL (reader + recorded-
    # source subsystem unavailable) -> all stay fixture-warn with honest citations.
    ("ArchiveService", "Resize"): (
        "tested-pass", ".agent/tasks/phase-37-archive-volume/evidence.md AC4 (resize to current capacity -> DONE, reversible no-op)"),
    ("ArchiveService", "ChangeBookmarks"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-37-archive-volume/evidence.md AC5 (server returns UNIMPLEMENTED 'ChangeBookmarks deprecated'; use BookmarkService.CreateBookmark)"),
    ("ArchiveService", "CreateReaderEndpoint"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-37-archive-volume/evidence.md AC5 (CORBA INTERNAL on every source AP; reader subsystem unavailable on this stand)"),
    ("ArchiveService", "Seek"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-37-archive-volume/evidence.md AC5 (needs a reader endpoint that cannot be created on this stand)"),
    ("ArchiveService", "ClearInterval"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-37-archive-volume/evidence.md AC5 (CORBA INTERNAL on every resolvable source/storage AP form)"),
    # Phase 36 ConfigurationService: reversible single-property unit change on
    # hosts/Server/DeviceIpint.1 display_name (Tracker -> probe -> Tracker), failed=0
    # both directions for both ChangeConfig and ChangeConfigStream. ListSimilarUnits
    # returns a valid paginated response. BatchGetFactories is reachable but returns
    # NOT_FOUND for every unit_type/parent on this build -> stays fixture-warn.
    ("ConfigurationService", "ChangeConfig"): (
        "tested-pass", ".agent/tasks/phase-36-config-change/evidence.md AC4 (reversible display_name round-trip)"),
    ("ConfigurationService", "ChangeConfigStream"): (
        "tested-pass", ".agent/tasks/phase-36-config-change/evidence.md AC4 (reversible streamed display_name round-trip)"),
    ("ConfigurationService", "ListSimilarUnits"): (
        "tested-pass", ".agent/tasks/phase-36-config-change/evidence.md AC4 (valid paginated similar-units response)"),
    ("ConfigurationService", "BatchGetFactories"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-36-config-change/evidence.md AC5 (RPC reachable, NOT_FOUND on every factory type on this build)"),
    # Phase 8 PTZ live run on DeviceIpint.53: acquire -> read pos -> AbsoluteMove
    # -> restore. These four round-tripped against the stand.
    ("TelemetryService", "AcquireSessionId"): (
        "tested-pass", ".agent/tasks/phase-8-finish-all/evidence.md AC4 (live session acquire)"),
    ("TelemetryService", "IsSessionAvailable"): (
        "tested-pass", ".agent/tasks/phase-8-finish-all/evidence.md AC4 (session availability checked live)"),
    ("TelemetryService", "GetPositionInformation"): (
        "tested-pass", ".agent/tasks/phase-8-finish-all/evidence.md AC4 (read pan 675/tilt 279 live)"),
    ("TelemetryService", "AbsoluteMove"): (
        "tested-pass", ".agent/tasks/phase-8-finish-all/evidence.md AC4 (moved pan 675->120, restored)"),
    # Shipped + unit-tested but the emulator driver rejects these with "error: 1";
    # they stay fixture-needed (need a hardware PTZ camera), now with a citation.
    ("TelemetryService", "Move"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC4 (tool ships; emulator rejects continuous mode, needs hardware PTZ)"),
    ("TelemetryService", "GoPreset"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC4 (tool ships; emulator rejects, needs hardware PTZ)"),
    ("TelemetryService", "ReleaseSessionId"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC4 (tool ships; emulator rejects, needs hardware PTZ)"),
    ("TelemetryService", "KeepAlive"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC4 (tool ships; not exercised on emulator, needs hardware PTZ)"),
    ("TelemetryService", "SetPreset2"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC1 (tool ships; preset writes need hardware PTZ)"),
    ("TelemetryService", "RemovePreset"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-8-finish-all/evidence.md AC1 (tool ships; preset writes need hardware PTZ)"),
    # Phase 5H VMDA fix: ExecuteQuery (MomentQuest) live-verified against real
    # archived objects on camera 1 (3931 intervals on day-5).
    ("VMDAService", "ExecuteQuery"): (
        "tested-pass", ".agent/tasks/phase-5h-vmda-fix/evidence.md (live MomentQuest, real archived objects)"),
    # Phase 5F-B1 TFA lifecycle PASS exercises the Google-auth TOTP trio.
    ("SecurityService", "GenGoogleAuthSecret"): (
        "tested-pass", "docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md (security_tfa_temp_user_lifecycle PASS)"),
    ("SecurityService", "EnableGoogleAuth"): (
        "tested-pass", "docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md (security_tfa_temp_user_lifecycle PASS)"),
    ("SecurityService", "DisableGoogleAuth"): (
        "tested-pass", "docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md (security_tfa_temp_user_lifecycle PASS)"),
    # Phase 9: raise_periodical_event operator workflow live-verified. The stand
    # accepts eventType=TargetList at DetectorEx.1/EventSupplier ({"error":"OK"});
    # a wrong type is now correctly rejected (BAD_EVENT_TYPE surfaced as apply error).
    ("ExternalDetectorService", "RaisePeriodicalEvent"): (
        "tested-pass",
        ".agent/tasks/phase-9-periodical-event/raw/live-verify.txt (TargetList accepted, OK; Event1 rejected)"),
    # The occasional path was HTTP-verified via external_event_inject before this
    # phase, but only now is its body-error contract proven; cite it for parity.
    ("ExternalDetectorService", "RaiseOccasionalEvent"): (
        "tested-pass",
        ".agent/tasks/phase-9-periodical-event/raw/live-verify.txt (Event1 accepted via external_event_inject path)"),
    # Phase 10: AuditEventInjector live-verified via tools/axxon_mcp_audit.py.
    # Six Inject* methods accept on the stand; InjectMMExportEvent errors (needs a
    # live export job) and stays pending.
    ("AuditEventInjector", "InjectCameraViewingEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectPtzControlEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectArchiveViewingEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectNgpJournalExportEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectClientAppOptionEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectLdapSetupEvent"): (
        "tested-pass", ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (injected)"),
    ("AuditEventInjector", "InjectMMExportEvent"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-10-audit-injector/raw/live-verify.txt (errors on stand: needs a live MM export job)"),
    # Phase 11: read-only RealtimeRecognizerService watchlist tools live-verified
    # against the stand's "Intersec Face List" (ELT_Face, 6 enrolled faces). The
    # fixture now exists, so these flip from fixture-warn to tested-pass.
    ("RealtimeRecognizerService", "GetLists"): (
        "tested-pass", ".agent/tasks/phase-11-recognizer-lists/raw/live-verify.txt (returns real face list)"),
    ("RealtimeRecognizerService", "GetListStream"): (
        "tested-pass", ".agent/tasks/phase-11-recognizer-lists/raw/live-verify.txt (streams list descriptor)"),
    ("RealtimeRecognizerService", "GetItems"): (
        "tested-pass", ".agent/tasks/phase-11-recognizer-lists/raw/live-verify.txt (streams 6 enrolled items, metadata only)"),
    # Phase 12: read-only DiscoveryService device discovery live-verified. Discover
    # starts a scan; GetDiscoveryProgress streams real found cameras (Hikvision/Dahua).
    ("DiscoveryService", "Discover"): (
        "tested-pass", ".agent/tasks/phase-12-device-discovery/raw/live-verify.txt (scan started)"),
    ("DiscoveryService", "GetDiscoveryProgress"): (
        "tested-pass", ".agent/tasks/phase-12-device-discovery/raw/live-verify.txt (streamed 3 real network cameras)"),
    # Phase 13: DomainNotifier/NodeNotifier reconcile (no new code). The shipped
    # domain_event_subscribe/node_event_subscribe tools exercise PullEvents,
    # PullDetailedEvents and DisconnectEventChannel on both notifiers; live runs
    # return clean idle streams (stream_idle + disconnect_clean true). The other
    # methods (UpdateSubscription/PushDiagnosticEvents/Ping) stay pending.
    ("DomainNotifier", "PullEvents"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (idle stream, clean disconnect)"),
    ("DomainNotifier", "PullDetailedEvents"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (idle stream, clean disconnect)"),
    ("DomainNotifier", "DisconnectEventChannel"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (disconnect_clean=true)"),
    ("NodeNotifier", "PullEvents"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (idle stream, clean disconnect)"),
    ("NodeNotifier", "PullDetailedEvents"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (idle stream, clean disconnect)"),
    ("NodeNotifier", "DisconnectEventChannel"): (
        "tested-pass", ".agent/tasks/phase-13-notifier-reconcile/raw/live-verify.txt (disconnect_clean=true)"),
    # Phase 14: RealtimeRecognizer watchlist write tools live-verified through the
    # MCP tools (recognizer_change_lists/items/clear). ChangeLists add/rename/remove
    # round-tripped; ChangeItems added an LPR plate confirmed by readback; Clear
    # wiped the node (authorized destructive). ChangeListsStream stays pending.
    ("RealtimeRecognizerService", "ChangeLists"): (
        "tested-pass", ".agent/tasks/phase-14-recognizer-writes/raw/live-verify.txt (add/rename/remove round-trip)"),
    ("RealtimeRecognizerService", "ChangeItems"): (
        "tested-pass", ".agent/tasks/phase-14-recognizer-writes/raw/live-verify.txt (LPR plate add confirmed by readback)"),
    ("RealtimeRecognizerService", "Clear"): (
        "tested-pass", ".agent/tasks/phase-14-recognizer-writes/raw/live-verify.txt (authorized node wipe, node empty after)"),
    # Phase 15: LogicService alert lifecycle probed live. RaiseAlert/GetActiveAlerts/
    # Begin/Continue/CancelAlertReview are reachable and exercised (raised real
    # alerts, read them back, ran review transitions). CompleteAlertReview/
    # EscalateAlert: the severity-enum bug is fixed (request now accepted, 200 vs
    # the old 500), but full success needs a rule-raised alert (user-raised alerts
    # only TTL-expire on this stand), so they stay fixture-needed.
    ("LogicService", "RaiseAlert"): (
        "tested-pass", ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (raised real alerts, returned alert_id)"),
    ("LogicService", "GetActiveAlerts"): (
        "tested-pass", ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (read back active alerts)"),
    ("LogicService", "BeginAlertReview"): (
        "tested-pass", ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (review transition exercised)"),
    ("LogicService", "ContinueAlertReview"): (
        "tested-pass", ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (review transition, result=True)"),
    ("LogicService", "CancelAlertReview"): (
        "tested-pass", ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (review transition exercised)"),
    ("LogicService", "CompleteAlertReview"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (severity bug fixed: SV_FALSE 200 vs false_alarm 500; full success needs a rule-raised alert)"),
    ("LogicService", "EscalateAlert"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-15-alarm-severity-fix/raw/live-verify.txt (reachable; full success needs a rule-raised alert)"),
    # Phase 16: LogicService control tools live-verified through the MCP tools
    # (launch_macro/change_arm_state). LaunchMacro ran the manual "Fire" macro;
    # ChangeArmState armed/disarmed cam1 for a bounded auto-reverting window.
    ("LogicService", "LaunchMacro"): (
        "tested-pass", ".agent/tasks/phase-16-macro-armstate/raw/live-verify.txt (launched manual macro Fire)"),
    ("LogicService", "ChangeArmState"): (
        "tested-pass", ".agent/tasks/phase-16-macro-armstate/raw/live-verify.txt (arm/disarm cam1, bounded auto-revert)"),
    # Phase 17: DomainSettingsService data-storage get+update live-verified through
    # the MCP tools. Get returned real retention/cleanup + etag; update changed
    # cleanup_period field-masked with the etag, confirmed by readback, then
    # restored (reversible). Export/GDPR/Bookmark RPCs stay pending.
    ("DomainSettingsService", "GetDataStorageSettings"): (
        "tested-pass", ".agent/tasks/phase-17-datastorage-settings/raw/live-verify.txt (read real retention/cleanup + etag)"),
    ("DomainSettingsService", "UpdateDataStorageSettings"): (
        "tested-pass", ".agent/tasks/phase-17-datastorage-settings/raw/live-verify.txt (field-masked etag update, readback + restore)"),
    # Phase 18: bookmark + GDPR settings updates. UpdateBookmarkSettings round-trips
    # (mandatory_protection toggle + restore). UpdateGDPRSettings is reachable but a
    # no-op on this stand (privacy masking needs a module/license), so fixture-warn.
    ("DomainSettingsService", "UpdateBookmarkSettings"): (
        "tested-pass", ".agent/tasks/phase-18-gdpr-bookmark-settings/raw/live-verify.txt (mandatory_protection toggle + restore)"),
    ("DomainSettingsService", "UpdateGDPRSettings"): (
        "tested-warn-fixture-needed",
        ".agent/tasks/phase-18-gdpr-bookmark-settings/raw/live-verify.txt (accepted but no-op: GDPR masking module not provisioned)"),
    # Phase 19: TimeZoneManager writes, all live round-tripped reversibly through the
    # MCP tools. SetTimeZone -> UTC then restored; SetNTP empty -> set -> cleared;
    # ChangeTimeZones add throwaway zone -> remove. Brings TimeZoneManager to 7/7.
    ("TimeZoneManager", "SetTimeZone"): (
        "tested-pass", ".agent/tasks/phase-19-timezone-ntp/raw/live-verify.txt (set UTC + restore)"),
    ("TimeZoneManager", "SetNTP"): (
        "tested-pass", ".agent/tasks/phase-19-timezone-ntp/raw/live-verify.txt (set pool.ntp.org + clear)"),
    ("TimeZoneManager", "ChangeTimeZones"): (
        "tested-pass", ".agent/tasks/phase-19-timezone-ntp/raw/live-verify.txt (add throwaway zone + remove)"),
    # Phase 20: ServerSettings writes live-verified through the MCP tools. SetLogLevel
    # INFO -> DEBUG -> restored to INFO; DropLogs authorized irreversible (server healthy
    # after). Brings ServerSettings to 3/3.
    ("ServerSettings", "SetLogLevel"): (
        "tested-pass", ".agent/tasks/phase-20-server-loglevel/raw/live-verify.txt (INFO -> DEBUG -> restore)"),
    ("ServerSettings", "DropLogs"): (
        "tested-pass", ".agent/tasks/phase-20-server-loglevel/raw/live-verify.txt (authorized drop, server healthy after)"),
    # Phase 21: GroupManager writes live round-tripped reversibly through the MCP tools.
    # ChangeGroups add throwaway group -> remove; SetObjectsMembership add object -> remove.
    # Brings GroupManager to 4/4.
    ("GroupManager", "ChangeGroups"): (
        "tested-pass", ".agent/tasks/phase-21-group-manager/raw/live-verify.txt (add throwaway group + remove)"),
    ("GroupManager", "SetObjectsMembership"): (
        "tested-pass", ".agent/tasks/phase-21-group-manager/raw/live-verify.txt (add object membership + remove)"),
    # Phase 22: RealtimeRecognizerService streaming watchlist write live round-tripped
    # reversibly through the MCP tool (add throwaway LPR list via stream -> remove via
    # stream). Closes the last non-fixture pending method; ChangeLists (deprecated) and
    # ChangeListsStream both now tested-pass.
    ("RealtimeRecognizerService", "ChangeListsStream"): (
        "tested-pass", ".agent/tasks/phase-22-recognizer-stream/raw/live-verify.txt (stream add LPR list + remove)"),
    # Phase 23: DiscoveryService node-scoped scan live-verified read-only through the MCP
    # tool (DiscoverNode + GetNodeDiscoveryProgress, found devices on node "Server").
    # Read-only network scan, no mutation. Node-scan reads now complete (Probe stays fixture-warn).
    ("DiscoveryService", "DiscoverNode"): (
        "tested-pass", ".agent/tasks/phase-23-discover-node/raw/live-verify.txt (node-scoped scan, devices found)"),
    # Phase 24: LayoutImagesManager streaming image download live round-tripped through the
    # MCP tool (uploaded a throwaway 1x1 PNG fixture, downloaded it via DownloadLayoutImage,
    # bytes matched, then removed). Read-only download; metadata-only response. LayoutImagesManager 4/4.
    ("LayoutImagesManager", "DownloadLayoutImage"): (
        "tested-pass", ".agent/tasks/phase-24-download-layout-image/raw/live-verify.txt (download streamed image, metadata-only)"),
    # Phase 25: UpdateSubscription live-verified through the self-contained MCP tool for both
    # notifiers (open short-lived subscription -> UpdateSubscription new filters -> disconnect).
    # Same helper covers both via the notifier param. Subscription torn down; nothing persists.
    ("DomainNotifier", "UpdateSubscription"): (
        "tested-pass", ".agent/tasks/phase-25-update-subscription/raw/live-verify.txt (domain: Bookmark -> Alert filters, disconnect clean)"),
    ("NodeNotifier", "UpdateSubscription"): (
        "tested-pass", ".agent/tasks/phase-25-update-subscription/raw/live-verify.txt (node: Bookmark -> Alert filters, disconnect clean)"),
    # Phase 26: DomainService batch read lookups live-verified read-only through the MCP view
    # tools using real camera/archive access points (each returned its entity, no fixture needed).
    # Brings DomainService to 21/21.
    ("DomainService", "GetCamerasByComponents"): (
        "tested-pass", ".agent/tasks/phase-26-domain-batch-reads/raw/live-verify.txt (1 camera by component AP)"),
    ("DomainService", "BatchGetArchives"): (
        "tested-pass", ".agent/tasks/phase-26-domain-batch-reads/raw/live-verify.txt (1 archive by AP)"),
    ("DomainService", "SearchMaps"): (
        "tested-pass", ".agent/tasks/phase-26-domain-batch-reads/raw/live-verify.txt (1 map locator by AP)"),
    # Phase 27: VMDAService ExecuteQueryTyped (non-deprecated typed forensic query) live-verified
    # read-only via vmda_query, which now builds a typed QueryDescription(motion_in_area) instead of
    # the deprecated ExecuteQuery MomentQuest string. Brings VMDAService to 3/4 (only Cleanup pending).
    ("VMDAService", "ExecuteQueryTyped"): (
        "tested-pass", ".agent/tasks/phase-27-vmda-query-typed/raw/live-verify.txt (typed motion-in-area query, real VMDA db + source)"),
    # Phase 28: ConfigurationManager.CollectBackup (read-only config export) live-verified through
    # collect_config_backup, which drains the backup stream and returns size/chunk metadata only.
    # Read-only (inverse of RestoreBackup); the safe member of the backup/restore cluster.
    ("ConfigurationManager", "CollectBackup"): (
        "tested-pass", ".agent/tasks/phase-28-collect-backup/raw/live-verify.txt (LOCAL export, 28 chunks / 1.82MB, metadata-only)"),
    # Phase 29: TelemetryService.Zoom live-verified reversibly through the ptz zoom tool on
    # DeviceIpint.53/TelemetryControl.0: capture position -> Zoom(absolute,0.4)=ok -> AbsoluteMove
    # restore to captured -> exact match. continuous mode is rejected by this simulated source.
    ("TelemetryService", "Zoom"): (
        "tested-pass", ".agent/tasks/phase-29-ptz-zoom/raw/live-verify.txt (Zoom absolute=ok, position captured + restored exactly)"),
    # Phase 30: GDPR user-data cleanup live-verified through the gated layout/map cleanup tools
    # using a throwaway, nonexistent user id -> the RPC executes (applied) but matches no real
    # user and deletes nothing real. Gate matrix (disabled/gap/error) holds with no wire call.
    ("LayoutManager", "UserDataCleanup"): (
        "tested-pass", ".agent/tasks/phase-30-gdpr-cleanup/raw/live-verify.txt (applied with throwaway user id, nothing real deleted)"),
    ("MapService", "UserDataCleanup"): (
        "tested-pass", ".agent/tasks/phase-30-gdpr-cleanup/raw/live-verify.txt (applied with throwaway user id, nothing real deleted)"),
    # Phase 31: AcfaService.PerformAction live-verified reversibly through perform_unit_action on the
    # ACFA emulator (EMULATOR_LOOP.17): capture DISARM -> ARM=applied -> DISARM restore -> original
    # state. VMDAService.Cleanup live-verified through vmda_cleanup on a camera with 0 analytics
    # intervals (verified empty first) -> result=True, nothing real deleted.
    ("AcfaService", "PerformAction"): (
        "tested-pass", ".agent/tasks/phase-31-vmda-acfa-actions/raw/live-verify.txt (ARM->DISARM reversible round-trip on the ACFA emulator)"),
    ("VMDAService", "Cleanup"): (
        "tested-pass", ".agent/tasks/phase-31-vmda-acfa-actions/raw/live-verify.txt (Cleanup on an empty-analytics camera, result=True, nothing real deleted)"),
    # Phase 32: AcfaService.DownloadData live-verified read-only through download_unit_data, which
    # drains the DownloadData stream for icon images discovered via list_unit_visualizations and
    # returns size metadata only. Completes AcfaService (7/7).
    ("AcfaService", "DownloadData"): (
        "tested-pass", ".agent/tasks/phase-32-acfa-download/raw/live-verify.txt (2 lock icon images, 344 bytes each, metadata-only)"),
    # Phase 33: TelemetryService - every method the live simulated PTZ device executes, verified
    # reversibly through the ptz tools on DeviceIpint.53/TelemetryControl.0 (presets created+removed,
    # position captured+restored, session released). The 12 device-unsupported methods (Focus/Iris/
    # auto/PointMove/AreaZoom/PerformAuxiliaryOperation/tour-writes) stay pending: the simulated
    # source rejects them (error 2 / GeneralError); closeable only on real PTZ hardware.
    ("TelemetryService", "KeepAlive"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (KeepAlive ok)"),
    ("TelemetryService", "ReleaseSessionId"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (ReleaseSessionId ok)"),
    ("TelemetryService", "Move"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (Move absolute ok)"),
    ("TelemetryService", "GetPositionInformationNormalized"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (normalized position read)"),
    ("TelemetryService", "AbsoluteMoveNormalized"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (normalized absolute move ok)"),
    ("TelemetryService", "GetPresetsInfo"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (list_presets ok)"),
    ("TelemetryService", "SetPreset"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (save_preset bare SetPreset, fresh-session ok)"),
    ("TelemetryService", "SetPreset2"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (set_preset SetPreset2 ok)"),
    ("TelemetryService", "GoPreset"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (go_preset fresh-session ok)"),
    ("TelemetryService", "RemovePreset"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (remove_preset fresh-session ok)"),
    ("TelemetryService", "ConfigurePreset"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (configure_preset ok)"),
    ("TelemetryService", "GetTours"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (get_tours ok)"),
    ("TelemetryService", "GetTourPoints"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (get_tour_points ok)"),
    ("TelemetryService", "GetAuxiliaryOperations"): (
        "tested-pass", ".agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt (get_auxiliary_operations ok)"),
    # Phase 34: MapService provider config completed via the gated map-providers module. Reversible
    # create->get->remove of a throwaway provider (lowercase id normalized to the server's uppercase).
    # Completes MapService (11/11).
    ("MapService", "ConfigureMapProviders"): (
        "tested-pass", ".agent/tasks/phase-34-map-providers/raw/live-verify.txt (create+remove throwaway provider, reversible)"),
    ("MapService", "GetMapProvider"): (
        "tested-pass", ".agent/tasks/phase-34-map-providers/raw/live-verify.txt (read back the created provider, NOT_FOUND after remove)"),
    # Phase 35: LogicService node-scoped batch alert ops live-verified through the new logic-alerts
    # module (node=Server, 0 active alerts -> clean no-op, unreachable_nodes empty). The 5 review
    # writes are approval-gated. BatchCompleteAlertsReview is NOT restamped: it reports
    # unreachable_nodes=['Server'] (cannot complete without a reviewable alert; same wall as the
    # single CompleteAlertReview). Counter ops stay fixture-walled (no counter configured).
    ("LogicService", "BatchGetActiveAlerts"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (node read, 0 active alerts)"),
    ("LogicService", "BatchFilterActiveAlerts"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (node+filter read)"),
    ("LogicService", "BatchBeginAlertsReview"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (applied, clean no-op)"),
    ("LogicService", "BatchContinueAlertsRewiew"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (applied, clean no-op)"),
    ("LogicService", "BatchCancelAlertsReview"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (applied, clean no-op)"),
    ("LogicService", "BatchEscalateAlerts"): (
        "tested-pass", ".agent/tasks/phase-35-logic-batch-alerts/raw/live-verify.txt (applied, clean no-op)"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply the restamp to the corpus file")
    args = ap.parse_args()

    doc = json.loads(CORPUS.read_text())
    changes = []
    for m in doc["methods"]:
        key = (m["service"], m["method"])
        if key not in RESTAMP:
            continue
        new_status, evidence = RESTAMP[key]
        old = m["live_status"]
        if old == new_status and m.get("evidence") == evidence:
            continue
        changes.append((m["service"], m["method"], old, new_status))
        m["live_status"] = new_status
        m["evidence"] = evidence

    for svc, meth, old, new in changes:
        print(f"  {old:28s} -> {new:28s} {svc}.{meth}")
    print(f"\n{len(changes)} method(s) restamped"
          f"{' (written)' if args.write else ' (dry-run, pass --write to apply)'}")

    if args.write and changes:
        CORPUS.write_text(json.dumps(doc, indent=2) + "\n")


if __name__ == "__main__":
    main()
