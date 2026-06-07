# Evidence: phase-39-security-credentials

Overall: PASS (all acceptance criteria PASS)

## AC1 — New module with read + gated credential changes — PASS
`tools/axxon_mcp_security_credentials.py` defines `AxxonMcpSecurityCredentials` with
`check_password` (read), `change_my_password` (gated), `change_my_login` (gated), plus the
connect helper / `connect_axxon_profile` / `ensure_client` / `_stub_and_pb2` / `_write_gate`.
Approval env `AXXON_SECURITY_CREDENTIALS_APPROVE`, token `CONFIRM-security-credentials`.
change_my_password/change_my_login act on the connected session's OWN user (no user_id arg),
documented in the module docstring. Idiom matches `tools/axxon_mcp_bookmark_extras.py`.

## AC2 — Gate enforced before any wire call — PASS
`tools/tests/test_axxon_mcp_security_credentials.py` GateTests: password env-off -> disabled,
bad token -> gap, empty -> error; login env-off -> disabled, empty -> error; check_password
empty user -> error; all assert `client.calls == []`. Live: gate env-off=disabled,
bad-token=gap (raw/live-verify.txt).

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `security_credentials`, conditional
`register_security_credentials_tools`, the register function with 4 `@server.tool` entries,
`--enable-security-credentials` flag, flag-gated instantiation, pass to create_server. Server
smoke registered all 4 tools. Imports OK (raw/build.txt).

## AC4 — Live reversible evidence — PASS
raw/live-verify.txt (sanitized): check_password -> NOT_UNIQUE for current pw, OK for unused
pw, error for empty user; change_my_password -> OK on throwaway admin user A (removed,
ListUsers confirms gone); change_my_login -> OK on throwaway admin user B (removed, gone).
Separate users because the module re-authenticates per call. The shared root account is never
modified. All probe credential values are generated throwaways, redacted in the transcript.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps CheckPassword, ChangePassword, ChangeLogin ->
tested-pass; all 7 LDAP methods (TestLDAPConnection, StartLDAPSynchronization,
StopLDAPSynchronization, SearchLDAP, SearchLDAP2, SearchLDAPGroups,
GetLDAPSynchronizationState) -> tested-warn-fixture-needed (5 were previously still pending),
since there is no LDAP server on this stand. Dry-run after --write reports `0 method(s)
restamped`. Coverage doc updated to 245 tested-pass / 82 pending / 34 fixture-warn;
SecurityService 28/35 with no pending rows left.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `892 passed` (881 prior + 11 new). Production module + server lint
clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
