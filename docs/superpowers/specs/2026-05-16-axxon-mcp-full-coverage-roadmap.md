# Axxon One MCP — Full-Coverage Roadmap

**Date:** 2026-05-16
**Status:** Active roadmap
**Author:** brainstorming session
**Spec type:** multi-phase roadmap (decomposition doc, not a single implementation spec)

---

## 1. Goal (verbatim from the user)

> Create an MCP server for Axxon One VMS that covers ALL functionalities and everything that the gRPC API can give. Everything the desktop client can do — view, operate/configure, receive events, snapshots, video flows, add cameras/detectors/layouts, use client API and all others — so customers and partners can:
>
> - operate with the VMS backend and frontend more easily,
> - create plugins or tools (Python for example) more easily,
> - make vertical or horizontal integrations with other software,
> - configure the product (add cameras, configure them aligned with documentation, add detectors and configure them, etc.).

This roadmap turns that goal into a concrete sequence of shippable specs.

---

## 1b. Current phase status (updated 2026-05-25)

| Phase | State | Merged to main? | Artifacts |
| --- | --- | --- | --- |
| **5A** Live + archive viewing | ✅ shipped | yes (`12c9283`) | `tools/axxon_mcp_view.py`, `tools/axxon_view_smoke.py`, `docs/api-audit/phase-5a-view-smoke-latest.md` |
| **5B** PTZ + Tag&Track + control panels | ⏸ deferred (no PTZ fixture) | n/a | none |
| **5C** Alarms (lifecycle + subscription) | ✅ shipped | yes (`12c9283`) | `tools/axxon_mcp_alarms.py`, `tools/axxon_alarms_smoke.py`, `docs/api-audit/phase-5c-alarms-smoke-latest.md`, design + plan under `docs/superpowers/specs/` and `docs/superpowers/plans/` |
| **5D** Videowall / layouts / maps | ✅ shipped | yes | `tools/axxon_mcp_view_objects.py`, `tools/axxon_view_objects_smoke.py`, `docs/api-audit/phase-5d-view-objects-smoke-latest.md`, design + plan under `docs/superpowers/` |
| **5E** Detector depth + archive policies | ✅ shipped (fixture caveats) | no | `tools/axxon_mcp_detector_archive.py`, `tools/axxon_detector_archive_smoke.py`, `docs/api-audit/phase-5e-detector-archive-smoke-latest.md`, design + plan under `docs/superpowers/` |
| **5F** Security / users / system health | ❌ not started | no | none |
| **6A** Authoring kit expansion | ❌ not started | no | none |
| **6B** Partner SDK kit + distribution | ❌ not started | no | none |
| **7** NL → plan translator | ❌ not started | no | none |

**Note on schedules:** During 5D brainstorming we decided to **move schedule authoring out of 5D into 5F** (security/system phase). The 5D scope is now Layouts + Maps + Videowalls only.

**Next concrete step:** start Phase 5F security/users/system-health/schedules planning, while carrying the Phase 5E fixture debt: descriptor-backed archive policy fixture, AV detector writable visual child, and isolated `codex-*` archive/camera fixture.

---

## 2. Source material and ground truth

### 2.1 Inputs to this roadmap

| Source | Location | Notes |
| --- | --- | --- |
| Axxon One product docs | https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314535799/Documentation | Public product documentation — used for capability mapping, not embedded in repo. |
| Integration APIs 3.0 PDF | `docs/integration-apis-3.0/` (local; gitignored) | AxxonSoft-copyrighted. Excluded from the public repo. Drives `api_methods.json` / `http_endpoints.json`. |
| gRPC proto files | `docs/grpc-proto-files/` (local; gitignored) | AxxonSoft-copyrighted. Source for the 361-method catalog. |
| PDF gap coverage matrix | `docs/api-audit/pdf-gap-coverage-matrix.md` | 37 rows, 30 verified, 1 partial, 6 fixture-blocked. |
| Structured MCP corpus | `docs/api-audit/mcp-corpus/` | 7 JSON files (api_methods, http_endpoints, task_recipes, fixtures, safety_policies, known_behaviors, README). |

### 2.2 Demo / testing stand

The roadmap and all live verification work targets the user-provided stand:

| Field | Value |
| --- | --- |
| Host | `<demo-host>` |
| gRPC port | `20109` |
| HTTP port | `80` |
| Login | `<demo-user>` |
| Password | `<redacted>` |
| Use | All live smoke runs, fixture creation, mutation playbooks, and rollback verification. |

These credentials are operator-test-only. They must **never** be committed in code, examples, or audit evidence — generators and smokes already read them from environment variables (`AXXON_HOST`, `AXXON_HTTP_URL`, `AXXON_USERNAME`, `AXXON_PASSWORD`, `AXXON_TLS_CN`). The sanitization rule from the existing repo (replace host with `<demo-host>`, user with `<demo-user>`, secrets/CA paths with `<redacted>`, TLS CN with `<your-tls-cn>`, and replace `hosts/Server/...` UIDs only when needed) carries forward to every phase below.

### 2.3 What is already shipped (verified)

This is not a greenfield project. The roadmap builds on:

| Phase | Status | Files |
| --- | --- | --- |
| Phase 1 — Docs-only MCP | Shipped | `axxon_mcp_docs.py`, `axxon_mcp_server.py` |
| Phase 2 — Read-only live | Shipped, 15 tools | `axxon_mcp_live.py` |
| Phase 3 — Controlled operator (plan/apply/verify/rollback) | Shipped, 11 workflows (7 ephemeral, 4 persistent) | `axxon_mcp_operator.py` |
| Phase 4 — Integration code generator | Shipped, 8 templates | `axxon_mcp_generator.py`, `tools/templates/` |
| Verified API methods | 146 / 361 (124 tested-pass + 21 tested-pass-safe-record + 1 tested-pass-empty) | `mcp-corpus/api_methods.json` |
| PDF coverage matrix | 30 / 37 verified, 1 partial, 6 fixture-blocked | `pdf-gap-coverage-matrix.md` |
| Unit tests | 384 / 384 passing in the Phase 5E worktree | `tools/tests/` |

### 2.4 What is still missing (the work this roadmap exists for)

Quantified from `api_methods.json`:

- **185 gRPC methods are still `pending`** (no live evidence). Largest pending services:
  - TelemetryService — 26 pending (PTZ control, presets, Tag&Track)
  - LogicService — 19 pending (alarm lifecycle beyond reads, rule mutations)
  - SecurityService — 11 pending (TFA, deeper LDAP, advanced policies)
  - AuthenticationService — 10 pending (extended session / federated flows)
  - AuditEventInjector — 7 pending
  - BookmarkService — 7 pending (additional shapes beyond create/update/delete)
  - NodeNotifier — 6 pending
  - HeatMapService — 6 pending (additional shapes)
  - MediaService — 6 pending
  - VideowallService — 4 pending (mutations)
  - GlobalTrackerService — 4 pending
  - RealtimeRecognizerService — 4 pending
  - LayoutManager / LayoutImagesManager — 7 pending combined
  - TagAndTrackService — 3 pending
- **30 methods are `tested-warn-fixture-needed`** (PTZ device, water-level, control panels, Tag&Track tracker, TFA, WebSocket `/events`, client HTTP API for layouts/videowalls, embeddable video component browser render).
- **Desktop-client features not yet surfaced as MCP tools** (even where the underlying API is verified):
  - Live multi-stream viewing flow (subscribe to multiple cameras, frame-accurate timestamps, snapshot batches).
  - Archive scrub with calendar + interval + frame review as a single tool.
  - Alarm operator workflow (begin → cancel/continue/complete/escalate).
  - PTZ joystick / preset / patrol control.
  - Videowall control (push layout, push camera, screen routing).
  - Layout / map authoring beyond `temp_layout` / `temp_map`.
  - System health dashboard (license, disk, storage, replication, backup, node status).
  - Schedule / calendar authoring.
  - Notification rule (LogicService rules) authoring.
- **Authoring kit (Phase 4 expansion):**
  - More templates: alarm responder, PTZ controller, ML-detector bridge, scheduled exporter, dashboard backend, plugin scaffold.
  - Multi-language: today Python only — Node/TypeScript and C# requested.
  - End-to-end `scaffold_plugin` that emits a runnable repo (auth, retry, telemetry, tests, CI).

