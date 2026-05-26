# Phase 5F-B1 Security Admin Mutations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add approval-gated MCP operator workflows for temporary `codex-*` security/admin mutations.

**Architecture:** Keep Phase 5F-A read tools read-only. Add a separate `AxxonAdminMutationRegistry` with plan/apply/verify/rollback semantics, in-memory plan storage, strict `codex-*` target guards, and redacted audit/evidence output. Register the registry behind `--enable-admin-mutations` and `AXXON_ADMIN_MUTATION_APPROVE=1`.

**Tech Stack:** Python 3.12, `unittest`, existing `AxxonApiClient`, direct gRPC stubs for SecurityService, existing MCP server registration pattern.

---

## Execution Rules

- Work on `main` unless the user redirects.
- Use TDD for every code task: failing test first, then minimal implementation.
- Commit after every task.
- Do not push until the phase is fully verified, unless the user explicitly requests per-task pushes.
- Keep mutations scoped to generated or explicitly `codex-*` security fixtures.
- Do not implement license apply/drop, timezone/NTP mutation, production user/role mutation, LDAP sync against a real directory, or schedule authoring in 5F-B1.
- Live verification must use env-only credentials and must sanitize evidence before commit.

---

## Task 1: Add Admin Mutation Client Helpers

**Files:**
- Modify: `tools/axxon_api_client.py`
- Test: `tools/tests/test_axxon_api_client_admin_mutations.py`

### Step 1: Write failing wrapper tests

Create `tools/tests/test_axxon_api_client_admin_mutations.py`.

Test that the client exposes focused helpers for the mutation shapes reused by 5F-B1:

```python
def test_security_change_config_posts_change_config_payload():
    c = _FakeClient()
    c.security_change_config({"added_roles": [{"index": "role"}]})
    self.assertEqual(
        c.calls[0],
        (
            "axxonsoft.bl.security.SecurityService.ChangeConfig",
            {"added_roles": [{"index": "role"}]},
        ),
    )
```

Also cover:

- `security_set_global_permissions(role_id, permissions)`,
- `security_set_object_permissions(role_id, permissions)`,
- `security_set_groups_permissions(permissions)`,
- `security_set_macros_permissions(role_id, macros_access)`,
- `security_list_groups_permissions_info(role_id, page_size, page_token)`,
- `security_list_macros_permissions_paged(role_id, page_size, page_token)`,
- `security_get_ldap_synchronization()`,
- `security_get_ldap_synchronization_state()`,
- direct TFA helper availability for `GenGoogleAuthSecret`, `EnableGoogleAuth`, and `DisableGoogleAuth` if implemented as direct-stub methods.

### Step 2: Run the focused test and verify failure

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_api_client_admin_mutations
```

Expected: FAIL because wrappers are missing.

### Step 3: Implement minimal wrappers

Add thin wrappers near the existing Phase 5F-A security read wrappers in `tools/axxon_api_client.py`.

Keep request construction explicit and boring:

```python
def security_change_config(self, data: dict[str, Any]) -> dict[str, Any]:
    return self.http_grpc("axxonsoft.bl.security.SecurityService.ChangeConfig", dict(data))
```

For paged list helpers, include `page_token` only when non-empty.

For TFA, either:

- add direct stub helper methods that import `SecurityService_pb2` and call the stub, or
- leave raw direct-stub calls inside `AxxonAdminMutationRegistry` and test them there.

Do not add wrappers for license or timezone mutations in this task.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_api_client_admin_mutations
```

Expected: PASS.

### Step 5: Run baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Expected: `Ran 4xx tests ... OK`; no diff-check output.

Commit:

```bash
git add tools/axxon_api_client.py tools/tests/test_axxon_api_client_admin_mutations.py
git commit -m "feat: add admin mutation client helpers"
```

---

## Task 2: Scaffold Admin Mutation Registry

**Files:**
- Create: `tools/axxon_mcp_admin_mutations.py`
- Test: `tools/tests/test_axxon_mcp_admin_mutations.py`

### Step 1: Write failing scaffold tests

Create tests for:

- `AxxonAdminMutationRegistry(enabled=False)` lists workflows but rejects apply.
- Planning returns a plan id, workflow name, risk, apply confirmation token, rollback confirmation token, and sanitized params.
- Unknown workflow planning raises or returns `status: gap`.
- Audit entries redact passwords, TFA secrets/codes, bearer tokens, license keys, serials, and hardware fingerprints.

