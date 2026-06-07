# Task Spec: phase-40-auth-sessions

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (AuthenticationService rows)
- tools/axxon_mcp_security_credentials.py (gated module idiom to mirror)
- tools/axxon_api_client.py (authenticate_grpc uses AuthenticateEx2 + token metadata)

## Original task statement
Continue the API-coverage proof loop. Close the serviceable AuthenticationService
session/auth-flow methods (Authenticate, Authenticate2, AuthenticateEx, RenewSession,
RenewSession2, CloseSession) via a new module mirroring the gated-module idiom. Live-verify
safely. Document the TFA/public-key methods as environment-walled.

## Live probe findings (2026-06-07, demo stand)
- Authenticate / Authenticate2 / AuthenticateEx: credential-based (user_name+password on the
  unauthenticated channel), each returns a valid token. SERVICEABLE (read-like, mint token).
- RenewSession / RenewSession2: empty request on the AUTHENTICATED (token-bearing) channel,
  each returns error_code 0 and a fresh token. SERVICEABLE.
- CloseSession: empty request on the authenticated channel, returns error_code OK (0).
  Closes the CALLING session, so it is verified on a SEPARATE throwaway session (a second
  authenticated client) to avoid killing the main session. SERVICEABLE.
- ApproveAuthentication / DeclineAuthentication / AuthenticateBySecondFactor /
  AuthenticateWithPublicKey: need TFA / supervisor-approval / public-key flows not configured
  on this stand -> stay fixture-warn (environment-walled).

## Message shapes (confirmed live)
- AuthenticateRequest{user_name, password}; AuthenticateResponse{token_name, token_value, expires_at, expires_in, is_unrestricted, user_id, roles_ids}.
- AuthenticateEx/RenewSession/RenewSession2 return AuthenticateResponseEx{..., error_code(EAuthenticateCode), error_description}.
- RenewSessionRequest{} (empty), CloseSessionRequest{} (empty).
- CloseSessionResponse{error_code: EErrorCode(OK/GENERAL_ERROR/IP_BLOCKED)}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_auth_sessions.py exposes authenticate (read, supports
  variant in {Authenticate, Authenticate2, AuthenticateEx}), renew_session (read, supports
  variant in {RenewSession, RenewSession2}), close_session (gated). connect helper +
  ensure_client + _write_gate match the security_credentials idiom. Approval env
  AXXON_AUTH_SESSIONS_APPROVE=1, confirmation token CONFIRM-auth-sessions. The tools must not
  return raw token values (token_present boolean only), to avoid leaking session tokens.
- AC2: close_session enforces the gate before any wire call: env-off -> {"status":"disabled"};
  bad token -> {"status":"gap"}. authenticate with empty user_name/password -> {"status":"error"}.
  Unit tests assert client.calls==[] in each gated/empty case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_auth_sessions_tools with @server.tool entries, --enable-auth-sessions flag,
  flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: Authenticate/Authenticate2/AuthenticateEx each mint a token;
  RenewSession/RenewSession2 each return error_code 0 with a fresh token; CloseSession returns
  OK on a separate throwaway session (the main session stays usable). Raw transcript
  raw/live-verify.txt with host/creds sanitized and no token values.
- AC5: Corpus restamp marks Authenticate, Authenticate2, AuthenticateEx, RenewSession,
  RenewSession2, CloseSession tested-pass; the 4 TFA/public-key methods left
  tested-warn-fixture-needed with honest citations. Dry-run after --write reports 0 restamped.
  Coverage doc updated; AuthenticationService 8/12.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- Never return or log raw token values (token_present boolean only).
- CloseSession verified on a throwaway session only; the main/root session is never closed.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>.
- Smallest defensible diff; reuse public_config_summary and the existing client.

## Non-goals
- Re-implementing the primary AuthenticateEx2 flow the client already uses.
- TFA / supervisor-approval / public-key auth (not configured on this stand).
- Long-lived session pooling or token caching beyond a single call.

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_auth_sessions.py (read, gate, no-token-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript (mint/renew/close on throwaway session) + restamp dry-run clean.
