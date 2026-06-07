# Evidence Bundle: phase-31-vmda-acfa-actions

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-07

## AC1 — gated module + gate matrix — PASS
- `tools/axxon_mcp_acfa_vmda_control.py` defines `AxxonMcpAcfaVmdaControl` with env
  AXXON_CONTROL_APPROVE=1 + token CONFIRM-control-action. `_write_gate` returns
  disabled (env off) / gap (bad token) / None (proceed) before any wire call.
- Proof: tests test_disabled_when_env_off / test_gap_on_bad_token (assert
  client.calls == []); live gate matrix (raw/live-verify.txt).

## AC2 — list_unit_actions read tool — PASS
- Streams AcfaService.ListUnitsActions and returns {status: ok, units:[{uid, actions:
  [{id,name,input}]}]}. Empty uids -> error, no wire call (not gated).
- Proof: test_list_unit_actions_shape / test_list_unit_actions_empty_is_error_no_wire;
  live list returned 6 actions for the loop (raw/live-verify.txt).

## AC3 — perform_unit_action gated tool — PASS
- Calls AcfaService.PerformAction; returns applied (empty error_message) or
  action-error (device refused). Missing uid/action_id -> error no wire. properties
  mapped to PropertyDescriptor value_string.
- Proof: test_applied_records_action_and_props, test_action_error_when_device_refuses,
  test_error_on_missing_args_no_wire; live reversible ARM->DISARM restored the unit to
  its captured DISARM state (raw/live-verify.txt).

## AC4 — vmda_cleanup gated tool — PASS
- Calls VMDAService.Cleanup; discovers the VMDA db when omitted, strips the hosts/
  prefix from camera_id, returns applied + result. Missing camera_id -> error no wire;
  no db -> gap.
- Proof: test_applied_discovers_db_and_strips_prefix, test_error_on_missing_camera_no_wire;
  live cleanup on a camera with 0 intervals -> result=True, nothing deleted
  (raw/live-verify.txt).

## AC5 — 6-edit wiring + suite + restamp — PASS
- create_server param `control`, conditional register, register_control_tools with 4
  @server.tool entries, --enable-control flag, flag-gated instantiation, create_server
  arg. Full suite `Ran 824 ... OK` (up from 813); control suite 11 OK; no secret leak.
  AcfaService.PerformAction + VMDAService.Cleanup -> tested-pass; coverage 212/111/38,
  item 10r; restamp dry-run 0 after --write. VMDAService now 4/4.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_acfa_vmda_control" (import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_acfa_vmda_control.py -v (11 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 824 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (2 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-31-vmda-acfa-actions/raw/build.txt
- .agent/tasks/phase-31-vmda-acfa-actions/raw/test-unit.txt
- .agent/tasks/phase-31-vmda-acfa-actions/raw/test-integration.txt
- .agent/tasks/phase-31-vmda-acfa-actions/raw/lint.txt
- .agent/tasks/phase-31-vmda-acfa-actions/raw/live-verify.txt

## Stand hygiene
- ACFA: the loop was returned to its captured DISARM state; no unit left changed.
  VMDA: cleanup ran only on a camera verified to have 0 analytics intervals; nothing
  real deleted. Writes default-off (env + token). No proto/CA/PDF committed; secrets
  env-only.

## Known gaps
- AcfaService.DownloadData still pending (separate). GSM/EMail sends still
  environment-walled (no SMTP/GSM infra).
