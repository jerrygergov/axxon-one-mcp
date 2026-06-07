# Task Spec: phase-39-security-credentials

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (SecurityService rows)
- tools/axxon_mcp_bookmark_extras.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close the serviceable SecurityService credential
methods (CheckPassword, ChangePassword, ChangeLogin) via a new gated module mirroring the
bookmark_extras idiom. Live-verify reversibly. Document the LDAP cluster as
environment-walled (no LDAP server on this stand).

## Live probe findings (2026-06-07, demo stand)
- CheckPassword: READ-ONLY password-uniqueness/policy pre-check (NOT an auth check). Current
  user's existing password -> NOT_UNIQUE; any unused password -> OK. No state change.
  user_id is the User.index from GetRestrictedConfig.current_user.
- ChangePassword / ChangeLogin: act on the AUTHENTICATED session's own user (request carries
  no user_id). Verified reversibly on a THROWAWAY admin user: as root, ChangeConfig adds a
  user with a password + admin role assignment; a second AxxonApiClient authenticates as that
  user; ChangePassword -> OK and ChangeLogin -> OK on that session; then root ChangeConfig
  removes the user + assignment (ListUsers confirms gone). The shared root account is never
  touched.
- LDAP cluster (TestLDAPConnection, Start/StopLDAPSynchronization, SearchLDAP, SearchLDAP2,
  SearchLDAPGroups, GetLDAPSynchronizationState): GetLDAPSynchronizationState returns
  UNAVAILABLE ("Can't get connection channel"); no LDAP server is configured/reachable on
  this stand -> all stay fixture-warn (environment-walled), honest.

## Message shapes (confirmed live)
- CheckPasswordRequest{user_id, password}; CheckPasswordResponse{result: EResult(OK/NOT_UNIQUE/INVALID)}.
- ChangePasswordRequest{password}; ChangePasswordResponse{result: EResult(OK/NOT_UNIQUE_PASSWORD/WEAK_PASSWORD)}.
- ChangeLoginRequest{login}; ChangeLoginResponse{result: EResult(OK/NOT_UNIQUE_LOGIN/WEAK_LOGIN)}.
- GetRestrictedConfigResponse{current_user: User{index, login, ...}, all_roles[RoleMeta], all_users[UserMeta]}.
- ChangeConfigRequest{added_users[User], modified_user_passwords[UserPasswordAssignment{user_index, password}],
  added_users_assignments[UserAssignment{user_id, role_id}], removed_users, removed_users_assignments, ...}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_security_credentials.py exposes check_password (read),
  change_my_password (gated write), change_my_login (gated write), with connect helper +
  ensure_client + _stub_and_pb2 + _write_gate matching bookmark_extras. Approval env
  AXXON_SECURITY_CREDENTIALS_APPROVE=1, confirmation token CONFIRM-security-credentials.
  change_my_password/change_my_login act on the connected session's own user and document
  that clearly (they do NOT take a user_id).
- AC2: change_my_password and change_my_login enforce the gate before any wire call: env-off
  -> {"status":"disabled"}; bad token -> {"status":"gap"}; empty password/login ->
  {"status":"error"}. check_password requires user_id+password else error. Unit tests assert
  client.calls==[] in each gated/empty case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_security_credentials_tools with @server.tool entries, --enable-security-credentials
  flag, flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: check_password returns NOT_UNIQUE for the current password and OK for
  an unused one; ChangePassword/ChangeLogin -> OK on a throwaway admin user that is created
  and then removed (ListUsers confirms gone). Raw transcript raw/live-verify.txt with
  host/creds sanitized.
- AC5: Corpus restamp marks CheckPassword, ChangePassword, ChangeLogin tested-pass; all 7
  LDAP methods (TestLDAPConnection, StartLDAPSynchronization, StopLDAPSynchronization,
  SearchLDAP, SearchLDAP2, SearchLDAPGroups, GetLDAPSynchronizationState) carry
  tested-warn-fixture-needed with honest citations (5 were previously pending). Dry-run after
  --write reports 0 restamped. Coverage doc updated; SecurityService 28/35 (no pending left).
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- The credential mutations are verified ONLY on a throwaway user, created and deleted within
  the verification; the shared root account is never modified.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>;
  do not commit any live password/login value (use generated throwaway values only, and
  redact them in the transcript).
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- Making the LDAP methods pass (no LDAP server on this stand).
- A generic admin-user-CRUD tool surface (user create/remove here is verification scaffolding
  only, not a shipped tool).
- Changing root or any real user's credentials.

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_security_credentials.py (read, gate, no-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript (throwaway-user round-trip) + restamp dry-run clean.
