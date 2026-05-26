# Phase 5F-B1 Security Admin Mutations Design

**Date:** 2026-05-26
**Status:** Approved for implementation planning
**Branch:** `main`

---

## Goal

Promote the proven security/admin mutation smoke into bounded MCP operator workflows for temporary `codex-*` users, roles, permissions, LDAP configuration, policy no-op safety, and temporary-user TFA lifecycle.

This is the first mutation half of Phase 5F-B. It intentionally excludes license application/drop, timezone changes, NTP changes, and production user/role edits.

---

## Ground Truth

- `main` includes Phase 5F-A at `64d6477`.
- Baseline test runner: `python3.12 -m unittest discover -s tools/tests`.
- Current baseline: 434 tests.
- Phase 5F-A read evidence: `docs/api-audit/phase-5f-admin-smoke-latest.md`.
- Existing security mutation evidence: `docs/api-audit/security-mutation-smoke-latest.md`.
- Existing mutation playbook: `docs/api-audit/mutation-playbooks/users-roles-security.md`.
- Existing direct smoke implementation: `tools/axxon_security_mutation_smoke.py`.

The security mutation smoke already verified a full temporary lifecycle on the demo stand: create a UUID-indexed `codex-*` role/user, set an in-memory generated password, assign the role, update temp-role permissions, replay password-policy/IP-filter/trusted-IP config as no-op writes, add/edit/remove a temporary LDAP server, enable/disable TFA on the temporary user, and rollback to baseline counts.

---

## Design Choice

Use a staged Phase 5F-B.

**5F-B1, this design:** MCP operator workflows for controlled security/admin mutations that only touch generated or explicitly `codex-*` fixtures.

**5F-B2, later:** maintenance-window workflows for license apply/drop, timezone, NTP, LDAP sync against a real directory, and production user/role changes.

This keeps the shipped MCP useful while preserving the project safety model: read-only by default, mutations behind explicit enable flags, plan/apply/verify/rollback, per-call confirmation tokens, and sanitized evidence.

---

## MCP Shape

Create a new module, `tools/axxon_mcp_admin_mutations.py`, instead of mixing high-risk mutation behavior into the Phase 5F-A read-only `tools/axxon_mcp_admin.py`.

Register it in `tools/axxon_mcp_server.py` behind a new flag:

```bash
python tools/axxon_mcp_server.py --enable-admin-mutations --transport stdio
```

The flag constructs an `AxxonAdminMutationRegistry` only when:

```bash
AXXON_ADMIN_MUTATION_APPROVE=1
```

Public MCP tools:

- `list_admin_mutation_workflows()`
- `plan_admin_mutation_workflow(workflow, params)`
- `apply_admin_mutation_plan(plan_id, confirmation)`
- `verify_admin_mutation_plan(plan_id)`
- `rollback_admin_mutation_plan(plan_id, confirmation)`

Add an audit resource:

- `axxon://admin-mutations/audit-log`

---

## Workflows

### `security_user_role_lifecycle`

Creates a temporary role and user, sets an in-memory generated password, assigns the role, verifies presence and assignment, and rolls back assignment, user, and role.

Rules:

- Generated role names use `codex-role-*`.
- Generated logins use `codex_user_*`.
- Generated passwords never leave memory and never appear in plans, audit entries, or evidence.
- Rollback removes only ids created by the plan.

### `security_role_permissions_update`

Creates or requires a temp `codex-*` role and applies restrictive global/object/group/macro permissions to that role only. The workflow stores a sanitized previous snapshot when the target role already exists, then rollback restores that snapshot.

Rules:

- Reject non-`codex-*` roles unless the role id was created by the same in-memory plan.
- Report only permission counts, selected object id lengths, and failed entry counts.
- Do not persist raw permission payloads that might expose private object names.

### `security_policy_noop_probe`

Reads current password-policy, IP-filter, and trusted-IP config, writes the same values back, then verifies counts are unchanged.

Rules:

- This is still a mutation and requires approval.
- It does not accept caller-supplied policy payloads in 5F-B1.
- Evidence stores counts only.

