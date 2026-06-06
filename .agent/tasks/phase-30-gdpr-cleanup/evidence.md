# Evidence Bundle: phase-30-gdpr-cleanup

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — gated module + gate matrix — PASS
- `tools/axxon_mcp_gdpr_cleanup.py` defines `AxxonMcpGdprCleanup` with env
  AXXON_GDPR_APPROVE=1 + token CONFIRM-gdpr-cleanup. `_write_gate` returns disabled
  (env off), gap (bad token), None (proceed) before any wire call; empty user_ids
  returns error with no wire call.
- Proof: tests test_disabled_when_env_off / test_gap_on_bad_token /
  test_error_on_empty_ids (each asserts client.calls == []); live gate matrix
  (raw/live-verify.txt).

## AC2 — two cleanup tools — PASS
- `layout_user_data_cleanup` and `map_user_data_cleanup` call
  LayoutManager.UserDataCleanup and MapService.UserDataCleanup, returning
  {status: applied, tool, user_ids}. Connect/ensure_client/_stub_and_pb2 mirror the
  groups module.
- Proof: test_layout_cleanup_applied_records_rpc (records LayoutManager UserDataCleanup
  with the right ids), test_map_cleanup_applied_records_rpc (MapService); live applied
  for both with a throwaway id (raw/live-verify.txt).

## AC3 — 6-edit server wiring — PASS
- create_server gains the `gdpr_cleanup` param; conditional
  register_gdpr_cleanup_tools call; register function with 3 @server.tool entries;
  --enable-gdpr-cleanup CLI flag; flag-gated instantiation in main; passed into
  create_server. Import smoke clean (build.txt).

## AC4 — unit + full suite green — PASS
- gdpr suite 6 OK. Full suite `Ran 813 tests ... OK` (raw/test-integration.txt), up
  from 807. No config secret leak (test_no_config_secret_leak).

## AC5 — corpus restamp + coverage doc — PASS
- LayoutManager.UserDataCleanup + MapService.UserDataCleanup -> tested-pass. Coverage
  210 pass-class / 113 pending / 38 fixture-warn; item 10q. Restamp dry-run reports 0
  after --write.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_gdpr_cleanup" (import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_gdpr_cleanup.py -v (6 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 813 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (2 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-30-gdpr-cleanup/raw/build.txt
- .agent/tasks/phase-30-gdpr-cleanup/raw/test-unit.txt
- .agent/tasks/phase-30-gdpr-cleanup/raw/test-integration.txt
- .agent/tasks/phase-30-gdpr-cleanup/raw/lint.txt
- .agent/tasks/phase-30-gdpr-cleanup/raw/live-verify.txt

## Stand hygiene
- Live verification used ONLY a throwaway/nonexistent user id; nothing real was
  deleted. Writes are default-off (env + token). VMDA Cleanup and notifier sends
  deferred honestly (not restamped). No proto/CA/PDF committed; secrets env-only.

## Known gaps
- VMDAService.Cleanup deferred (destructive on shared analytics data).
- EMailNotifier.SendEMail / GSMNotifier.SendSMS deferred (no notifier/SMTP/GSM infra
  on the stand; environment-walled, cannot be honestly live-passed).
