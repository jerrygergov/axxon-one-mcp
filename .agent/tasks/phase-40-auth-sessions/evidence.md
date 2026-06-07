# Evidence: phase-40-auth-sessions

Overall: PASS (all acceptance criteria PASS)

## AC1 — New module with reads + gated close, no token leak — PASS
`tools/axxon_mcp_auth_sessions.py` defines `AxxonMcpAuthSessions` with `authenticate`
(variant in Authenticate/Authenticate2/AuthenticateEx), `renew_session` (variant in
RenewSession/RenewSession2), `close_session` (gated), plus connect helper / ensure_client /
_write_gate. Approval env `AXXON_AUTH_SESSIONS_APPROVE`, token `CONFIRM-auth-sessions`. Tools
report token_present boolean + response code only, never raw token_value.

## AC2 — Gate + input validation before any wire call — PASS
`tools/tests/test_axxon_mcp_auth_sessions.py` GateTests: close env-off -> disabled, bad token
-> gap; authenticate empty creds / bad variant -> error; renew bad variant -> error; all
assert `client.calls == []`. Live: gate env-off=disabled, bad-token=gap (raw/live-verify.txt).

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `auth_sessions`, conditional `register_auth_sessions_tools`,
the register function with 4 `@server.tool` entries, `--enable-auth-sessions` flag,
flag-gated instantiation, pass to create_server. Server smoke registered all 4 tools. Imports
OK (raw/build.txt).

## AC4 — Live evidence — PASS
raw/live-verify.txt (sanitized): Authenticate/Authenticate2/AuthenticateEx each token_present
True (expires_in 300); RenewSession/RenewSession2 each error_code 0 token_present True;
close_session on a throwaway session -> applied OK; the main session still renews afterward
(still usable). No token values in the transcript.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps Authenticate, Authenticate2, AuthenticateEx,
RenewSession, RenewSession2, CloseSession -> tested-pass; ApproveAuthentication,
DeclineAuthentication, AuthenticateBySecondFactor, AuthenticateWithPublicKey ->
tested-warn-fixture-needed. Dry-run after --write reports `0 method(s) restamped`. Coverage
doc updated to 251 tested-pass / 72 pending / 38 fixture-warn; AuthenticationService 8/12 with
no pending rows left.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `902 passed` (892 prior + 10 new). Production module + server lint
clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
