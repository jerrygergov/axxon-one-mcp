# Axxon One MCP — Project Status & Handoff

**Last updated:** 2026-05-26
**Branch state:** `main` includes Phase 5F-A through commit `64d6477`. Continue Phase 5F-B1 directly on `main` unless the user asks for a new worktree.

This file is the single point of entry for any agent (Claude, Codex, human) continuing this project. Read it first, then jump into the linked roadmap and the next-phase plan.

---

## TL;DR

- The MCP is real and live-verified against a private demo stand (`<demo-host>`, `<demo-user>`, gRPC `20109`, HTTP `80`; credentials and CA paths stay out of committed docs).
- The shipped baseline includes docs (Phase 1), live read-only (Phase 2), operator workflows (Phase 3), integration generator (Phase 4), Phase 5A view tools, Phase 5C alarms, Phase 5D videowall/layout/map tools, Phase 5E detector/archive tools, and Phase 5F-A admin read tools on `main`.
- Phase 5B (PTZ) is deferred — no PTZ camera on the demo stand.
- Phase 5D (videowall / layouts / maps) is shipped on `main` with 11 read tools, 11 operator workflows, live map/videowall smoke evidence, and sanitized docs. Schedules moved to Phase 5F.
- Phase 5E is implemented with 11 detector/archive read tools and 9 operator workflows. Latest combined live evidence: PASS=12, WARN=3, FAIL=0 across read-only, mutation, and archive-maintenance-no-op modes.
- Phase 5F-A is shipped on `main` with 11 read-only admin tools and sanitized live evidence PASS=7, WARN=4, FAIL=0.
- Phase 5F-B1 planning is approved: controlled `codex-*` security/admin mutation workflows only. License, timezone, NTP, production user/role edits, LDAP sync, and schedule authoring remain deferred.

Test suite baseline on `main`: 434 / 434 passing.

---

## How to continue in a new session (Codex or Claude)

1. **Read these four files in order:**
   1. `STATUS.md` (this file).
   2. `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` — the full 7-phase plan with current status table.
   3. `docs/superpowers/specs/2026-05-26-phase-5f-b-security-admin-mutations-design.md`.
   4. `docs/superpowers/plans/2026-05-26-phase-5f-b-security-admin-mutations.md`.
2. **Confirm the toolchain is ready:**
   ```bash
   cd /Users/jerrygergov/Documents/GitHub/axxon-one-mcp
   python3.12 -m unittest discover -s tools/tests 2>&1 | tail -3
   # current main baseline: Ran 434 tests OK
   ```
3. **Set demo-stand env for any live verification:**
   ```bash
   export AXXON_HOST=<demo-host>
   export AXXON_HTTP_URL=http://<demo-host>
   export AXXON_USERNAME=<demo-user>
   export AXXON_PASSWORD=<redacted>
   export AXXON_TLS_CN=<demo-tls-cn>
   export AXXON_CA=<redacted-ca-path>
   ```
4. **Start Phase 5F-B1 Task 1** from `docs/superpowers/plans/2026-05-26-phase-5f-b-security-admin-mutations.md`. Keep mutations approval-gated and fixture-backed.
5. **For any new live verification**, sanitize evidence before committing (replace concrete host/user/CA values with `<demo-host>`, `<demo-user>`, `<redacted>`, never commit bearer tokens or passwords).

---

## Phase status

| Phase | State | Tools shipped | Evidence |
| --- | --- | --- | --- |
| 1 — Docs MCP | ✅ shipped | 6 (search/get/method/endpoint/recipe/gaps) | `tools/axxon_mcp_docs.py` |
| 2 — Live read | ✅ shipped | 15 | `tools/axxon_mcp_live.py` |
| 3 — Operator | ✅ shipped | 11 workflows (7 ephemeral + 4 persistent) | `tools/axxon_mcp_operator.py` |
| 4 — Generator | ✅ shipped | 8 templates | `tools/axxon_mcp_generator.py` |
| 5A — Viewing | ✅ shipped | 6 (live_view, snapshot_batch, archive_scrub, archive_frame, archive_mjpeg_bounded, stream_health) | `docs/api-audit/phase-5a-view-smoke-latest.md` |
| 5B — PTZ | ⏸ deferred (no fixture) | — | — |
| 5C — Alarms | ✅ shipped | 7 reads + 6 mutations | `docs/api-audit/phase-5c-alarms-smoke-latest.md` |
| **5D — Videowall/layouts/maps** | ✅ shipped | 11 reads + 11 operator workflows | `docs/api-audit/phase-5d-view-objects-smoke-latest.md` |
| 5E — Detector depth + archive policies | ✅ shipped (fixture caveats) | 11 reads + 9 workflows | `docs/api-audit/phase-5e-detector-archive-smoke-latest.md` |
| 5F-A — Security/system-health reads + bounded notifiers | ✅ shipped (fixture caveats) | 11 reads | `docs/api-audit/phase-5f-admin-smoke-latest.md` |
| 5F-B1 — Security/admin mutations | 📝 planned | — | `docs/superpowers/plans/2026-05-26-phase-5f-b-security-admin-mutations.md` |
| 6A — Authoring kit expansion (Python + Node) | ❌ not started | — | — |
| 6B — Partner SDK kit | ❌ not started | — | — |
| 7 — NL → plan translator | ❌ not started | — | — |

