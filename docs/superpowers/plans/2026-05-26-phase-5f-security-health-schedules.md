# Phase 5F-A Security / System Health / Schedules Implementation Plan

> **For Claude/Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Goal:** Add read-only MCP tools for security inventory, system health, license/time status, bounded notifier streams, and schedule descriptor discovery.

**Architecture:** Add a new `AxxonMcpAdmin` module that composes thin `AxxonApiClient` wrappers and existing redaction/sanitization patterns. Register the tools behind `--enable-admin`. Keep admin mutations out of this plan; they belong to Phase 5F-B.

**Tech Stack:** Python 3.12, unittest, direct gRPC stubs, HTTP `/grpc`, existing `AxxonApiClient`, existing FastMCP registration pattern.

---

## Task 1: Add admin API wrappers

**Files:**
- Modify: `tools/axxon_api_client.py`
- Create or modify tests: `tools/tests/test_axxon_api_client_admin.py`

Steps:

1. Write failing wrapper tests for:
   - `security_list_roles`
   - `security_list_users`
   - `security_list_ldap_servers`
   - `security_get_policies`
   - `security_get_restricted_config`
   - `security_list_global_permissions`
   - `security_list_object_permissions_info`
   - `license_get_global_restrictions`
   - `license_get_domain_key_info`
   - `license_get_host_info`
   - `time_get_time_zone`
   - `time_get_ntp`
2. Run:
   ```bash
   python3.12 -m unittest tools.tests.test_axxon_api_client_admin -v
   ```
   Expected: fail because wrappers do not exist.
3. Implement minimal thin wrappers using existing `import_module`, `stub_from_proto`, `http_grpc`, and `message_to_dict` patterns.
4. Run the focused test until green.
5. Commit:
   ```bash
   git add tools/axxon_api_client.py tools/tests/test_axxon_api_client_admin.py
   git commit -m "feat: add admin API wrappers"
   ```

## Task 2: Scaffold `AxxonMcpAdmin`

**Files:**
- Create: `tools/axxon_mcp_admin.py`
- Create: `tools/tests/test_axxon_mcp_admin.py`

Steps:

1. Write failing tests for:
   - module constants,
   - `admin_connect_axxon_profile`,
   - redaction helper for passwords, bearer tokens, TFA secrets, license keys, serials, and hardware identifiers.
2. Run:
   ```bash
   python3.12 -m unittest tools.tests.test_axxon_mcp_admin -v
   ```
3. Implement dataclass scaffold with `client_factory`, `config_factory`, `ensure_client`, profile summary, and redaction helpers.
4. Run focused tests until green.
5. Commit:
   ```bash
   git add tools/axxon_mcp_admin.py tools/tests/test_axxon_mcp_admin.py
   git commit -m "feat: scaffold admin MCP tools"
   ```

## Task 3: Security inventory and policy tools

**Files:**
- Modify: `tools/axxon_mcp_admin.py`
- Modify: `tools/tests/test_axxon_mcp_admin.py`

Tools:
- `security_inventory`
- `security_policy_summary`
- `role_permissions`
- `current_user_security`

Steps:

1. Write failing tests for paginated role/user/LDAP summaries, policy summary with LDAP state warning, permission summaries, and current-user restricted config.
2. Verify tests fail.
3. Implement the four tools with sanitized summaries only. Do not return full raw user records by default.
4. Run:
   ```bash
   python3.12 -m unittest tools.tests.test_axxon_mcp_admin -v
   ```
5. Commit:
   ```bash
   git add tools/axxon_mcp_admin.py tools/tests/test_axxon_mcp_admin.py
   git commit -m "feat: add admin security read tools"
   ```

## Task 4: License, time, and system health tools

**Files:**
- Modify: `tools/axxon_mcp_admin.py`
- Modify: `tools/tests/test_axxon_mcp_admin.py`

Tools:
- `license_status`
- `time_status`
- `system_health`

Steps:

1. Write failing tests for license redaction, node-restriction bounds, time/NTP summary, and system-health aggregation.
2. Verify tests fail.
3. Implement the three tools. `system_health` should compose security/license/time/archive/session summaries and mark missing fixture sections as `fixture-needed` instead of failing the whole response.
4. Run focused tests.
5. Commit:
   ```bash
   git add tools/axxon_mcp_admin.py tools/tests/test_axxon_mcp_admin.py
   git commit -m "feat: add admin health tools"
   ```

## Task 5: Bounded notifier tools and schedule descriptor discovery

**Files:**
- Modify: `tools/axxon_api_client.py`
- Modify: `tools/axxon_mcp_admin.py`
- Modify: `tools/tests/test_axxon_api_client_admin.py`
- Modify: `tools/tests/test_axxon_mcp_admin.py`

