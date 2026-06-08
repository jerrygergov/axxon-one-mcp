# Spec: phase-47-state-tnt-probe

## Original task

Probe the 5 pending methods the coverage triage flagged as "possibly closeable" and either close
them or honestly reclassify them: ConfigurationManager.SetRevision, StateControlService.SetState,
and TagAndTrackService.SetMode/FollowTrack/MoveToCoords.

Live probing determined that none are code-closeable on this stand:
- StateControlService.SetState: the only relay-bearing device (DeviceIpint.54, generic driver)
  exposes StateControl.relay0:0/0:1 in the config graph, but GetCurrentState/GetDefaultState/SetState
  all return INTERNAL "Can't resolve reference to .../StateControl.relay0:0" -- the relay I/O object
  is not instantiated. The read companions (GetCurrentState/GetDefaultState) are ALREADY
  tested-warn-fixture-needed for exactly this reason.
- TagAndTrackService.SetMode/FollowTrack/MoveToCoords: ListTrackers returns NOT_FOUND on the device,
  every TelemetryControl endpoint, and the video source -- no calibrated Tag&Track tracker object is
  configured. ListTrackers (the read sibling) is ALREADY tested-warn-fixture-needed.
- ConfigurationManager.SetRevision: GetRevisionInfo works (461 revisions), but SetRevision rolls the
  entire shared/local config back to a prior revision -- a destructive whole-system config restore,
  not safely reversible on a shared stand. Left pending (like its sibling RestoreBackup) pending
  explicit authorization; not probed as a mutation.

This phase ships no production code. It moves the 4 stand-walled methods from pending to
tested-warn-fixture-needed (matching their already-fixture-warn read siblings) and documents the
finding. SetRevision stays pending.

## Acceptance criteria

- AC1: Live evidence (sanitized, host as <demo-host>) in raw/live-verify.txt records the endpoint
  discovery (DomainService.ListComponents) and the per-method probe results proving each of the 4
  reclassified methods was live-exercised and blocked by stand state (StateControl INTERNAL
  unresolved-reference, TagAndTrack NOT_FOUND), and explains why SetRevision is left pending.
- AC2: Corpus restamp is honest + idempotent. StateControlService.SetState and TagAndTrackService
  SetMode/FollowTrack/MoveToCoords -> tested-warn-fixture-needed with the phase-47 citation.
  ConfigurationManager.SetRevision is NOT changed (stays pending). No other ledger row is touched.
  `python3.12 tools/axxon_corpus_restamp.py --write` then a dry-run reports `0 method(s) restamped`.
  Totals: 283 tested-pass / 20 pending / 58 fixture-warn (361). Coverage doc headline + a phase-47
  note updated.
- AC3: Full test suite stays green (969) and production modules lint clean (no production code
  changed, so this is a regression guard).

## Constraints

- Credentials only from env; .env never staged. Sanitize host/creds in artifacts; secret-scan the
  staged diff.
- No production code changes; this is a probe-and-classify pass.
- Reclassify only the 4 stand-walled methods. Do not touch SetRevision or any unrelated row.
- No mutation was applied to the stand (every SetState attempt was rejected before applying; no
  relay toggled, no T&T mode changed).

## Non-goals

- No attempt to close SetRevision/RestoreBackup (destructive whole-config restore; needs explicit
  authorization + a throwaway target).
- No new StateControl/TagAndTrack tooling (the methods are stand-walled, not code-gapped).
- No fixture provisioning (would need a non-generic relay driver and a calibrated T&T tracker).

## Verification plan
- Build: n/a (no production code changed).
- Unit tests: python3.12 -m pytest tools/tests/ -q (regression guard, expect 969).
- Integration tests: same suite.
- Lint: uvx ruff check tools/axxon_corpus_restamp.py.
- Manual checks: restamp dry-run after write = 0; ledger totals 283/20/58.