Example:

```python
def test_apply_rejects_when_registry_disabled():
    registry = module.AxxonAdminMutationRegistry(client_factory=lambda: fake, enabled=False)
    plan = registry.plan("security_user_role_lifecycle", {})
    result = registry.apply(plan["plan_id"], plan["confirmation_token"])
    self.assertEqual(result["status"], "rejected")
```

### Step 2: Verify failure

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: FAIL because the module does not exist.

### Step 3: Implement scaffold

Create:

- `ADMIN_MUTATION_APPROVE_ENV = "AXXON_ADMIN_MUTATION_APPROVE"`,
- `ADMIN_MUTATION_WORKFLOWS`,
- `AxxonAdminMutationRegistry`,
- `AdminMutationPlan` dataclass or plain plan dicts,
- `list_workflows`,
- `plan`,
- `apply`,
- `verify`,
- `rollback`,
- `audit_log`.

For this task, workflow handlers may return `status: fixture-needed` or `status: planned`; real mutations come later.

### Step 4: Run tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_admin_mutations.py tools/tests/test_axxon_mcp_admin_mutations.py
git commit -m "feat: scaffold admin mutation registry"
```

---

## Task 3: Implement `security_user_role_lifecycle`

**Files:**
- Modify: `tools/axxon_mcp_admin_mutations.py`
- Modify: `tools/tests/test_axxon_mcp_admin_mutations.py`

### Step 1: Write failing lifecycle tests

Use a fake security client with in-memory users, roles, assignments, and `change_config` calls.

Test:

- plan creates generated ids/names with `codex-*` or `codex_user_*`;
- apply calls ChangeConfig with added role, added user, assignment, and generated password assignment;
- apply never returns the generated password;
- verify confirms role/user/assignment presence;
- rollback removes assignment, user, and role;
- rollback cannot remove ids not created by the plan.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: FAIL on missing lifecycle implementation.

### Step 3: Implement lifecycle

Reuse logic from `tools/axxon_security_mutation_smoke.py`:

- UUID role id,
- UUID user id,
- `codex-role-*` name,
- `codex_user_*` login,
- in-memory generated password,
- ChangeConfig add payload,
- ChangeConfig rollback payload.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_admin_mutations.py tools/tests/test_axxon_mcp_admin_mutations.py
git commit -m "feat: add admin user role lifecycle workflow"
```

---

## Task 4: Implement Temp Role Permission Workflow

**Files:**
- Modify: `tools/axxon_mcp_admin_mutations.py`
- Modify: `tools/tests/test_axxon_mcp_admin_mutations.py`

### Step 1: Write failing permission tests

Test that `security_role_permissions_update`:

- rejects role names/ids that are not plan-created and do not start with `codex-`;
- applies restrictive global permissions to the target role;
- applies object, group, and macro permissions when fixture ids are available;
- reports counts and failed item counts only;
- rollback restores previous snapshot for pre-existing `codex-*` role or removes the plan-created role.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: FAIL on missing permission workflow.

### Step 3: Implement permission workflow

Use the request shapes proven in `SecurityMutationSmoke.run_permission_mutations`.

Keep outputs summarized:

```python
{
    "status": "applied",
    "role_id": "<role-id>",
    "global_role_present": True,
    "object_failed_count": 0,
    "group_permission_id_len": 36,
    "macro_permission_id_len": 36,
}
```

Do not return raw permission maps.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_admin_mutations.py tools/tests/test_axxon_mcp_admin_mutations.py
git commit -m "feat: add admin permission mutation workflow"
```

---

## Task 5: Implement Policy No-Op And LDAP Temp Lifecycle

**Files:**
- Modify: `tools/axxon_mcp_admin_mutations.py`
- Modify: `tools/tests/test_axxon_mcp_admin_mutations.py`

### Step 1: Write failing tests

For `security_policy_noop_probe`, test:

- reads current policies,
- writes the same password-policy/IP-filter/trusted-IP values,
- verifies counts unchanged,
- rejects caller-supplied policy payloads.

For `security_ldap_temp_lifecycle`, test:

- add temp loopback LDAP server,
- edit friendly name,
- remove temp LDAP server,
- verify absent after rollback/cleanup,
- never return bind password.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: FAIL on missing workflows.

### Step 3: Implement workflows

Use:

- current policy values from `security_get_policies`,
- `modified_pwd_policy`, `modified_ip_filters`, `modified_trusted_ip_list`,
- temp LDAP server fields from `SecurityMutationSmoke.temp_ldap_server`.

Keep sync/search out of this task.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_admin_mutations.py tools/tests/test_axxon_mcp_admin_mutations.py
git commit -m "feat: add admin policy and ldap workflows"
```

