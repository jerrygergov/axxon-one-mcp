# Task Spec: phase-5f-b2-prod-role-edit

## Metadata
- Task ID: phase-5f-b2-prod-role-edit
- Created: 2026-05-29T14:37:37+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- AGENTS.md
- CLAUDE.md

## Original task statement
Implement the safely-reversible slice of Phase 5F-B2: production user/role edits. Add an admin mutation workflow security_production_role_edit_lifecycle that snapshots an existing PRODUCTION role (by name/index), pushes a modified_roles ChangeConfig changing only the cosmetic comment field while preserving every other field, verifies the comment changed, then restores the exact original Role record (rollback) and verifies full restoration. Live-proved against the stand on the operator role: edit landed, restored==original byte-for-byte. Same approval gates as 5F-B1 (--enable-admin-mutations, AXXON_ADMIN_MUTATION_APPROVE=1, CONFIRM tokens). Add to ADMIN_MUTATION_WORKFLOWS, plan/apply/verify/rollback dispatch, the smoke, unit tests, and evidence. Timezone/NTP and license apply/drop stay deferred (user decision). schedule authoring stays fixture-needed.

## Acceptance criteria
- AC1: New workflow `security_production_role_edit_lifecycle` in ADMIN_MUTATION_WORKFLOWS with plan/apply/verify/rollback dispatch; plan snapshots an existing production role (by `role_name` or `role_index`) and stores the full original Role record.
- AC2: apply pushes `modified_roles` changing only the cosmetic `comment` to a `codex-*` marker, preserving every other field; verify confirms the new comment is present on the role.
- AC3: rollback pushes `modified_roles` restoring the exact captured original record; a post-rollback verify confirms the role matches the original byte-for-byte (full restore, no residue).
- AC4: Same gates as 5F-B1 (`--enable-admin-mutations`, `AXXON_ADMIN_MUTATION_APPROVE=1`, CONFIRM apply/rollback tokens); apply rejected without env+token.
- AC5: Unit tests cover plan/apply/verify/rollback with a fake client; full suite stays green. Live smoke proves the round-trip on the `operator` role and is recorded in sanitized evidence.

## Constraints
- Production role edit must be fully reversible; restore the captured original record exactly.
- Only the `comment` field is mutated; never touch restrictions, name, or assignments.
- Direct gRPC/CA/proto symlink never committed; evidence sanitized.

## Non-goals
- Production user (account) edits, password/login changes: roles are lower-risk than live operator accounts; this slice covers role comment edits only.
- Timezone/NTP changes and license apply/drop (deferred per user decision).
- LDAP sync against a real directory; schedule authoring (fixture-needed).

## Verification plan
- Build: extend `tools/axxon_mcp_admin_mutations.py` + smoke `tools/axxon_admin_mutation_smoke.py`.
- Unit tests: `python3.12 -m unittest discover -s tools/tests`.
- Integration tests: `python3.12 tools/axxon_admin_mutation_smoke.py --enable-admin-mutations` against the stand (CN=Server) with approval env.
- Manual checks: operator-role comment edit lands and restores to original.