Tools:
- `domain_event_subscribe`
- `node_event_subscribe`
- `schedule_descriptor_get`

Steps:

1. Write failing tests for:
   - cap clamping,
   - DomainNotifier service selection,
   - NodeNotifier service selection,
   - disconnect on normal completion,
   - disconnect on stream error,
   - schedule field discovery,
   - fixture-needed result when no schedule-like fields exist.
2. Verify tests fail.
3. Implement a generalized bounded notifier wrapper and the three MCP tools.
4. Run focused tests.
5. Commit:
   ```bash
   git add tools/axxon_api_client.py tools/axxon_mcp_admin.py tools/tests/test_axxon_api_client_admin.py tools/tests/test_axxon_mcp_admin.py
   git commit -m "feat: add admin notifier and schedule tools"
   ```

## Task 6: Register `--enable-admin`

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

Steps:

1. Write failing tests proving admin tools are absent by default and present with `admin=StubAdmin`.
2. Add parser flag `--enable-admin`.
3. Add `register_admin_tools`.
4. Wire `AxxonMcpAdmin()` in `main()` when `--enable-admin` is set.
5. Run:
   ```bash
   python3.12 -m unittest tools.tests.test_axxon_mcp_server -v
   ```
6. Commit:
   ```bash
   git add tools/axxon_mcp_server.py tools/tests/test_axxon_mcp_server.py
   git commit -m "feat: register admin MCP tools"
   ```

## Task 7: Add Phase 5F-A live smoke

**Files:**
- Create: `tools/axxon_admin_smoke.py`
- Create: `tools/tests/test_axxon_admin_smoke.py`

Steps:

1. Write failing tests for CLI defaults, cap bounds, `--include-node-notifier`, report sanitization, and no abbreviated credential flags.
2. Implement read-only smoke:
   - connect,
   - security inventory,
   - policy summary,
   - role permissions for a discovered role,
   - current user,
   - license status,
   - time status,
   - system health,
   - DomainNotifier bounded pull,
   - schedule descriptor probe.
3. Add optional NodeNotifier bounded pull behind `--include-node-notifier`.
4. Run focused tests.
5. Commit:
   ```bash
   git add tools/axxon_admin_smoke.py tools/tests/test_axxon_admin_smoke.py
   git commit -m "feat: add admin live smoke"
   ```

## Task 8: Run live verification and commit sanitized evidence

**Files:**
- Create: `docs/api-audit/phase-5f-admin-smoke-latest.md`
- Create: `docs/api-audit/phase-5f-admin-smoke-latest.json`

Steps:

1. Run the read-only smoke against the demo stand with env-only credentials.
2. If safe, run `--include-node-notifier`.
3. Sanitize evidence:
   - concrete host -> `<demo-host>`,
   - concrete user -> `<demo-user>`,
   - passwords/tokens/TFA/license/serial/hardware ids -> `<redacted>`,
   - CA paths -> `<redacted-ca>`.
4. Run a secret scan over the new evidence.
5. Commit:
   ```bash
   git add docs/api-audit/phase-5f-admin-smoke-latest.md docs/api-audit/phase-5f-admin-smoke-latest.json
   git commit -m "test: add phase 5f admin live evidence"
   ```

## Task 9: Update docs and coverage matrix

**Files:**
- Modify: `README.md`
- Modify: `STATUS.md`
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`

Steps:

1. Document `--enable-admin` and the 5F-A tools.
2. Add/update the Phase 5F matrix row.
3. Update current test count.
4. Update next concrete step to Phase 5F-B planning after 5F-A is complete.
5. Run full suite and secret scan over changed docs/evidence.
6. Commit:
   ```bash
   git add README.md STATUS.md docs/api-audit/pdf-gap-coverage-matrix.md docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md
   git commit -m "docs: document phase 5f admin coverage"
   ```

## Task 10: Final verification

**Files:** none expected

Steps:

1. Run:
   ```bash
   python3.12 -m unittest discover -s tools/tests
   git diff --check
   git status --short
   ```
2. Run final secret scan over changed source/docs/evidence.
3. Request final spec and code-quality review.
4. Commit only if verification requires tracked docs/evidence changes.

---

## Execution Notes

- Do not implement Phase 5F-B mutations in this plan.
- Do not commit local proto files or copyrighted PDFs.
- Do not store passwords, bearer tokens, license keys, TFA secrets, serials, or raw hardware identifiers in evidence.
- Treat quiet notifier streams as acceptable if subscription setup, cap enforcement, and disconnect cleanup are verified.