---

## 3. Design constraints (carry over from the existing repo)

These are existing project rules. The roadmap honors them in every phase.

1. **Default posture is read-only.** Mutating tools require explicit enable (`AXXON_OPERATOR_APPROVE=1`) and per-call confirmation tokens.
2. **Plan → apply → verify → rollback** for every mutation. No tool ever mutates state without a returned plan ID and a confirmation token.
3. **Bounded streams.** Every subscription / media / export tool enforces byte caps, time caps, and frame caps.
4. **Secrets in memory only.** Credentials come from environment variables. Generated code reads credentials from env, never from arguments. Static verifier already rejects embedded secrets.
5. **Sanitized evidence.** Concrete host IPs, users, CA paths, passwords, tokens, and TLS CNs are scrubbed before evidence is committed. Intrinsic `hosts/Server/...` UIDs may remain unless they identify sensitive customer data; the private demo stand is sanitized to `<demo-host>` in any published report.
6. **No copyrighted source in this repo.** `docs/integration-apis-3.0/` and `docs/grpc-proto-files/` stay gitignored. Only audit tooling and evidence authored in this project are public.
7. **Reuse `AxxonApiClient`.** Direct gRPC with TLS override, HTTP `/grpc`, legacy HTTP, and `/v1` endpoints all share the same client.
8. **No defensive programming unless justified.** Errors surface for debuggability; we add try/except only where a user-facing safety guarantee depends on it (rollback, byte cap, redaction).

---

## 4. Architectural shape of the finished MCP

The finished server keeps the existing four-layer shape and extends each layer:

```
┌─────────────────────────────────────────────────────────────────────┐
│  MCP transports: stdio, streamable-http                             │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 1: Docs / Knowledge — search, methods, endpoints, recipes,   │
│            examples, gaps, fixtures, safety classification.         │
│  Phase 2: Live read — inventory, events, metadata, archive          │
│            intervals, bounded subscriptions, snapshots, calendar.   │
│  Phase 3: Operator — plan/apply/verify/rollback workflows for       │
│            every desktop-client configuration action.               │
│  Phase 4: Authoring — code generators, plugin scaffolds, recipe     │
│            assemblers, NL → plan translators.                       │
│  Phase 5 (new): Operator UX — multi-step desktop-equivalent flows   │
│            (live multi-stream, alarm handling, PTZ, videowall,      │
│            system health, archive scrub).                           │
│  Phase 6 (new): Partner / SDK kit — multi-language scaffolds,       │
│            webhook bridge bundles, distribution + signing,          │
│            integration test fixtures.                               │
├─────────────────────────────────────────────────────────────────────┤
│  Safety layer: read-only by default, risk classification, byte/time │
│  caps, rollback verification, secret redaction, audit log.          │
├─────────────────────────────────────────────────────────────────────┤
│  Axxon runtime: AxxonApiClient (direct gRPC with TLS override,      │
│  HTTP /grpc, legacy HTTP, /v1).                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Each phase below is independently shippable. Each ends with: updated coverage matrix, new evidence reports under `docs/api-audit/`, new unit tests, and a runnable smoke against the demo stand.

---

## 5. Phase plan (the decomposition)

Each phase below is its own future spec → plan → implementation cycle. Order reflects dependency, not difficulty.

### Phase 5A — Operator UX: Live + Archive viewing

**Why first.** It is the most-requested desktop capability and is built almost entirely on already-verified APIs (media streams, archive intervals, archive calendar, snapshots). Low API risk, high user value.

**Scope.**
- `live_view(camera_ids, duration_s, fps_cap, codec_preference)` — returns bounded HLS/RTSP/MJPEG/snapshot handles for one or more cameras with stream-info, byte and time caps.
- `snapshot_batch(camera_ids, ts="now"|iso, format="jpeg")` — parallel snapshot capture with size/count caps.
- `archive_scrub(camera_id, range)` — combined calendar + intervals + frame-registration probe.
- `archive_frame(camera_id, ts, archive=None)` — single-frame archive retrieval with size cap.
- `archive_mjpeg_bounded(camera_id, range, byte_cap, time_cap)` — already exists as smoke; promote to tool.
- `stream_health(camera_id)` — uses `/statistics/...` (already verified) plus media access-point listing.

**Out of scope.** PTZ control (Phase 5B), composite multi-camera mosaics (Phase 5D).

**Acceptance.**
- All tools enforce documented caps and refuse calls without them.
- Live smoke run against `<demo-host>:20109` produces sanitized evidence under `docs/api-audit/phase-5a-*-latest.md`.
- Unit tests cover cap enforcement, error redaction, and access-point resolution.

---

### Phase 5B — Operator UX: PTZ + Tag&Track + Control panels

**Why second.** Unblocks the largest pending service (TelemetryService — 26 pending). Requires a fixture (PTZ-capable camera or virtual telemetry).

**Scope.**
- `ptz_list()` — discover telemetry access points and capabilities.
- `ptz_move(camera_id, pan, tilt, zoom, speed)` — bounded relative move with safety stop.
- `ptz_goto_preset(camera_id, preset_id)` / `ptz_set_preset` / `ptz_list_presets`.
- `ptz_patrol_start(camera_id, route_id)` / `ptz_patrol_stop`.
- `tag_and_track_subscribe(camera_id, duration_s, byte_cap)` — bounded read of tracker stream.
- `control_panel_list()` and `control_panel_action(panel_id, action_id, confirm)`.
- `water_level_read(device_id)`.

**Fixture path.** Phase 5B has a documented fixture-or-stub mode: if no PTZ device exists on the demo stand, tools return `status: fixture-needed` with a precise list of required objects. The integration with `axxon_fixture_discovery.py` is required so this status is auto-detected, not hand-set.

**Out of scope.** Authoring PTZ patrol routes (Phase 5E uses LogicService).

**Acceptance.**
- All mutations go through the plan/apply/verify/rollback flow.
- If no fixture is available on `<demo-host>`, smoke ends with a clean fixture-needed report. If a fixture is provided, smoke verifies one preset goto and one bounded move with rollback to start position.
- TelemetryService pending count drops to ≤ 5 (everything except mode-specific advanced calls).

---

### Phase 5C — Operator UX: Alarm lifecycle and notifications

**Why third.** LogicService is the second-largest pending service (19 methods). Alarm handling is core operator work and not yet exposed as a tool.

**Scope.**
- `alarm_subscribe(filter, duration_s)` — bounded WebSocket-or-gRPC alarm stream with filtering on macro, camera, severity.
- `alarm_begin(alarm_id)` / `alarm_continue` / `alarm_cancel(reason)` / `alarm_complete(reason)` / `alarm_escalate(role_id, reason)` — already exists as RPC, promote to safe tool with audit and confirmation.
- `alarm_history(range, filter)` — uses `EventHistoryService.ReadEvents` with alarm-specific filter.
- `notification_rule_list()` and `notification_rule_get(id)`.
- `notification_rule_create(plan)` / `update` / `remove` — all under operator plan/apply/verify/rollback.

**Acceptance.**
- Alarm subscription drops cleanly at byte or time cap; partial-result reporting matches `subscribe_events_bounded` shape.
- Alarm lifecycle tools require a real active alarm or a synthesized one via `external_event_inject` (already verified) — no silent no-op.
- LogicService pending count drops to ≤ 5.

---

### Phase 5D — Operator UX: Videowall, layouts, maps

**Why.** Configuration depth for visual surfaces. Builds on already-verified `temp_layout`, `temp_map`, `LayoutsOnView`, `MapService` reads.

**Scope.**
- `videowall_list()` / `videowall_push(screen_id, layout_id|camera_id)` / `videowall_clear(screen_id)`.
- `layout_create_persistent(plan)` / `layout_update(plan)` / `layout_delete(id)` — persistent counterpart of `temp_layout`.
- `layout_render_preview(layout_id, size)` — uses `LayoutImagesManager` (which has 3 pending methods).
- `map_create_persistent(plan)` / `map_update(plan)` / `map_delete(id)` — persistent counterpart of `temp_map`.
- `map_marker_add(map_id, marker)` / `update` / `remove` — already verified, promote to tools.
- Schedule authoring moved to Phase 5F.

**Acceptance.**
- Every mutation goes through plan/apply/verify/rollback.
- Persistent layouts and maps include explicit `caller_owns_lifecycle` annotation in the plan output (consistent with existing `create_camera`, `create_macro`).

---

### Phase 5E — Operator UX: Detector + analytics depth, archive policies

**Status.** Shipped on `codex/phase-5e-detectors-archive` with fixture caveats. Latest evidence: `docs/api-audit/phase-5e-detector-archive-smoke-latest.md` (PASS=12, WARN=3, FAIL=0).

**Why.** Detector parameter list/read/edit is verified, but the catalog of detector kinds, the per-kind parameter schemas, and the archive-binding rules are not yet exposed as tools. This phase closes the gap so an LLM can author a full detector config from a natural-language description.

**Scope.**
- `detector_kind_catalog()` — full list of supported detector kinds with parameter schemas, derived from proto and config-model study (already partly verified).
- `create_av_detector_full(plan)` / `create_appdata_detector_full(plan)` — extension of `temp_av_detector` / `temp_appdata_detector` to non-temporary detectors with full parameter trees.
- `detector_parameter_schema(kind)` — returns JSON schema for a detector kind so the caller (or LLM) can build a valid plan.
- `archive_policy_get(camera_id)` / `archive_policy_update(plan)` — recording schedules and pre/post-event windows.
- `archive_management_extended` — promotes the verified format/reindex/cancel-reindex/cloud/link operations from approval-gated maintenance to operator workflows (still gated on isolated storage fixture).
- `metadata_schema_catalog()` — VMDA / face / LPR / heatmap parameter shapes.

**Out of scope.** Vendor-specific camera firmware tuning beyond what the proto exposes.

**Acceptance.**
- Detector parameter schemas are round-trip safe: a generated plan from `detector_parameter_schema` applied via `create_av_detector_full` or `create_appdata_detector_full` produces a detector that readback verification confirms.
- Archive policy updates are diff-rendered before apply, descriptor-backed, and snapshot-rollback guarded.

**Design and plan.**
- Design/spec: `docs/superpowers/specs/2026-05-19-phase-5e-detectors-archive-policies-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-05-19-phase-5e-detectors-archive-policies.md`.
- Live evidence: `docs/api-audit/phase-5e-detector-archive-smoke-latest.md`.

**Fixture debt.** `archive_policy_get` needs a descriptor that exposes policy-like fields, AV-detector visual mutation needs a writable visual child, and `archive_policy_update` needs an isolated `codex-*` archive/camera fixture. Archive maintenance no-op is verified only with `codex-nonexistent-*` volume ids; real maintenance remains approval-gated.

---

### Phase 5F — Operator UX: Security, users, roles, system health

**Why.** Closes 11 pending SecurityService methods, 10 pending AuthenticationService methods, 5 pending LicenseService methods, NodeNotifier (6 pending), and DomainNotifier (5 pending).

**Scope.**
- `users_list()` / `user_create(plan)` / `user_update(plan)` / `user_delete(id)` — promoted from `temp_user` smoke.
- `roles_list()` / `role_create(plan)` / `role_update(plan)` / `role_delete(id)` — promoted from `temp_role` smoke.
- `permission_set(target, role_id, plan)` — already verified shape.
- `tfa_enable(user_id, plan)` / `tfa_disable(user_id, plan)` — fixture-needed; ships with `status: fixture-needed` until OTP fixture is approved.
- `ldap_directory_add(plan)` / `update` / `remove` — already verified.
- `ldap_sync(directory_id)` — fixture-needed.
- `license_status()` / `license_apply(file)` — license_apply is approval-gated.
- `system_health()` — composite of node status, disk space, replication status, backup status, license, time zone.
- `domain_event_subscribe(filter, duration)` — DomainNotifier / NodeNotifier streams with bounded reads.

**Acceptance.**
- Security and admin mutations match the existing `mutation-playbooks/users-roles-security.md` flow.
- `system_health` returns a single JSON document that maps to the desktop client's status overview.

---

### Phase 6A — Authoring kit expansion: more templates, more languages

**Why.** Today's generator emits 8 Python templates. Customers want Node/TypeScript and C#, and they want higher-level templates than raw consumers.

**Scope.**
- New templates (each verified against demo stand with end-to-end smoke):
  - `alarm_responder` — subscribe to alarms, run handler, ack via `alarm_complete`.
  - `ptz_controller` — bounded PTZ commands triggered by event or HTTP webhook.
  - `ml_detector_bridge` — receives metadata from an external ML model and injects via `external_event_producer`.
  - `scheduled_exporter` — cron-style scheduled archive export with rotation.
  - `dashboard_backend` — small FastAPI/Express server that aggregates inventory + events for a custom UI.
  - `plugin_scaffold` — full runnable repo with auth, retry, telemetry, tests, CI.
- Multi-language: Python (existing) + Node/TypeScript + C# (new). All three use shared schema definitions, so adding a fourth language is mostly a renderer change.
- Static verifier extended to all three languages: rejects embedded secrets, missing caps, disallowed imports, unsafe HTTP defaults.
- Bundle signing: optional `--sign` flag that emits a manifest with hashes so distributors can pin templates.

**Acceptance.**
- All 6 new templates produce runnable bundles in all 3 languages → 18 generator smokes pass against `<demo-host>`.
- Existing 8 templates also gain Node and C# variants (24 more smokes). Total smoke surface for generators: 8 + 6 = 14 templates × 3 languages = 42 bundles.

---

### Phase 6B — Partner SDK kit and distribution

**Why.** Make the MCP a first-class plugin platform.

**Scope.**
- `scaffold_plugin(name, capabilities, language)` — emits a complete plugin repo with: MCP entrypoint, env-only credential loader, AxxonApiClient wrapper, tests, CI workflow, README, LICENSE template, sample integration.
- `plugin_lint(path)` — static lint that runs the existing verifier plus repo-level checks (no committed secrets, env example present, tests present, README has safety section).
- `plugin_package(path, format)` — produces a distributable artifact (`.whl`, `.tar.gz`, `.zip`) and a manifest with capability list and SHA-256 of every file.
- Distribution scaffolding: a `customer-templates/` folder in this repo that holds reference plugins (one per language) which CI keeps green against the demo stand.

**Out of scope.** Hosting / registry (that is a separate product decision).

**Acceptance.**
- A new contributor can run `scaffold_plugin → plugin_lint → plugin_package` and end up with a runnable plugin that connects to `<demo-host>` and lists cameras within 5 minutes of clone.

---

### Phase 7 — NL → plan translator and recipe assembler

**Why.** The headline value of the MCP for an LLM-using customer: "describe in English, get a verified plan."

**Scope.**
- `assemble_recipe(intent_text, context)` — given an English intent (e.g. "add a camera at 10.0.0.5 with face detection and 7-day archive"), returns a sequenced plan that references existing operator workflows. Does **not** execute.
- `validate_recipe(plan)` — checks every step against the schema of the referenced workflow, flags fixture gaps, byte/time caps, and missing approvals.
- `explain_recipe(plan)` — produces a human-readable preview with risk classification, rollback strategy, and estimated wall-clock time.
- Recipe execution still goes through the existing `apply_operator_plan` per step. The translator never invents API shapes — it only composes known workflows.

**Acceptance.**
- For 10 reference intents (camera + detector, alarm responder, export schedule, layout + map, role + permission, etc.), `assemble_recipe → validate_recipe → apply` round-trips successfully against `<demo-host>` with rollback verified.

---

## 6. Cross-cutting work (applies to every phase)

These items are not phases on their own — they are extended in every phase.

| Concern | What grows each phase |
| --- | --- |
| Safety policies | New `safety_policies.json` entries for every new tool: risk class, default caps, required approvals, rollback strategy. |
| Coverage matrix | New row(s) in `pdf-gap-coverage-matrix.md` with status, risk, tooling, report, next step. |
| Evidence | New `docs/api-audit/phase-X-*-latest.md` reports, sanitized. |
| Unit tests | New tests under `tools/tests/` for every tool's argument validation, cap enforcement, and redaction. |
| Smokes | New `axxon_*_smoke.py` script per phase, runnable against the demo stand. |
| Docs corpus | `api_methods.json` `live_status` field flips from `pending` → `tested-pass` (or `tested-warn-fixture-needed`) as evidence lands. |
| Sanitization | Every committed artifact scrubs concrete host IPs, users, CA paths, passwords, tokens, and TLS CNs; intrinsic `hosts/Server/...` UIDs may remain unless they identify sensitive customer data. |

---

## 7. Dependencies and ordering rationale

```
Phase 5A (live/archive view)   ─┐
                                ├─► Phase 5C (alarms) ─┐
