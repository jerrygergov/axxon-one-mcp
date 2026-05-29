# Task Spec: phase-5e-archive-policy

## Metadata
- Task ID: phase-5e-archive-policy
- Created: 2026-05-29T13:49:49+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- AGENTS.md
- CLAUDE.md

## Original task statement
Close the Phase 5E archive_policy_get WARN. Root cause: the tool already returns status ok with retention (day_depth) and archive_bindings (storage_type) when given the top-level MultimediaStorage archive unit UID (hosts/Server/MultimediaStorage.AliceBlue). The WARN came only because the smoke axxon_detector_archive_smoke.py archive_policy_target() picked the first inventory archive entry, an embedded device storage (hosts/Server/DeviceIpint.5/MultimediaStorage.0) that is not a standalone config unit. Fix: make archive_policy_target prefer a top-level MultimediaStorage.<name> archive access point. Verify live the smoke records archive_policy_get as ok (not WARN). Refresh phase-5e evidence and corpus.

## Acceptance criteria
- AC1: `axxon_detector_archive_smoke.py` `archive_policy_target()` prefers a top-level `MultimediaStorage.<name>` archive access point (a standalone config unit) over embedded device storages (`DeviceIpint.N/MultimediaStorage.0`).
- AC2: A live read-only smoke run records `archive_policy_get` with `status: ok` (not WARN), exposing at least one retention property (`day_depth`) and one archive binding.
- AC3: All existing `tools/tests` stay green (>=500). New unit coverage for the target-selection preference.
- AC4: Phase 5E evidence (`docs/api-audit/phase-5e-detector-archive-smoke-latest.md`) refreshed: `archive_policy_get` row moves from fixture-gap to verified, WARN count drops.

## Constraints
- Read-only; no stand mutation for this gap.
- Direct gRPC needs CA + proto symlink; never commit them.
- Sanitize committed evidence.

## Non-goals
- `archive_policy_update` mutation (still gated behind isolated codex-* archive fixture).
- Embedded per-device storage policy resolution.

## Verification plan
- Build: edit `archive_policy_target()` in `tools/axxon_detector_archive_smoke.py`.
- Unit tests: `python3.12 -m unittest discover -s tools/tests`.
- Integration tests: `python3.12 tools/axxon_detector_archive_smoke.py` against the stand (CN=Server).
- Manual checks: confirm smoke `archive_policy_get` status ok for `MultimediaStorage.AliceBlue`.
