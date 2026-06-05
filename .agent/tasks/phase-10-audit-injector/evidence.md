# Evidence Bundle: phase-10-audit-injector

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + direct gRPC — PASS
- `tools/axxon_mcp_audit.py` adds `AxxonMcpAudit` with
  `audit_connect_axxon_profile`, `list_audit_event_kinds`, `audit_inject`.
  Direct gRPC via `stub_from_proto("axxonsoft/bl/audit/Audit.proto", "AuditEventInjector")`.

## AC2 — kind catalog with required fields — PASS
- `list_audit_event_kinds()` returns 6 kinds with required params
  (camera_viewing/ptz_control->[camera_ap]; archive_viewing->[camera_ap, archive_ap];
  journal_export->[start, end]; client_app_option->[group, setting, setting_value];
  ldap_setup->[ldap, group, setting, setting_value]).
- Proof: `test_kind_catalog_lists_required_fields`.

## AC3 — approval + confirmation gating — PASS
- No approval -> `{"status":"disabled"}`; approved but wrong token -> no wire call;
  approved + `CONFIRM-audit-inject` -> wire call.
- Proof: `test_inject_disabled_without_approval`, `test_inject_rejects_bad_confirmation`,
  `test_inject_success_calls_wire`.

## AC4 — kind + param validation before wire — PASS
- Unknown kind and missing required param return structured errors, no wire call.
- Proof: `test_inject_unknown_kind`, `test_inject_missing_required_param`.

## AC5 — unit tests + full suite green — PASS
- 7 tests in `tools/tests/test_axxon_mcp_audit.py`.
- Full suite `Ran 696 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp, live-justified — PASS
- Live (raw/live-verify.txt): all 6 kinds `injected` against the stand (camera 1 /
  AliceBlue archive). `InjectMMExportEvent` errors -> stays fixture-warn.
- 6 methods restamped `pending -> tested-pass`, 1 -> `tested-warn-fixture-needed`
  via `tools/axxon_corpus_restamp.py`. AuditEventInjector 0/7 -> 6/7 pass.
- Note: an earlier sweep hit `DEADLINE_EXCEEDED` on a slow stand window; rerun with
  a 30s timeout injected all 6 cleanly (transient env, not a code defect).

## AC7 — server registration behind --enable-audit — PASS
- `register_audit_tools` registers `audit_connect_axxon_profile`,
  `list_audit_event_kinds`, `audit_inject`; wired via `--enable-audit` (off by
  default), `audit` param threaded through `create_server`.
- Proof: register sanity check lists all 3 tool names.

## Sanitization
- raw/live-verify.txt contains only `hosts/Server/...` UIDs; no host IP / creds.