### `security_ldap_temp_lifecycle`

Adds a temporary LDAP server record using loopback/non-production values, edits its friendly name, removes it, and verifies it is gone.

Rules:

- LDAP bind password is generated in memory.
- Server names are loopback/test values only.
- LDAP sync/search stays fixture-needed without a real directory fixture.

### `security_tfa_temp_user_lifecycle`

Creates a temporary user if needed, generates a Google Auth secret, enables TFA on that temporary user, disables it using an in-memory TOTP code, and rolls back the temp user/role.

Rules:

- Secret keys and verification codes never appear in plan/audit/evidence.
- Evidence may include `secret_len`, enum results, and disable attempt count.
- Only temp users created by the same plan are eligible.

---

## Deferred Scope

Do not implement these in 5F-B1:

- production `user_create`, `user_update`, `user_delete`, `change_password`, or `change_login`;
- production role/permission edits outside `codex-*` fixtures;
- LDAP synchronization start/stop against a real directory;
- license apply/drop/document generation;
- timezone, timezone list mutation, or NTP update;
- schedule authoring.

The implementation may add explicit fixture-needed/deferred documentation for these, but it must not register mutating MCP tools for them in 5F-B1.

---

## API And Transport

Reuse `AxxonApiClient` for shared configuration, authentication, direct gRPC stubs, and HTTP `/grpc` helpers.

Phase 5F-B1 can use direct gRPC for mutation shapes that already work in `tools/axxon_security_mutation_smoke.py`, especially TFA. Thin client helpers should only hide repeated request construction or stub discovery; they should not hide approval checks.

Any mutation result passed back to MCP must go through the admin redaction rules before it is returned, written to audit, or included in evidence.

---

## Safety Model

All mutation workflows must enforce:

- server startup flag: `--enable-admin-mutations`,
- environment approval: `AXXON_ADMIN_MUTATION_APPROVE=1`,
- plan ids generated before apply,
- per-plan apply confirmation token,
- per-plan rollback confirmation token,
- apply rejects unknown, expired, or already-applied plan ids,
- rollback rejects unknown plans and mismatched tokens,
- target ids/names must be generated by the plan or start with `codex-`,
- cleanup attempts run after failed live smokes,
- audit entries never include passwords, TFA secrets/codes, bearer tokens, license keys, serials, CA paths, or concrete demo host/user values.

---

## Live Verification

Create `tools/axxon_admin_mutation_smoke.py`.

Default mode:

- refuses to run without `AXXON_ADMIN_MUTATION_APPROVE=1`,
- refuses to run without `--i-understand-this-mutates`,
- requires `--confirm CONFIRM-admin-mutation-smoke`,
- runs only temporary `codex-*` workflows,
- writes sanitized latest evidence to `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.{json,md}`.

Expected live groups:

- `security_user_role_lifecycle`,
- `security_role_permissions_update`,
- `security_policy_noop_probe`,
- `security_ldap_temp_lifecycle`,
- `security_tfa_temp_user_lifecycle`.

The smoke must fail if rollback leaves the temporary user, role, assignment, LDAP server, or TFA state behind.

---

## Documentation Updates

At the end of implementation:

- update `README.md`,
- update `STATUS.md`,
- update `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`,
- update `docs/api-audit/pdf-gap-coverage-matrix.md`,
- update `docs/api-audit/mutation-playbooks/users-roles-security.md`,
- add sanitized live evidence.

---

## Definition Of Done

- `--enable-admin-mutations` registers only the five controlled admin mutation MCP tools and does not register them by default.
- Offline tests cover disabled approval, confirmation tokens, plan/apply/verify/rollback, `codex-*` guardrails, redaction, cleanup, and server registration.
- The live smoke runs against the demo stand with env-only credentials and sanitized evidence.
- No production user/role, license, timezone, NTP, schedule, or real LDAP sync mutation is exposed in 5F-B1.
- Full suite passes with `python3.12 -m unittest discover -s tools/tests`.
