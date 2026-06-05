# Task Spec: phase-10-audit-injector

## Metadata
- Task ID: phase-10-audit-injector
- Created: 2026-06-05
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- docs/api-audit/capability-vs-coverage-2026-06-05.md (AuditEventInjector listed 0/7)
- Pattern: tools/axxon_mcp_bookmarks.py (dataclass module) +
  tools/axxon_mcp_admin_mutations.py (approval gating)
- Live probe (this session): 6/7 Inject* methods accept on the stand via direct gRPC.

## Original task statement
Expose AuditEventInjector as MCP tools so external integrations can write
audit-trail events (compliance use case). The service is write-only and NOT
reversible (you cannot un-inject a journal record), so it is gated behind an
explicit approval env + confirmation token, mirroring the admin-mutation gate,
not the plan/apply/verify/rollback operator model.

Live-verified accepted methods (this stand): InjectCameraViewingEvent,
InjectPtzControlEvent, InjectArchiveViewingEvent, InjectNgpJournalExportEvent,
InjectClientAppOptionEvent, InjectLdapSetupEvent. InjectMMExportEvent errors
(needs a real export job) and stays uncovered.

## Acceptance criteria
- AC1: New module `tools/axxon_mcp_audit.py` with an `AxxonMcpAudit` dataclass
  exposing `audit_connect_axxon_profile`, `list_audit_event_kinds`, and
  `audit_inject(kind, params, confirmation)`. Direct gRPC via
  `AuditEventInjector` (`axxonsoft/bl/audit/Audit.proto`).
- AC2: `list_audit_event_kinds()` returns the supported kinds with their required
  param fields (camera_viewing -> [camera_ap]; ptz_control -> [camera_ap];
  archive_viewing -> [camera_ap, archive_ap]; journal_export -> [start, end];
  client_app_option -> [group, setting, setting_value];
  ldap_setup -> [ldap, group, setting, setting_value]). No live call.
- AC3: `audit_inject` is gated: without approval env (`AXXON_AUDIT_INJECT_APPROVE=1`)
  it returns `{"status":"disabled", ...}`; with approval but a missing/incorrect
  confirmation token (`CONFIRM-audit-inject`) it returns `{"status":"gap"/"error"}`;
  only with both does it call the wire.
- AC4: `audit_inject` validates the kind and required params before any wire call;
  unknown kind or missing required param returns a structured error, not an exception.
- AC5: Unit tests under `tools/tests/` cover kind catalog, gating (disabled / bad
  token / approved), param validation, and a fake-client success path. Full suite
  stays green (`python3.12 -m unittest discover -s tools/tests`).
- AC6: The six accepted AuditEventInjector methods are restamped
  `pending -> tested-pass` in the corpus via `tools/axxon_corpus_restamp.py` with a
  cited live-evidence string. `InjectMMExportEvent` stays `pending` (errors on stand).
- AC7: The module is registered in `tools/axxon_mcp_server.py` behind an
  `--enable-audit` flag (off by default), consistent with how other mutating
  modules are wired (ptz/admin-mutations/metadata).

## Constraints
- Reuse `AxxonApiClient` direct gRPC (`stub_from_proto` + `import_module`); no new client.
- Write-only + irreversible: approval env + per-call confirmation token; no rollback claim.
- Env-only secrets; sanitize evidence (`<demo-host>`, `<demo-user>`, `<redacted>`);
  `hosts/Server/...` UIDs may stay. No proto/PDF committed.
- Google-style docstrings, no banned words, no defensive programming beyond the
  documented gating/validation contract.

## Non-goals
- InjectMMExportEvent (needs a live export job fixture).
- A read-back verifier of the audit journal (audit records are not trivially
  queryable by injected id; acceptance of the call is the live signal).
- A code-generator template for audit injection.

## Verification plan
- Build: new tools/axxon_mcp_audit.py + tests + server registration + restamp entry.
- Unit: `python3.12 -m unittest discover -s tools/tests` green incl. new tests.
- Integration: live inject of the 6 accepted kinds against the stand (camera 1 /
  AliceBlue archive), record acceptance in raw/. Retry 3x on transient timeouts.
- Lint: n/a.
- Manual: `list_audit_event_kinds()` output inspected for AC2 shape.
