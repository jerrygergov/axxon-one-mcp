# Axxon One MCP — Project Status & Handoff

**Last updated:** 2026-05-18
**Branch state:** `main` at `12c9283 merge: Phase 5A (live + archive viewing) and Phase 5C (alarms)`. Worktree branch `codex/phase-5d-layouts-maps-videowalls` contains the Phase 5D implementation and docs; not merged to `main` yet.

This file is the single point of entry for any agent (Claude, Codex, human) continuing this project. Read it first, then jump into the linked roadmap and the next-phase plan.

---

## TL;DR

- The MCP is real and live-verified against a stand at `100.76.150.18` (root/root, gRPC `20109`, HTTP `80`, CA at `docs/grpc-proto-files/api.ngp.root-ca.crt`, TLS CN `Server`).
- The shipped baseline in `main` includes docs (Phase 1), live read-only (Phase 2), operator workflows (Phase 3), integration generator (Phase 4), Phase 5A view tools, and Phase 5C alarms.
- Phase 5B (PTZ) is deferred — no PTZ camera on the demo stand.
- Phase 5D (videowall / layouts / maps) is **implemented on branch** with 11 read tools, 11 operator workflows, live map/videowall smoke evidence, and sanitized docs. Schedules moved to Phase 5F.
- Phases 5E, 5F, 6A, 6B, 7 are not yet started.

Test suite: 281 / 281 passing on the Phase 5D branch.

---

## How to continue in a new session (Codex or Claude)

1. **Read these three files in order:**
   1. `STATUS.md` (this file).
   2. `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` — the full 7-phase plan with current status table.
   3. The next-phase design/spec (default next work: Phase 5E detector + analytics depth, archive policies).
2. **Confirm the toolchain is ready:**
   ```bash
   cd /Users/jerrygergov/Documents/GitHub/axxon-one-mcp
   python3.12 -m unittest discover -s tools/tests 2>&1 | tail -3
   # expect on this branch: Ran 281 tests OK
   ```
3. **Set demo-stand env for any live verification:**
   ```bash
   export AXXON_HOST=100.76.150.18
   export AXXON_HTTP_URL=http://100.76.150.18
   export AXXON_USERNAME=root
   export AXXON_PASSWORD=root
   export AXXON_TLS_CN=Server
   export AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt
   ```
4. **Pick the next phase** (default: 5E) and follow the resulting plan task-by-task. Plans are written as bite-sized TDD steps; an agent should execute them via the subagent-driven-development approach (or whatever equivalent the runtime provides). Each task: failing test → minimal code → passing test → commit.
5. **Live-verify mutations** on the demo stand. Sanitize evidence before committing (replace `100.76.150.18` with `<demo-host>`, never commit bearer tokens or passwords).

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
| **5D — Videowall/layouts/maps** | **✅ implemented on branch** | 11 reads + 11 operator workflows | `docs/api-audit/phase-5d-view-objects-smoke-latest.md` |
| 5E — Detector depth + archive policies | ❌ not started | — | — |
| 5F — Security / users / system health + schedules | ❌ not started | — | — |
| 6A — Authoring kit expansion (Python + Node) | ❌ not started | — | — |
| 6B — Partner SDK kit | ❌ not started | — | — |
| 7 — NL → plan translator | ❌ not started | — | — |

---

## What's left in the roadmap

See [the roadmap](docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md) for the full breakdown. The remaining work, in dependency order:

1. **Phase 5E — Detector + analytics depth, archive policies.** Not yet brainstormed. Closes the last large pending block in `LogicService`-adjacent and `ArchiveService` config surfaces.
2. **Phase 5F — Security, users, roles, system health, schedules.** Schedule authoring was moved here during 5D scoping.
3. **Phase 6A — Authoring kit expansion.** Add Node/TypeScript templates and 6 new template kinds (alarm responder, PTZ controller, ML-detector bridge, scheduled exporter, dashboard backend, plugin scaffold).
4. **Phase 6B — Partner SDK kit and distribution.** `scaffold_plugin`, `plugin_lint`, `plugin_package`, reference plugins in `customer-templates/`.
5. **Phase 7 — NL → plan translator.** `assemble_recipe`, `validate_recipe`, `explain_recipe`; composes existing operator workflows.

---

## Working agreements that survive the handoff

These are the rules every phase enforces — they are not optional:

- **Default posture is read-only.** Mutations require explicit `--enable-*-mutation` flags AND env approval (`AXXON_OPERATOR_APPROVE=1` or `AXXON_ALARMS_APPROVE=1`).
- **Per-call confirmation tokens** for mutations (`CONFIRM-<action>`).
- **Plan → apply → verify → rollback** for every operator workflow. No mutation reaches the wire without a plan id and a confirmation token.
- **Bounded streams.** Every subscription / media / export tool clamps bytes, time, fps. Caps are reported back in `caps`.
- **URL-only for media.** The MCP never proxies bytes; it returns capped URLs and the caller fetches.
- **Env-only secrets.** Credentials come from `AXXON_*` env vars. Generators reject embedded secrets.
- **Sanitized evidence.** Replace `100.76.150.18` with `<demo-host>`, replace TLS CN, never commit bearer tokens or passwords. `hosts/Server/...` UIDs may stay (intrinsic to the stand, not credential material).
- **No copyrighted source in this repo.** `docs/integration-apis-3.0/` and `docs/grpc-proto-files/` are gitignored.
- **TDD + frequent commits.** Each plan task is one logical step: failing test → minimal code → passing test → commit with the exact message in the plan.
- **No defensive programming** unless the user-facing safety guarantee depends on it. Errors should surface for debuggability.

---

## Demo stand quirks (carry forward)

These were learned during 5A and 5C and apply to every future phase:

- The CA cert path that the gRPC client expects is `docs/grpc-proto-files/api.ngp.root-ca.crt` — NOT the `Tickets/ngp.ca` file (which is the Sale CA, not the stand's root). Use the absolute path when running smokes from a worktree subdir.
- `BatchGetActiveAlerts` returns paginated `event_stream_items[]` where the first page can report `unreachable_nodes: ["hosts/Server"]` even though subsequent pages have data. The 5C `list_active_alerts` only surfaces `unreachable_nodes` when **every** page agrees.
- New bearer token TTL on the stand is 5 minutes (`AuthenticationService.RenewSession2`).
- `CompleteAlertReview` requires a non-empty `bookmark.message` because the stand's `LogicService.GetConfig` reports `required_comment: {confirmed_alarm: true, suspicious_situation: true, false_alarm: true}`.
- The smoke harness for `axxon_alarms_smoke.py --mutation` uses `raise → begin → continue → cancel → verify-gone` as its non-record-leaving round-trip. Use `--full` only on a dedicated stand because it leaves bookmarks.

---

## Handoff to a Codex session

You can hand this project to Codex (or any other agent) with the following one-liner:

> Read `STATUS.md` at the repo root, then continue from the "Next concrete step" listed in `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`. Phase 5D is implemented on `codex/phase-5d-layouts-maps-videowalls`; default next step is Phase 5E (detector + analytics depth, archive policies) brainstorming/spec. Follow future plans task-by-task with TDD discipline; commit after every task. Live-verify mutations against the demo stand. Sanitize evidence before commit. Test runner: `python3.12 -m unittest discover -s tools/tests`.

That single sentence plus this file gives a fresh session everything it needs.
