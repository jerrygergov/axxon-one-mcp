# Spec: phase-8-finish-all (close the last three gaps)

User directive: finish ALL remaining gaps. Test stand is disposable; destructive testing authorized.
Per-gap depth chosen by the user:
- PTZ: implement + fixture-gated verify (ship code; live motion stays gated on a PTZ device).
- 5F-B2 remainder: full reversible security mutations, live-verified create-then-remove on the stand.
- Schedules: prove API-impossibility exhaustively, then document with evidence.

## Ground truth (from Integration APIs 3.0 + proto files)
- TelemetryService (`axxonsoft/bl/ptz/Telemetry.proto`) is fully specified: AcquireSessionId, KeepAlive,
  ReleaseSessionId, IsSessionAvailable, Move, Zoom, Focus/FocusAuto, Iris/IrisAuto, AbsoluteMove(+Normalized),
  GetPositionInformation(+Normalized), SetPreset/SetPreset2/ConfigurePreset/GoPreset/RemovePreset,
  PointMove, AreaZoom, GetPresetsInfo, GetAuxiliaryOperations/PerformAuxiliaryOperation, tours.
  PTZ access point is `.../DeviceIpint.N/TelemetryControl.0`.
- Live probe (2026-06-05): the *filtered inventory* (200 components) shows 0 telemetry endpoints, but the full
  config graph (501 components) has 3 real ones on `DeviceIpint.53` (TelemetryControl.0/1/2). They respond:
  IsSessionAvailable=true, GetPosition returns live coords, AcquireSessionId+AbsoluteMove+restore+release all
  work. PTZ is FULLY LIVE-VERIFIABLE, not fixture-gated. (Same false-negative pattern as VMDA/archived-events.)
- SecurityService (`axxonsoft/bl/security/SecurityService.proto`) offers ChangeConfig (role/user store),
  ChangePassword, ChangeLogin, Set{Global,Groups,Object,Macros}Permissions.
- PDF has 0 pages mentioning "schedule"/"calendar"/"weekly"; no schedule descriptor on any of 38 devices.

## Acceptance criteria
### PTZ (ptz_controller)
- AC1: New `tools/axxon_mcp_ptz.py` exposes the documented TelemetryService surface as bounded tools
  (discover telemetry sources, acquire/keepalive/release session, move/zoom/focus/iris, absolute + normalized
  move, presets list/set/go/remove, point/area move, auxiliary ops, position read). Registered behind
  `--enable-ptz`.
- AC2: Telemetry-source discovery returns a clean structured `gap` (not a crash) when no `TelemetryControl`
  endpoint exists; every control call refuses with a structured gap when the source is missing.
- AC3: Exhaustive unit tests with a fake client cover the happy path (session lifecycle + each control) and the
  no-endpoint gap path.
- AC4 (live): against the stand's `DeviceIpint.53/TelemetryControl.0`, exercise the full lifecycle: discover
  source, acquire session, read position, AbsoluteMove, restore original position, release session, plus a
  preset round-trip; raw evidence saved. The no-endpoint gap path is still unit-tested for cameras without PTZ.

### 5F-B2 remainder (full reversible security mutations)
- AC5: Add reversible production user lifecycle workflows to `axxon_mcp_admin_mutations.py`:
  `security_user_create_lifecycle` (create ephemeral codex user -> verify -> delete -> verify-absent),
  `security_user_credential_lifecycle` (on an ephemeral user: change_login + change_password -> verify ->
  restore/remove). Same approval gate (`AXXON_ADMIN_MUTATION_APPROVE=1`) and confirmation tokens as 5F-B1.
- AC6: Each new workflow has plan/apply/verify/rollback and only ever targets generated codex-* objects; it
  refuses to mutate `root` or any non-ephemeral account.
- AC7: Unit tests cover plan/apply/verify/rollback and the refuse-non-ephemeral path.
- AC8 (live): apply + verify + rollback each new workflow on the stand against ephemeral objects, leaving the
  security store as found; raw evidence saved.
- Out of scope (documented, not reversible / can brick the stand): `license_apply`/`license_drop`,
  `time_set_timezone`/`time_set_ntp`, LDAP sync against a real directory.

### Schedules
- AC9: Probe every plausible API surface (config ChangeConfig descriptors, LogicService, Macro, all proto
  descriptors, the live unit/component tree) for any schedule/calendar/weekly authoring RPC or descriptor.
  Record the search and the negative result as evidence; document `schedule_descriptor_get` as a hard API
  limitation (desktop-client authored) rather than a code gap.

### Global
- AC10: Full suite green: `python3.12 -m unittest discover -s tools/tests` (no failures), test count grows.
- AC11: Docs (STATUS.md, roadmap) updated to reflect the closed/clarified state.

## Constraints
- Smallest defensible diffs; reuse existing patterns (admin_mutations registry, optional `--enable-*` flag,
  fake-client unit tests).
- TDD where practical.
- Never commit proto files, CA, or the PDF; remove the `docs/grpc-proto-files` symlink before any commit.
- Sanitize all committed evidence; intrinsic `hosts/Server/...` UIDs may stay.
- Retry transient `urlopen`/`DEADLINE_EXCEEDED` up to 3x in live runs.
- Live security mutations require `AXXON_ADMIN_MUTATION_APPROVE=1` and must restore the stand to its prior state.