Phase 5B (PTZ, fixture-gated) ─┘                       │
                                                       ├─► Phase 7 (NL translator)
Phase 5D (videowall/layouts/maps) ─┐                   │
                                    ├─► Phase 5E (det) ─┤
Phase 5F (security/health) ────────┘                   │
                                                       │
Phase 6A (templates × langs) ─────► Phase 6B (SDK) ────┘
```

- **5A first** because everything else uses live media + archive primitives.
- **5B can run in parallel with 5C/5D** but is fixture-gated, so it cannot block the critical path.
- **5E depends on 5D** (layouts/maps surface) and on 5A (archive primitives).
- **6A/6B can run in parallel with 5C–5F** once 5A's primitives are stable.
- **7 is last** because it composes everything else.

---

## 8. Risks and open questions

| Risk | Mitigation / what we still need to decide |
| --- | --- |
| PTZ / Tag&Track / control panels / TFA / WebSocket `/events` / client HTTP API for layouts are fixture-blocked on the demo stand. | Each phase ships with `status: fixture-needed` paths that are clean no-ops with clear evidence, and tools auto-detect via `axxon_fixture_discovery.py`. We decide per-phase whether to procure a fixture or ship fixture-gated. |
| Desktop client has interactive elements (joystick drag, mosaic drag-drop, hot zones) that have no obvious 1:1 API. | These are out of scope. The MCP exposes the underlying capability (PTZ move, layout cell content, map marker position) — building a graphical client on top is a different product. |
| Multi-language template explosion (14 × 3 = 42 bundles to keep green). | Shared schema; CI matrix; language-specific renderers are thin. Static verifier is the single source of truth for safety. |
| NL → plan translator could hallucinate API shapes. | Translator only composes registered workflows; `validate_recipe` rejects anything outside the registry; `explain_recipe` shows the exact RPC sequence before apply. |
| Copyright on proto and PDF material. | Existing rule holds: `docs/integration-apis-3.0/` and `docs/grpc-proto-files/` stay gitignored. Only audit tooling and evidence we author are public. |
| Demo-stand drift (objects change, archives roll). | Smokes already use `codex-*` temporary IDs with rollback. Sanitization rules already in place. |
| Concurrent operators on the same stand. | All mutating tools use ETag where the API supports it; the apply token is per-plan; rollback verifies object state before reverting. |

Open questions to confirm with the user before Phase 5A spec:

1. Should `live_view` return media URLs the caller fetches, or should the MCP proxy bytes (and apply byte caps inline)? Existing media smokes use both shapes; we need to pick one default.
2. Do we want Node/TypeScript and C# in Phase 6A, or just Node first?
3. Is the private demo stand the only verification target, or will partners be expected to bring their own stand for CI?

---

## 9. Definition of done for the overall roadmap

The full-coverage MCP is "done" when:

1. `api_methods.json` shows ≤ 20 `pending` methods (the remainder are documented fixture-blocked, not unknown).
2. PDF coverage matrix has no `not-verified` rows; any `partial` or `fixture-needed` rows are backed by explicit fixture debt and next steps.
3. Every desktop-client capability category in section 2.4 has a corresponding MCP tool (or a documented fixture-gated stub).
4. The authoring kit ships at least one runnable reference plugin per supported language, all green against `<demo-host>`.
5. The NL translator passes its 10-reference-intent suite.
6. Unit tests stay 100% green; smokes pass against the demo stand from a clean clone.

---

## 10. Immediate next step

This document is a roadmap, not an implementation plan. The next step is:

1. **Start Phase 5F planning** for security, users, roles, system health, and schedules.
2. **Carry Phase 5E fixture debt** as a separate validation track: descriptor-backed archive policy fixture, writable visual detector child, and isolated `codex-*` archive/camera fixture.
3. Keep the loop for each phase: implementation, evidence, sanitization, coverage matrix update, merge.