---

## Task 6: Implement Temp-User TFA Lifecycle

**Files:**
- Modify: `tools/axxon_mcp_admin_mutations.py`
- Modify: `tools/tests/test_axxon_mcp_admin_mutations.py`

### Step 1: Write failing TFA tests

Test:

- workflow creates or reuses a temp user created by the same plan;
- secret key and verification codes are kept out of plan/apply/verify/rollback outputs;
- enable result enum is summarized;
- disable tries current, previous, and next TOTP windows;
- rollback removes the temporary user/role even if TFA disable fails.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: FAIL on missing TFA workflow.

### Step 3: Implement TFA workflow

Reuse:

- `totp_code`,
- `tfa_verification_codes`,
- `GenGoogleAuthSecret`,
- `EnableGoogleAuth`,
- `DisableGoogleAuth`,
- temp user cleanup.

Return only:

- secret length,
- enum result names,
- disable attempt count,
- cleanup status.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_admin_mutations
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_admin_mutations.py tools/tests/test_axxon_mcp_admin_mutations.py
git commit -m "feat: add admin tfa mutation workflow"
```

---

## Task 7: Register MCP Server Tools

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

### Step 1: Write failing registration tests

Add a `StubAdminMutator` to `tools/tests/test_axxon_mcp_server.py`.

Assert:

- admin mutation tools are not registered by default;
- `create_server(..., admin_mutator=StubAdminMutator())` registers all five tools and audit resource;
- parser accepts `--enable-admin-mutations`;
- wrapper signatures pass through workflow, params, plan id, and confirmation.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_server
```

Expected: FAIL because server registration is missing.

### Step 3: Implement registration

Add:

- `admin_mutator` parameter to `create_server`,
- `register_admin_mutation_tools`,
- `--enable-admin-mutations`,
- env approval wiring in `main`.

Use `AXXON_ADMIN_MUTATION_APPROVE=1` for the enabled flag.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_mcp_server
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_mcp_server.py tools/tests/test_axxon_mcp_server.py
git commit -m "feat: register admin mutation tools"
```

---

## Task 8: Add Live Admin Mutation Smoke

**Files:**
- Create: `tools/axxon_admin_mutation_smoke.py`
- Test: `tools/tests/test_axxon_admin_mutation_smoke.py`

### Step 1: Write failing smoke tests

Test:

- parser rejects CLI credential flags and requires env/config credentials;
- parser requires `--i-understand-this-mutates`;
- parser requires `--confirm CONFIRM-admin-mutation-smoke`;
- evidence sanitizer replaces concrete host/user/CA, passwords, bearer tokens, TFA secret/codes, role/user ids, emails, license/serial/hardware fields;
- fake tool run writes latest JSON and markdown reports with PASS/WARN/FAIL summary.

### Step 2: Run failing tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_admin_mutation_smoke
```

Expected: FAIL because smoke is missing.

### Step 3: Implement smoke

Smoke sequence:

1. connect registry/client,
2. plan/apply/verify/rollback `security_user_role_lifecycle`,
3. plan/apply/verify/rollback `security_role_permissions_update`,
4. plan/apply/verify/rollback `security_policy_noop_probe`,
5. plan/apply/verify/rollback `security_ldap_temp_lifecycle`,
6. plan/apply/verify/rollback `security_tfa_temp_user_lifecycle`,
7. write `phase-5f-b-admin-mutation-smoke-latest.{json,md}`.

### Step 4: Run focused tests

Run:

```bash
python3.12 -m unittest tools.tests.test_axxon_admin_mutation_smoke
```

Expected: PASS.

