# Axxon One MCP — Full-Coverage Roadmap

**Date:** 2026-05-16 (original) · **Reconciled against `main`:** 2026-06-09
**Status:** Active roadmap
**Spec type:** multi-phase roadmap (decomposition doc, not a single implementation spec)

> **Reconciliation note (2026-06-09).** The original roadmap's status tables were written
> when ~146/361 RPCs were verified and Phases 5C–5F were "not started." The codebase has
> since shipped all of those phases. This document has been rewritten against the actual
> repo so the numbers match `STATUS.md`, `docs/COVERAGE.md`, and
> `docs/api-audit/mcp-corpus/api_methods.json`. The phase plan below now reflects only the
> *remaining* work.

---

## 1. Goal (verbatim from the user)

> Create an MCP server for Axxon One VMS that covers ALL functionalities and everything that
> the gRPC API can give. Everything the desktop client can do — view, operate/configure,
> receive events, snapshots, video flows, add cameras/detectors/layouts, use client API and
> all others — so customers and partners can:
>
> - operate with the VMS backend and frontend more easily,
> - create plugins or tools (Python for example) more easily,
> - make vertical or horizontal integrations with other software,
> - configure the product (add cameras, configure them aligned with documentation, add
>   detectors and configure them, etc.).

---

## 2. Where the project actually is (2026-06-09)

Numbers are pulled from the repo, not prose. See `STATUS.md` for the regeneration commands.

| Metric | Value |
| --- | ---: |
| gRPC services | 51 |
| gRPC RPCs total | 361 |
| RPCs live-verified | 283 (78%) |
| RPCs fixture-blocked | 58 |
| RPCs pending | 20 |
| MCP tools registered | 255 |
| Capability groups | 37 |
| Services with a dedicated tool group | 33 / 51 |
| Offline unit tests | 976 passing |

**All four original layers shipped and went well past the original plan:**

| Layer | State |
| --- | --- |
| Knowledge (docs / search / examples / recipes) | shipped |
| Live read-only inventory + events + bounded streams | shipped |
| Operator (plan / apply / verify / rollback) — cameras, detectors, layouts, maps, macros, alarms, PTZ, videowall, settings, users/roles, archive policy | shipped |
| Generator (Python + Node integration skeletons, partner plugin scaffolds) | shipped |
| NL → operator recipe translator (`assemble_recipe`, `validate_recipe`) | shipped (early form) |

Original Phases 5A (live/archive view), 5C (alarms), 5D (videowall/layouts/maps),
5E (detector + archive depth), and 5F (security/users/system-health) are **done and on
`main`**. 5B (PTZ) shipped as a tool group; its remaining methods are fixture-blocked, not
unbuilt.

---

## 3. The remaining gap (re-derived from the current repo)

The headline coverage number (78% verified) understates the real remaining work in one
direction and overstates it in another:

1. **Verified ≠ callable.** 18 of 51 services have **no dedicated MCP tool group**. Ten of
   those have RPCs that pass live but cannot be invoked by an LLM through a tool. This is the
   highest-value gap for the "everything the desktop client can do" goal — the API works, it
   just isn't exposed. (Full list in `STATUS.md` §3.)
2. **58 fixture-blocked RPCs** need hardware / driver / infra the stand lacks (PTZ device
   modes, TFA/OTP, control panels, water-level, Tag&Track tracker, isolated archive volume).
3. **20 pending RPCs** are deliberately-deferred destructive / infra operations (license
   distribute/drop, node add/drop/proclaim, config revision set / restore, cloud bind,
   backup make/cancel, email/SMS send, installer download).

### 3.1 Verified-but-no-tool services (the expose-as-tool backlog)

| Service | Verified RPCs | User value |
| --- | --- | --- |
| DevicesCatalog | `ListVendors(V2)`, `ListDevices(V2)`, `GetDevice` | driver/vendor catalog for "add a camera aligned with the docs" |
| SharedKVStorageService | `ListRecords`, `BatchGetRecords`, `Commit`, `GetRecordsStream` | plugin / integration shared state |
| FileSystemBrowser | `ListDirectory`, `GetFileInfo`, `GetSpace` | export-path picking, storage UX |
| ConfigurationManager | `GetRevisionInfo`, `CollectBackup` | config revision history + backup (read) |
| GlobalTrackerService | `GetProfile` (rest fixture-blocked) | cross-camera tracking profiles |
| StatisticService | `GetStatistics` | stream / server health for dashboards |
| EventDescription | `GetEventGroupingTags` | event taxonomy for filter building |
| DomainManager | `EnumerateNodes` (mutations pending) | multi-node topology read |
| NgpNodeService | `ListSceneDescription` | scene geometry for analytics |
| InstallationPackageProvider | `CheckPackageAvailability` | update / package availability |

