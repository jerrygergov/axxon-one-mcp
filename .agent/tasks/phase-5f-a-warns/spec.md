# Task Spec: phase-5f-a-warns

## Metadata
- Task ID: phase-5f-a-warns
- Created: 2026-05-29T13:57:30+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- AGENTS.md
- CLAUDE.md

## Original task statement
Close Phase 5F-A WARNs. (1) license_status host_info WARN: LicenseService.GetHostInfo returns RemoteDisconnected over HTTP /grpc but works over direct gRPC (returns hwinfo XML). Route license_get_host_info over direct gRPC; redact hwinfo fingerprint in evidence. (2) DomainNotifier/NodeNotifier WARN: streams connect and stay open until the bounded deadline then raise DEADLINE_EXCEEDED with 0 events because the single-node stand emits no domain/node topology events during the window. A clean DEADLINE_EXCEEDED on an established stream with a clean DisconnectEventChannel is a healthy-but-idle stream, not a failure; report it as status idle (ok-class) distinct from genuine transport errors (UNAVAILABLE/UNAUTHENTICATED) which stay warn/error. (3) schedule_descriptor_get WARN: no descriptor-backed schedule fixture on the stand; this genuinely needs a stand-side fixture and stays fixture-needed with a precise spec. Verify live; refresh phase-5f-a evidence and corpus.

## Acceptance criteria
- AC1: `license_status` returns `status: ok` live; `GetHostInfo` routed over direct gRPC; hwinfo fingerprint never echoed (present-flag only, redacted).
- AC2: `domain_event_subscribe` and `node_event_subscribe` return `status: idle` (PASS-class) with `stream_idle: true` and `disconnect_clean: true` on a clean DEADLINE_EXCEEDED; genuine transport errors stay `warn`.
- AC3: `schedule_descriptor_get` stays a clean `fixture-needed` (WARN) because the stand has no schedule descriptor; the precise fixture is documented (see Non-goals / fixture spec).
- AC4: All `tools/tests` green (>=503); live 5F-A smoke WARN count drops from 4 to 1; evidence refreshed and sanitized.

## Constraints
- Read-only; direct gRPC needs CA + proto symlink, never committed.
- hwinfo hardware fingerprint must never appear in committed evidence.

## Non-goals
- Closing schedule_descriptor_get without a stand-side fixture. REQUIRED FIXTURE: a config unit on the stand that exposes schedule-like properties (id/name/path containing one of: schedule, calendar, weekly, daily). None of the 107 sampled config units carry such fields. To close this, create (stand-side) a recording schedule / arming calendar object whose ConfigurationService.ListUnits descriptor exposes a weekly/daily schedule property, then re-run the smoke with --schedule-uid <that uid>.

## Verification plan
- Build: route GetHostInfo over gRPC in axxon_api_client; idle-stream classification in pull_notifier_events_bounded; idle->PASS in admin smoke.
- Unit tests: `python3.12 -m unittest discover -s tools/tests`.
- Integration tests: `python3.12 tools/axxon_admin_smoke.py --include-node-notifier` against the stand (CN=Server).
- Manual checks: license_status ok; notifiers idle; schedule fixture-needed.