### Step 5: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add tools/axxon_admin_mutation_smoke.py tools/tests/test_axxon_admin_mutation_smoke.py
git commit -m "feat: add admin mutation live smoke"
```

---

## Task 9: Live Verify Against Demo Stand

**Files:**
- Create: `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.json`
- Create: `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md`

### Step 1: Export env-only credentials

Use local shell environment only:

```bash
export AXXON_HOST=<demo-host>
export AXXON_HTTP_URL=http://<demo-host>
export AXXON_USERNAME=<demo-user>
export AXXON_PASSWORD=<redacted>
export AXXON_TLS_CN=<demo-tls-cn>
export AXXON_CA=<redacted-ca-path>
export AXXON_ADMIN_MUTATION_APPROVE=1
```

Do not commit these values.

### Step 2: Run live smoke

Run:

```bash
python3.12 tools/axxon_admin_mutation_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-admin-mutation-smoke
```

Expected: FAIL=0. WARN is acceptable only for fixture-gated LDAP sync/search, not for temp object rollback.

### Step 3: Inspect and sanitize evidence

Run a targeted scan over the latest files:

```bash
rg -n "100[.]76[.]150[.]18|AXXON_PASS[W]ORD=|pass(?:word)=root|pass(?:word): root|Bearer [A-Za-z0-9_.-]{12,}|/Users/[^[:space:]\"']+\\.crt|licen(?:se)[_ -]?key|serial[_ -]?num(?:ber)|hard(?:ware)[_ -]?fingerprint" docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.*
```

Expected: no matches.

Also manually check the markdown summary for:

- no concrete host/user/CA path,
- no generated password,
- no TFA secret,
- no TFA verification code,
- no bearer token.

### Step 4: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.json docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md
git commit -m "test: add phase 5f b admin mutation evidence"
```

---

## Task 10: Update Docs And Coverage Matrix

**Files:**
- Modify: `README.md`
- Modify: `STATUS.md`
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `docs/api-audit/mutation-playbooks/users-roles-security.md`
- Modify: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`

### Step 1: Update docs

Document:

- new `--enable-admin-mutations` flag,
- five admin mutation workflows,
- approval env var,
- confirmation-token model,
- live evidence path,
- fixture caveats,
- deferred 5F-B2 scope.

Update the roadmap and status handoff so the next step moves to either Phase 5F-B2 or Phase 6A, depending on remaining fixture debt.

### Step 2: Run docs hygiene

Run:

```bash
git diff --check
rg -n "100[.]76[.]150[.]18|AXXON_PASS[W]ORD=|pass(?:word)=root|pass(?:word): root|Bearer [A-Za-z0-9_.-]{12,}|/Users/[^[:space:]\"']+\\.crt|licen(?:se)[_ -]?key|serial[_ -]?num(?:ber)|hard(?:ware)[_ -]?fingerprint" README.md STATUS.md docs/api-audit/pdf-gap-coverage-matrix.md docs/api-audit/mutation-playbooks/users-roles-security.md docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md
```

Expected: no real-value matches. Placeholder examples are acceptable only when they do not include real credentials.

### Step 3: Baseline and commit

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Commit:

```bash
git add README.md STATUS.md docs/api-audit/pdf-gap-coverage-matrix.md docs/api-audit/mutation-playbooks/users-roles-security.md docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md
git commit -m "docs: document phase 5f b admin mutations"
```

---

## Task 11: Final Verification And Push

**Files:** none expected

### Step 1: Run final verification

Run:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
git status --short
```

Expected:

- full unit suite OK,
- no whitespace errors,
- clean worktree.

### Step 2: Final secret scan

Run over all changed source/docs/evidence:

```bash
git diff --name-only origin/main..HEAD | xargs rg -n "100[.]76[.]150[.]18|AXXON_PASS[W]ORD=|pass(?:word)=root|pass(?:word): root|Bearer [A-Za-z0-9_.-]{12,}|/Users/[^[:space:]\"']+\\.crt|licen(?:se)[_ -]?key|serial[_ -]?num(?:ber)|hard(?:ware)[_ -]?fingerprint"
```

Expected: no real-value matches. If the command exits 123 because no files are passed or `rg` returns no matches, rerun with explicit filenames.

### Step 3: Push main

Run:

```bash
git push origin main
```

Expected: `main -> main`.
