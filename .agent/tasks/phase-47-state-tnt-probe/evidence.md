# Evidence: phase-47-state-tnt-probe

Overall: PASS (all acceptance criteria PASS)

## AC1 — Live probe evidence — PASS
raw/live-verify.txt (sanitized, host as <demo-host>) records the endpoint discovery via
DomainService.ListComponents (500 APs: TelemetryControl.0/1/2 and StateControl.relay0:0/0:1 on
DeviceIpint.54, the only relay/telemetry-bearing device, added with a generic driver) and the
per-method probe results:
- StateControlService.SetState (and GetCurrentState/GetDefaultState) -> INTERNAL "Can't resolve
  reference to .../StateControl.relay0:0" on both relays; the relay I/O object is not instantiated.
- TagAndTrackService ListTrackers -> NOT_FOUND on the device, every TelemetryControl endpoint, and
  the video source; no calibrated Tag&Track tracker object exists, so SetMode/FollowTrack/
  MoveToCoords cannot be exercised.
- ConfigurationManager.GetRevisionInfo works (461 revisions); SetRevision is a destructive
  whole-config restore and was NOT probed as a mutation (left pending).
No stand state was changed (every SetState attempt was rejected before applying).

## AC2 — Corpus restamp honest + idempotent — PASS
tools/axxon_corpus_restamp.py adds 4 phase-47 entries: StateControlService.SetState +
TagAndTrackService SetMode/FollowTrack/MoveToCoords -> tested-warn-fixture-needed (out of pending),
matching their already-fixture-warn read siblings (GetCurrentState/GetDefaultState, ListTrackers).
ConfigurationManager.SetRevision left pending. `--write` applied; dry-run after = `0 method(s)
restamped`. Totals now 283 tested-pass / 20 pending / 58 fixture-warn (361). Coverage doc headline +
item 10ah updated; README + STATUS coverage line updated. As part of touching this file, 6
dead-shadowed duplicate TelemetryService keys (phase-8 fixture-warn entries superseded by the
phase-33 tested-pass entries that Python's dict already kept) were removed; the effective ledger is
unchanged (the 6 methods stay tested-pass) and ruff F601 now passes.

## AC3 — Regression guard (no production code changed) — PASS
No production module changed (probe-and-classify only; restamp dedup is cosmetic). raw/
test-integration.txt: 969 passed. raw/lint.txt: All checks passed! (uvx ruff check on the restamp
module, F601 duplicate-key warnings cleared).