---

## What's left in the roadmap

See [the roadmap](docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md) for the full breakdown. The remaining work, in dependency order:

1. **Phase 5F-B1 — Security/admin mutations.** Promote the proven temp `codex-*` users/roles/permissions/LDAP/TFA lifecycle into approval-gated MCP workflows.
2. **Phase 6A — Authoring kit expansion.** Add Node/TypeScript templates and 6 new template kinds (alarm responder, PTZ controller, ML-detector bridge, scheduled exporter, dashboard backend, plugin scaffold).
3. **Phase 6B — Partner SDK kit and distribution.** `scaffold_plugin`, `plugin_lint`, `plugin_package`, reference plugins in `customer-templates/`.
4. **Phase 7 — NL → plan translator.** `assemble_recipe`, `validate_recipe`, `explain_recipe`; composes existing operator workflows.

Phase 5E fixture debt carried forward: provide a descriptor-backed archive policy fixture, an AV detector with a writable visual child, and an isolated `codex-*` archive/camera fixture to clear the three WARN rows in the latest live smoke.

Phase 5F-A fixture/stand caveats carried forward: `LicenseService.GetHostInfo` closes the connection while other license reads succeed, DomainNotifier/NodeNotifier streams were quiet and ended by bounded deadline after disconnect cleanup, and schedule descriptor discovery needs an isolated descriptor-backed schedule fixture.

Phase 5F-B2 deferred scope: license apply/drop, timezone changes, NTP changes, production user/role edits, LDAP sync against a real directory, and schedule authoring.

---

## Working agreements that survive the handoff

These are the rules every phase enforces — they are not optional:

- **Default posture is read-only.** Mutations require explicit `--enable-*-mutation` flags AND env approval (`AXXON_OPERATOR_APPROVE=1` or `AXXON_ALARMS_APPROVE=1`).
- **Per-call confirmation tokens** for mutations (`CONFIRM-<action>`).
- **Plan → apply → verify → rollback** for every operator workflow. No mutation reaches the wire without a plan id and a confirmation token.
- **Bounded streams.** Every subscription / media / export tool clamps bytes, time, fps. Caps are reported back in `caps`.
- **URL-only for media.** The MCP never proxies bytes; it returns capped URLs and the caller fetches.
- **Env-only secrets.** Credentials come from `AXXON_*` env vars. Generators reject embedded secrets.
- **Sanitized evidence.** Replace concrete host/user/CA values with `<demo-host>`, `<demo-user>`, and `<redacted>`, replace TLS CN when needed, never commit bearer tokens or passwords. `hosts/Server/...` UIDs may stay (intrinsic to the stand, not credential material).
- **No copyrighted source in this repo.** `docs/integration-apis-3.0/` and `docs/grpc-proto-files/` are gitignored.
- **TDD + frequent commits.** Each plan task is one logical step: failing test → minimal code → passing test → commit with the exact message in the plan.
- **No defensive programming** unless the user-facing safety guarantee depends on it. Errors should surface for debuggability.

---

## Demo stand quirks (carry forward)

These were learned during 5A and 5C and apply to every future phase:

- The gRPC client expects the stand root CA, not the Sale CA file. Keep the concrete CA path in local environment only and redact it from evidence.
- `BatchGetActiveAlerts` returns paginated `event_stream_items[]` where the first page can report `unreachable_nodes: ["hosts/Server"]` even though subsequent pages have data. The 5C `list_active_alerts` only surfaces `unreachable_nodes` when **every** page agrees.
- New bearer token TTL on the stand is 5 minutes (`AuthenticationService.RenewSession2`).
- `CompleteAlertReview` requires a non-empty `bookmark.message` because the stand's `LogicService.GetConfig` reports `required_comment: {confirmed_alarm: true, suspicious_situation: true, false_alarm: true}`.
- The smoke harness for `axxon_alarms_smoke.py --mutation` uses `raise → begin → continue → cancel → verify-gone` as its non-record-leaving round-trip. Use `--full` only on a dedicated stand because it leaves bookmarks.

---

## Handoff to a Codex session

You can hand this project to Codex (or any other agent) with the following one-liner:

> Read `STATUS.md` at the repo root, then use `docs/superpowers/specs/2026-05-26-phase-5f-b-security-admin-mutations-design.md` and `docs/superpowers/plans/2026-05-26-phase-5f-b-security-admin-mutations.md` to start Phase 5F-B1 Task 1 on `main`. Keep mutations approval-gated and fixture-backed. Test runner: `python3.12 -m unittest discover -s tools/tests`.

That single sentence plus this file gives a fresh session everything it needs.
