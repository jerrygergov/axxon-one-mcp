# Axxon One MCP — Project Status & Handoff

**Last updated:** 2026-05-29
**Branch state:** `main` includes Phase 5F-B1 and Phase 5G (BookmarkService) implementations with live evidence. Phases 5D, 5E, and 5F-A gaps are now closed against the live stand (see the gap-closing note below). Continue on `main` unless the user asks for a new worktree.

This file is the single point of entry for any agent (Claude, Codex, human) continuing this project. Read it first, then jump into the linked roadmap and the next-phase plan.

---

## TL;DR

- The MCP is real and live-verified against a private demo stand (`<demo-host>`, `<demo-user>`, gRPC `20109`, HTTP `80`; credentials and CA paths stay out of committed docs).
- The shipped baseline includes docs (Phase 1), live read-only (Phase 2), operator workflows (Phase 3), integration generator (Phase 4), Phase 5A view tools, Phase 5C alarms, Phase 5D videowall/layout/map tools, Phase 5E detector/archive tools, Phase 5F-A admin read tools, and Phase 5F-B1 admin mutation workflows on `main`.
- Phase 5B (PTZ) is deferred — no PTZ camera on the demo stand.
- Phase 5D (videowall / layouts / maps) is shipped on `main` with 11 read tools, 11 operator workflows, live map/videowall smoke evidence, and sanitized docs. Schedules moved to Phase 5F.
- Phase 5E is implemented with 11 detector/archive read tools and 9 operator workflows. `archive_policy_get` is now live-verified: read-only evidence PASS=11, WARN=0, FAIL=0. It resolves `MultimediaStorage.AliceBlue` (retention `day_depth`, binding `storage_type`); the smoke now prefers a top-level `MultimediaStorage.<name>` unit over embedded device storages.
- Phase 5F-A is shipped on `main` with 11 read-only admin tools. Latest sanitized live evidence PASS=10, WARN=1, FAIL=0. `license_status` is `ok` (`GetHostInfo` over direct gRPC), and `domain_event_subscribe` / `node_event_subscribe` return `idle` (healthy idle streams). The remaining WARN is `schedule_descriptor_get`, a genuine stand-side fixture gap.
- Phase 5F-B1 is shipped with five approval-gated `codex-*` security/admin mutation workflows. Phase 5F-B2 added a sixth, `security_production_role_edit_lifecycle` (the reversible slice of 5F-B2): it snapshots a real production role, edits only its cosmetic comment, verifies, then restores the exact original record (`full_restore: true`). Combined live evidence PASS=6, WARN=0, FAIL=0. Still deferred from 5F-B2 (not safely reversible on a shared stand or out of approved scope): license apply/drop, timezone/NTP changes, production user-account/password/login edits, LDAP sync against a real directory, and schedule authoring.
- Phase 5G (BookmarkService) is shipped with live-verified reads over HTTP `/grpc` and an approval-gated `bookmark_lifecycle` mutation workflow. The full lifecycle (create -> verify -> delete) is now live-verified against the stand once a camera access point and an archive range are supplied (PASS=2, WARN=0, FAIL=0). `RenderTrack` is out of scope.
- Inventory discovery has an HTTP `/grpc` fallback (`load_inventory_http`) so camera/archive enumeration works even when the gRPC root CA is unavailable. The stand's gRPC cert CN is `Server` (not `axxon`); use `AXXON_TLS_CN=Server` for direct-gRPC live runs.

Test suite baseline on `main`: 578 / 578 passing.

---

## How to continue in a new session (Codex or Claude)

1. **Read these files in order:**
   1. `STATUS.md` (this file).
   2. `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` — the full 7-phase plan with current status table.
   3. The selected next-phase design/plan. For 5F-B2, start from the 5F-B1 design and explicitly add fixture/maintenance-window constraints before implementation. For 6A, create a fresh authoring-kit plan first.
2. **Confirm the toolchain is ready:**
   ```bash
   cd /Users/jerrygergov/Documents/GitHub/axxon-one-mcp
   python3.12 -m unittest discover -s tools/tests 2>&1 | tail -3
   # current main baseline: Ran 500 tests OK
   ```
3. **Set demo-stand env for any live verification:**
   ```bash
   export AXXON_HOST=<demo-host>
   export AXXON_HTTP_URL=http://<demo-host>
   export AXXON_USERNAME=<demo-user>
   # set AXXON_PASSWORD in your shell or secret manager; keep the value out of committed docs
   export AXXON_TLS_CN=Server   # gRPC cert CN on this stand is "Server"; HTTP /grpc reads need no CA
   export AXXON_CA=<redacted-ca-path>
   ```
