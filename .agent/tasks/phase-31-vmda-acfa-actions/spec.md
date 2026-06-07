# Spec: phase-31-vmda-acfa-actions

## Original task statement
Close two gated control gaps now that targets exist on the stand:
1. VMDAService.Cleanup — wipe a camera's VMDA analytics for a schema.
2. AcfaService.PerformAction — perform an action on an ACFA unit (the user added an
   ACFA emulator: virtual locks/readers/loops/fences/sensors/zone-groups).
Ship one new approval-gated module covering both, plus the read helpers needed to
drive PerformAction safely (list a unit's available actions).

Probe results (live, <demo-host>):
- VMDA db: hosts/Server/VMDA_DB.0/Database; schema_ID="vmda_schema". Cleanup on a real
  camera with 0 analytics intervals (e.g. DeviceIpint.1/SourceEndpoint.video:0:0)
  returned result=True and deleted nothing real (the camera had no VMDA data).
- ACFA: units are addressed by access_point as uid, e.g.
  hosts/Server/ACFA.2/EMULATOR_LOOP.17. ListUnitsActions returns per-unit actions
  (loops/fences/pads/zone-groups expose ARM/DISARM/ALARM/HANDLE_ALARM; readers expose
  OPEN/CLOSE/BLOCK/UNBLOCK/PASS; root exposes SYNCHRO_TIME). PerformAction(uid, id)
  returns PerformActionResponse{error_message, properties}; empty error_message = ok.
  Reversible round-trip verified: capture DISARM -> ARM (ok) -> state ARM -> DISARM
  (ok) -> state DISARM restored.

## Acceptance criteria

- AC1: New module `tools/axxon_mcp_acfa_vmda_control.py` defines a dataclass with the
  gated idiom: env `AXXON_CONTROL_APPROVE=1` + token `CONFIRM-control-action`.
  `_write_gate(confirmation)` returns disabled (env off) / gap (bad token) / None
  before any wire call.
- AC2: Read tool `list_unit_actions(uids)` streams AcfaService.ListUnitsActions and
  returns {status: ok, units: [{uid, actions: [{id, name, input:[{id,type}]}]}]}.
  Empty uids -> {status: error} with no wire call. (Read, not gated.)
- AC3: Gated tool `perform_unit_action(uid, action_id, properties, confirmation)`
  calls AcfaService.PerformAction and returns {status: applied|action-error, tool,
  uid, action_id, error_message, outputs}. error_message non-empty -> status
  action-error (the wire call happened but the device rejected it). Missing uid or
  action_id -> {status: error} no wire call. properties is an optional list of
  {id, value} mapped to PropertyDescriptor with the right typed value.
- AC4: Gated tool `vmda_cleanup(camera_id, schema_id, database, confirmation)` calls
  VMDAService.Cleanup and returns {status: applied, tool, camera_id, schema_id,
  database, result}. Missing camera_id -> {status: error} no wire call. database is
  discovered (`*/VMDA_DB.N/Database`) when omitted; if none found -> {status: gap}.
- AC5: Server wired with the 6-edit pattern (--enable-control flag, param, register,
  instantiation, create_server arg). Unit tests cover gate matrix + applied + error
  + no-leak for all three tools. Full suite green. Corpus restamp
  ("VMDAService","Cleanup") and ("AcfaService","PerformAction") -> tested-pass;
  restamp dry-run 0 after --write; coverage doc updated. Live verify recorded.

## Constraints
- Mutations approval-gated (env + token), default-off.
- VMDA Cleanup live-verified ONLY on a camera with 0 analytics intervals (verified
  empty first) -> real RPC, real target, nothing real deleted.
- ACFA PerformAction live-verified reversibly: capture state -> ARM -> verify ->
  DISARM restore -> verify original state. No unit left in a changed state.
- Reuse the groups/gdpr gating idiom and the 6-edit server pattern.

## Non-goals
- AcfaService.DownloadData (separate), other ACFA reads already tested-pass.
- Wiping a camera that actually has analytics data.

## Verification plan
- Build: pyimport smoke (server + new module)
- Unit tests: gate matrix + applied + error + no-leak for the 3 tools
- Integration tests: full suite discover
- Lint: n/a
- Manual checks: live list_unit_actions; perform_unit_action ARM then DISARM restore;
  vmda_cleanup on an empty camera -> result True; gate disabled/gap; restamp dry 0
