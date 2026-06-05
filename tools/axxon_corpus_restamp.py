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