4. **Next track is Phase 6A — authoring-kit expansion.** All of 5D/5E/5F are closed against the live stand (the reversible 5F-B2 role-edit slice shipped; the rest of 5F-B2 stays deferred, and `schedule_descriptor_get` needs the stand-side schedule fixture above). 6A is net-new and large. The multi-language renderer seam is in place and all 8 existing templates plus `alarm_responder` and `scheduled_exporter` support Python + Node/TypeScript (20 bundles). Next: 4 remaining new template kinds starting in Python then Node (target: 14 × 2 = 28 bundles, with C# as a future layer).
5. **For any new live verification**, sanitize evidence before committing (replace concrete host/user/CA values with `<demo-host>`, `<demo-user>`, `<redacted>`, never commit bearer tokens or passwords).

---

## Phase status

| Phase | State | Tools shipped | Evidence |
| --- | --- | --- | --- |
| 1 — Docs MCP | ✅ shipped | 6 (search/get/method/endpoint/recipe/gaps) | `tools/axxon_mcp_docs.py` |
| 2 — Live read | ✅ shipped | 15 | `tools/axxon_mcp_live.py` |
| 3 — Operator | ✅ shipped | 11 workflows (7 ephemeral + 4 persistent) | `tools/axxon_mcp_operator.py` |
| 4 — Generator | ✅ shipped | 8 templates | `tools/axxon_mcp_generator.py` |
| 5A — Viewing | ✅ shipped (archive live-verified) | 6 (live_view, snapshot_batch, archive_scrub, archive_frame, archive_mjpeg_bounded, stream_health) | `docs/api-audit/phase-5a-view-smoke-latest.md` |
| 5B — PTZ | ⏸ deferred (no fixture) | — | — |
| 5C — Alarms | ✅ shipped | 7 reads + 6 mutations | `docs/api-audit/phase-5c-alarms-smoke-latest.md` |
| **5D — Videowall/layouts/maps** | ✅ shipped (gaps closed) | 11 reads + 11 operator workflows | `docs/api-audit/phase-5d-view-objects-smoke-latest.md` |
| 5E — Detector depth + archive policies | ✅ shipped (archive policy closed) | 11 reads + 9 workflows | `docs/api-audit/phase-5e-detector-archive-smoke-latest.md` |
| 5F-A — Security/system-health reads + bounded notifiers | ✅ shipped (only schedule fixture open) | 11 reads | `docs/api-audit/phase-5f-admin-smoke-latest.md` |
| 5F-B1/B2 — Security/admin mutations | ✅ shipped (B2 partial) | 6 workflows | `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md` |
| 5G — BookmarkService reads + lifecycle | ✅ shipped (lifecycle live-verified) | 2 reads + 1 lifecycle workflow | `docs/api-audit/phase-5g-bookmarks-smoke-latest.md` |
| 6A — Authoring kit expansion (Python + Node) | 🔧 in progress (increment 4 shipped) | All 8 base templates Python+Node; new kinds `alarm_responder` + `scheduled_exporter` (py+node); 578 tests | `tools/templates/*.ts.tmpl` (10 files), `tools/tests/test_axxon_mcp_generator_6a*.py` |
| 6B — Partner SDK kit | ❌ not started | — | — |
| 7 — NL → plan translator | ❌ not started | — | — |

---

## What's left in the roadmap

See [the roadmap](docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md) for the full breakdown. The remaining work, in dependency order:

1. **Phase 5F-B2 — high-risk admin mutations (partially shipped).** The reversible production role-comment edit/restore (`security_production_role_edit_lifecycle`) is shipped and live-verified. Still deferred (need a dedicated fixture/maintenance window or are not safely reversible on a shared stand): license apply/drop, timezone/NTP changes, production user-account/password/login edits, and LDAP sync against a real directory.
2. **Phase 6A — Authoring kit expansion.** In progress (commit `dfa2c74`). Increments 1-4 shipped:
   language-agnostic renderer seam (`language` field on `GenerationRequest`, `languages` on `TemplateInfo`),
   Node/TypeScript variants for all 8 existing templates (`tools/templates/*.ts.tmpl`),
   `_scan_typescript` in `Verifier`, and two new template kinds: `alarm_responder` (py+node, reads active
   alerts then runs the BeginAlertReview->CompleteAlertReview lifecycle, mutation-gated) and
   `scheduled_exporter` (py+node, bounded scheduled loop over ExportService.ListSessions, read-safe).
   Next: 4 remaining new template kinds (ml_detector_bridge, dashboard_backend, plugin_scaffold,
   ptz_controller) in Python, then their Node variants. (ptz_controller waits on a PTZ fixture.)
3. **Phase 6B — Partner SDK kit and distribution.** `scaffold_plugin`, `plugin_lint`, `plugin_package`, reference plugins in `customer-templates/`.
4. **Phase 7 — NL → plan translator.** `assemble_recipe`, `validate_recipe`, `explain_recipe`; composes existing operator workflows.

Phase 5E fixture debt carried forward: `archive_policy_get` is now closed (resolves `MultimediaStorage.AliceBlue`). Still open for the mutation/maintenance modes only: an AV detector with a writable visual child, and an isolated `codex-*` archive/camera fixture for `archive_policy_update`.

Phase 5F-A: `LicenseService.GetHostInfo` is now read over direct gRPC (HTTP `/grpc` disconnects), and DomainNotifier/NodeNotifier idle streams report `idle` (PASS). The only remaining caveat is `schedule_descriptor_get` — the stand exposes no schedule descriptor (see the gap-closing note for the exact fixture needed).

Phase 5F-B1 live evidence: `docs/api-audit/phase-5f-b-admin-mutation-smoke-latest.md` verifies plan/apply/verify/rollback for temporary user/role lifecycle, temp-role permissions, policy no-op replay, temporary LDAP add/edit/remove, and temporary-user TFA enable/disable.

Phase 5F-B2: the reversible production role-comment edit/restore is shipped (`security_production_role_edit_lifecycle`). Still deferred: license apply/drop, timezone changes, NTP changes, production user-account/password/login edits, LDAP sync against a real directory, and schedule authoring.

Phase 5G status: the `bookmark_lifecycle` workflow is live-verified end to end (apply -> verify -> rollback) once camera 1 is bound to the `AliceBlue` archive and a `camera_access_point` + RFC3339 `range` are supplied. `CreateBookmark`/`GetBookmark`/`DeleteBookmark` are `tested-pass`. `UpdateBookmark`/`SetExportedTime` are not yet exercised; `RenderTrack` is out of scope.

Gap-closing pass (2026-05-29) carried forward: the stand's gRPC cert CN is `Server` (not `axxon`) — use `AXXON_TLS_CN=Server` for direct-gRPC live runs. `load_inventory()` now falls back to an HTTP `/grpc` loader so camera/archive discovery works without the gRPC root CA. Closed gaps: 5A archive frame/MJPEG, the full 5G bookmark lifecycle, **5D `list_layout_images`** (the HTTP `/grpc` bridge returns 500 for `LayoutImagesManager`; routed over direct gRPC and proved with a reversible upload/list/remove round-trip — the stand has 20 layouts, contrary to the earlier "no layouts" assumption), **5E `archive_policy_get`** (resolves `MultimediaStorage.AliceBlue`; smoke now picks the top-level storage unit), and **5F-A `license_status` + notifiers** (`GetHostInfo` over direct gRPC; idle notifier streams report `idle`).

The single genuinely open fixture is **5F-A `schedule_descriptor_get`**: the stand has no config unit exposing schedule/calendar/weekly/daily fields (107 units sampled, zero matched). To close it, create a stand-side recording schedule / arming calendar whose `ConfigurationService.ListUnits` descriptor exposes a weekly/daily schedule property, then run `axxon_admin_smoke.py --schedule-uid <that uid>`.

---

## Working agreements that survive the handoff

These are the rules every phase enforces — they are not optional:

- **Default posture is read-only.** Mutations require explicit mutation flags AND env approval (`AXXON_OPERATOR_APPROVE=1`, `AXXON_ALARMS_APPROVE=1`, or `AXXON_ADMIN_MUTATION_APPROVE=1`).
- **Per-call confirmation tokens** for mutations (`CONFIRM-<action>` or workflow-specific admin tokens).
- **Plan → apply → verify → rollback** for every operator/admin workflow. No mutation reaches the wire without a plan id and a confirmation token.
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

> Read `STATUS.md` at the repo root, then choose either Phase 5F-B2 (only with a dedicated fixture/maintenance approval for high-risk admin mutations) or Phase 6A authoring-kit expansion. Keep credentials env-only and evidence sanitized. Test runner: `python3.12 -m unittest discover -s tools/tests`.

That single sentence plus this file gives a fresh session everything it needs.