---

## 4. Design constraints (unchanged — carried from the repo)

1. **Everything on by default; `--read-only` restricts to reads.** Per-group `--enable-*`
   flags + `AXXON_*_APPROVE` env vars give fine-grained control.
2. **Plan → apply → verify → rollback** for every mutation; every mutation requires a
   per-call confirmation token.
3. **Bounded streams** — byte, time, and frame caps on every subscription / media / export.
4. **Secrets in memory only**; generated code reads credentials from env, never arguments.
5. **Sanitized evidence** — host / user / CA / tokens / passwords scrubbed before commit;
   `AXXON_TLS_CN=Server` and `hosts/Server/...` UIDs may remain.
6. **No copyrighted source in the repo** — protos, the Integration APIs PDF, and the CA stay
   gitignored.
7. **Reuse `AxxonApiClient`** (direct gRPC with TLS override, HTTP `/grpc`, legacy HTTP, `/v1`).
8. **No defensive programming** unless a user-facing safety guarantee depends on it.

---

## 5. Remaining phases

Order reflects user value, then dependency. Each phase still runs the repo proof loop
(freeze spec → build TDD → evidence → fresh verify → fix) and ends with updated coverage
numbers, sanitized evidence under `docs/api-audit/`, new unit tests, and a stand smoke.

### Phase A — Expose the verified-but-no-tool services

**Why first.** Pure upside: 10 services already pass live; wrapping them turns working RPCs
into LLM-callable capabilities with no fixture or infra dependency. Closes the single
largest "the desktop client can do this but the MCP can't" gap.

**Scope (one tool group per service, reads first):**
- `devices_catalog` — `list_vendors`, `list_devices`, `get_device` (the camera-driver catalog).
- `shared_kv` — `list_records`, `get_records`, `commit_record` (plugin state; `commit` is mutating → confirmation token).
- `filesystem_browser` — `list_directory`, `get_file_info`, `get_space` (read-only, byte-capped listing).
- `statistics` — `get_statistics` (stream/server health).
- `config_revisions` — `get_revision_info`, `collect_backup` (read; `collect_backup` byte-capped).
- `event_taxonomy` — `get_event_grouping_tags`.
- `domain_topology` — `enumerate_nodes` (read; node add/drop stays pending/gated).
- `scene_description` — `list_scene_description`.
- `package_availability` — `check_package_availability`.
- `global_tracker` — `get_profile` read tool (rest documented fixture-needed).

