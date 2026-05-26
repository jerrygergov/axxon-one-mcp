# Phase 5F-A Security / System Health / Schedules Design

**Date:** 2026-05-26
**Status:** Ready for implementation
**Branch:** `codex/phase-5f-security-health-schedules`

---

## Goal

Ship the read-first half of Phase 5F: security inventory, policy and permission summaries, current-user context, license/time/system-health status, bounded DomainNotifier/NodeNotifier subscriptions, and fixture-aware schedule discovery.

Phase 5F-B will promote users/roles/permissions/LDAP/TFA/license/timezone mutations after 5F-A is merged.

---

## Ground Truth

- Phase 5E is merged to `main` at `62a4b9b`.
- Baseline test runner: `python3.12 -m unittest discover -s tools/tests`; current baseline is 386 tests.
- Existing security read evidence: `docs/api-audit/security-admin-preflight-latest.md`.
- Existing security mutation evidence: `docs/api-audit/security-mutation-smoke-latest.md`.
- Existing aux read evidence: `docs/api-audit/aux-topics-smoke-latest.md`.
- Existing safety playbook: `docs/api-audit/mutation-playbooks/users-roles-security.md`.
- Local proto files are gitignored. Use the repo-local `docs/grpc-proto-files/` directory when it is present in the active checkout.

---

## Design Choice

Use a two-step Phase 5F.

**5F-A, this plan:** read-only and bounded-stream tools. This gives customers a system-health/admin overview without introducing high-risk security mutations into the same branch.

**5F-B, later:** controlled operator workflows for users, roles, permissions, LDAP, TFA, license, timezone, and NTP changes.

This follows the project posture: read-only by default, mutating behavior only after explicit plan/apply/verify/rollback design.

---

## MCP Module

Create `tools/axxon_mcp_admin.py`.

Public read tools:

- `admin_connect_axxon_profile(profile="env")`
- `security_inventory(include_users=True, include_roles=True, include_ldap=True, page_size=100)`
- `security_policy_summary()`
- `role_permissions(role_id, page_size=50)`
- `current_user_security()`
- `license_status(include_host_info=True, include_node_restrictions=True, node_names=None, limit=32)`
- `time_status(include_available=True)`
- `system_health(include_security=True, include_license=True, include_time=True, include_archive=True)`
- `domain_event_subscribe(subjects=None, event_types=None, timeout_s=5.0, limit=25, detailed=False)`
- `node_event_subscribe(subjects=None, event_types=None, timeout_s=5.0, limit=25, detailed=False)`
- `schedule_descriptor_get(uid)`

Register these behind `--enable-admin` in `tools/axxon_mcp_server.py`.

---

## Data Handling

Security, license, and host data must be summarized by default.

Redact:

- passwords and password policy values where they include secrets,
- bearer tokens and session ids,
- TFA secret keys and verification codes,
- license keys and serial-like fields,
- hardware or host fingerprints,
- raw LDAP bind passwords,
- concrete demo host/user/CA values in evidence.

`hosts/Server/...` UIDs may remain when they are intrinsic access-point identifiers and not credential material.

---

## API Surface

Add thin wrappers in `tools/axxon_api_client.py` only where repeated request construction would otherwise leak transport details into the MCP module.

Expected wrappers:

- security read wrappers for roles, users, LDAP servers, policies, restricted config, user permissions, and role permission pages,
- auth session wrappers for `GetSessionInfo`, isolated `RenewSession`, isolated `RenewSession2`, and isolated `CloseSession`,
- license wrappers for global restrictions, domain license info, node restrictions, launch possibility, license key info, and host info,
- timezone wrappers for `GetTimeZone`, `ListTimeZones`, `BatchGetZones`, and `GetNTP`,
- a generalized notifier pull wrapper for DomainNotifier and NodeNotifier with hard timeout/event caps and disconnect cleanup.

Keep direct mutation wrappers out of 5F-A unless a read helper requires a no-op or isolated session lifecycle.

---

## Schedule Scope

No standalone schedule service appears in the current corpus or proto scan. Phase 5F-A therefore treats schedules as descriptor-backed configuration fields:

- expose discovered schedule-like fields through `schedule_descriptor_get(uid)`,
- reuse Phase 5E descriptor categorization for `schedule`, `calendar`, `weekly`, and `daily`,
- return `fixture-needed` when no descriptor exposes writable schedule fields,
- do not mutate schedule fields in 5F-A.

Archive calendar is already covered by Phase 5A/aux evidence and remains a read tool dependency, not schedule authoring.

---

## Live Verification

Create `tools/axxon_admin_smoke.py`.

Default read-only smoke:

- connect,
- security inventory,
- policy summary,
- permission summary for an existing role,
- current user,
- license status,
- time status,
- system health,
- bounded DomainNotifier pull,
- schedule descriptor probe.

Optional `--include-node-notifier`:

- bounded NodeNotifier pull and disconnect.

No 5F-A smoke writes security config, changes license state, changes timezone/NTP, or pushes diagnostic events.

---

## Fixture Caveats

- Demo stand currently has zero LDAP servers; LDAP sync/search stays fixture-needed.
- TFA mutation is proven by the old smoke but remains 5F-B because it is a security mutation and exposes OTP policy decisions.
- License reads may expose sensitive host/license fields unless aggressively summarized.
- NodeNotifier may be quiet on a small demo stand; bounded streams can pass with zero events if subscription setup/cleanup succeeds.
- Schedule descriptor discovery may return fixture-needed until an isolated archive/config fixture exposes schedule fields.

---

## Definition Of Done

- `--enable-admin` registers all 5F-A tools and does not register them by default.
- Offline tests cover pagination, redaction, cap clamping, notifier disconnect cleanup, and fixture-needed schedule behavior.
- Live read-only smoke runs against the demo stand and produces sanitized evidence.
- Coverage matrix, roadmap, README, and STATUS are updated.
- Full suite passes with `python3.12 -m unittest discover -s tools/tests`.
