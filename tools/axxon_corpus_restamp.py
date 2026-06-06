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