**Acceptance.** Each new group has argument-validation + redaction unit tests, a stand smoke
that returns real data (or a clean fixture-needed report), and flips the service's `tool
group?` to `yes` in `STATUS.md`. `devices_catalog` additionally feeds the camera-add recipe.

### Phase B — Close fixture-blocked RPCs (fixture procurement track)

**Why.** 58 RPCs are one fixture away from `tested-pass`. This is infra, not code.

**Scope.** Per fixture, document the exact required object and either procure it on the stand
or ship the tool with an auto-detected `status: fixture-needed`:
- PTZ-capable device → 10 TelemetryService methods + 4 TagAndTrackService methods.
- TFA / OTP fixture → Securityize Google-auth + AuthenticationService federated flows.
- Control panel + water-level device → StateControlService.
- Isolated `codex-*` archive volume → ArchiveService maintenance, archive policy update.
- GlobalTracker profile fixture → 6 GlobalTrackerService methods.

**Acceptance.** Each fixture either flips its RPCs to `tested-pass` with sanitized evidence,
or the tool ships fixture-gated with a precise required-object list auto-detected at runtime.

### Phase C — Wire the pending destructive / infra RPCs behind hard gates

**Why.** The 20 pending RPCs are the last of the desktop-client surface (multi-node domain,
license distribution, config restore, email/SMS notifications, cloud bind, backup).

**Scope.** Expose each only through the operator plan/apply/verify/rollback flow, with:
- explicit approval env var per group,
- dry-run plan that never mutates,
- rollback or "irreversible — no rollback" classification surfaced in the plan,
- email/SMS gated on an SMTP/GSM fixture (ship fixture-needed otherwise).

**Acceptance.** No pending RPC is callable without an approval flag + per-call token; every
irreversible op is labeled as such in its plan output.

### Phase D — Authoring kit + partner SDK depth

**Status (reconciled 2026-06-09): the template/language work is already shipped.** The generator
has **13 templates, each in Python AND Node/TypeScript** (`tools/templates/*.{py,ts}.tmpl`),
including the ones this section originally listed as "to build": `alarm_responder`,
`scheduled_exporter`, `dashboard_backend`, `ml_detector_bridge`, `external_event_producer`,
`webhook_bridge`, `inventory_sync`, plus `plugin_scaffold`. The partner SDK kit
(`scaffold_plugin` / `plugin_lint` / `plugin_package`) and the static verifier
(`verify_integration` / `verify_dir`, rejecting embedded secrets, missing caps, unsafe HTTP
defaults) are also shipped. Tools: `list_integration_templates`, `generate_integration`,
`verify_integration`, `scaffold_plugin`, `plugin_lint`, `plugin_package`.

**Remaining (not yet built).**
- **C# as a third language** — entirely absent today (no `.cs.tmpl`, no `csharp` branch). Full C#
  parity = a `.cs.tmpl` + a `csharp` build branch for each of the 13 templates, a `.csproj`
  dependency emitter, a `csharp` CI branch, `csharp` static-verifier rules, and `"csharp"` added
  to each template's `languages`. Deferred (large mechanical surface; C# can't be compile-verified
  on this stand).
- **Bundle signing** — optional `--sign` flag emitting a manifest with per-file hashes so
  distributors can pin templates. Not yet implemented.
- **`ptz_controller` template** — listed originally; not present (PTZ has tool coverage but no
  generator template).

**Acceptance.** Every shipped template produces a runnable bundle; the static verifier is the
single source of truth for safety. (Both already hold for Python + Node.)

### Phase E — NL → plan translator depth (deepen the existing `assemble_recipe`)

**Why.** The translator exists in early form. The headline value is "describe in English, get
a verified plan" across *all* operator workflows.

**Scope.** `assemble_recipe` composes only registered workflows; `validate_recipe` rejects
anything outside the registry and flags fixture gaps / caps / missing approvals;
`explain_recipe` shows the exact RPC sequence + rollback strategy before apply. Translator
never invents API shapes.

**Acceptance.** A reference suite of 10 intents (camera + detector, alarm responder, export
schedule, layout + map, role + permission, …) round-trips assemble → validate → apply with
rollback verified against the stand.

---

## 6. Cross-cutting (every phase)

| Concern | Grows each phase |
| --- | --- |
| Safety policies | new `safety_policies.json` entry per tool: risk class, caps, approvals, rollback |
| Coverage | `api_methods.json` `live_status` flips `pending`/`fixture` → `tested-pass`; `STATUS.md` §3 `tool group?` flips to `yes` |
| Evidence | new sanitized `docs/api-audit/phase-*-latest.md` |
| Tests | new `tools/tests/` cases for argument validation, cap enforcement, redaction |
| Smokes | new `axxon_*_smoke.py` per phase, runnable against the stand |

---

## 7. Ordering

```
Phase A (expose verified services)  ── highest value, no fixtures
Phase B (fixtures) ─┐
Phase C (gated destructive) ─┤
                    ├─► Phase E (NL translator depth) ── composes everything
Phase D (templates + SDK) ──┘
```

- **A first** — pure upside, unblocks the camera-add recipe via `devices_catalog`.
- **B and C** are infra/risk tracks that can run in parallel with D.
- **E last** — it composes the workflows the other phases register.

---

## 8. Definition of done

1. `api_methods.json` shows ≤ 20 `pending` methods, each documented as deliberate.
2. Every service with a verified RPC has a dedicated tool group (`STATUS.md` §3 has no
   bold "verified-but-no-tool" rows).
3. Every fixture-blocked RPC is either flipped to `tested-pass` with evidence or ships
   fixture-gated with an auto-detected required-object list.
4. The authoring kit ships at least one runnable reference plugin per supported language.
5. The NL translator passes its 10-reference-intent suite.
6. Unit tests stay green; smokes pass from a clean clone.

---

## 9. Immediate next step

Start **Phase A** (expose the 10 verified-but-no-tool services), leading with
`devices_catalog` because it directly serves "add a camera aligned with the documentation."
Carry the fixture debt (Phase B) and the gated-destructive backlog (Phase C) as parallel
tracks.
