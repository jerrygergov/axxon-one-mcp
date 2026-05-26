# Mutation Playbook: Users, Roles, And Security Policy

- PDF pages: 449-463.
- APIs involved: user/role create/edit/remove, permissions, security policy, IP filters, LDAP changes, and temporary-user TFA enable/disable.
- Fixture requirements: non-root test user/role prefixed `codex-`; isolated role with no production permissions.
- Preflight read snapshot: role/user counts and sanitized shape; never store password or full policy payload.
- Mutation request: create or edit only the `codex-` user/role.
- Verification command: list users/roles and verify count/id.
- Rollback request: remove `codex-` assignments, user, and role.
- Post-rollback verification: list users/roles and verify baseline counts/shapes.
- Read-only preflight result: `security-admin-preflight-latest.md` verifies users/roles, policies, global/group/object/macro permission summaries, and restricted config without storing full security payloads. The demo stand has 4 roles, 35 users, 0 LDAP servers, 1 password policy, 0 IP filters, 0 trusted IPs, 36 object-permission info rows, 1 group-permission info row, and 16 macro-permission rows.
- Controlled mutation result: `security-mutation-smoke-latest.md` verifies temporary UUID-indexed `codex-*` role/user create, generated in-memory password set, assignment, temp-role global/object/group/macro permission updates, no-op password-policy/IP-filter/trusted-IP writes from the current snapshot, temporary LDAP directory add/edit/remove, and rollback to baseline role/user/LDAP counts.
- MCP admin mutation result: `phase-5f-b-admin-mutation-smoke-latest.md` verifies the approval-gated MCP plan/apply/verify/rollback workflows for temporary user/role lifecycle, temp-role permission updates, policy no-op replay, temporary LDAP add/edit/remove, and temporary-user TFA enable/disable. Reports include only secret lengths/result enums/counts and redact generated passwords, TFA secrets, verification codes, bearer tokens, concrete host/user/CA values, licensing identifiers, and device identifiers.
- Fixture warning: `GetLDAPSynchronizationState` returns `UNAVAILABLE: Can't get connection channel!` on the demo stand when no LDAP servers are configured. Treat LDAP search/sync examples as fixture-needed.
- Risk level: high.
- Approval requirement: `--enable-admin-mutations`, `AXXON_ADMIN_MUTATION_APPROVE=1`, a plan id, a workflow-specific apply confirmation token, and a separate rollback confirmation token.
- Deferred scope: production user/role edits, LDAP sync against a real directory, license apply/drop, timezone/NTP changes, and schedule authoring require a dedicated fixture or maintenance-window plan outside Phase 5F-B1.
