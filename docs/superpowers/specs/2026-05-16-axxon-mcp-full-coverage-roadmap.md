# Axxon One MCP — Full-Coverage Roadmap

**Date:** 2026-05-16 (original) · **Reconciled against `main`:** 2026-06-11
**Status:** Phases A, B (attainable), D, E done. Only Phase C remains in this phase plan (blocked on user).
**Spec type:** multi-phase roadmap (decomposition doc, not a single implementation spec)

Canonical service-by-service target map: [`docs/ALL_IN_ONE_VMS_API_ROADMAP.md`](../../ALL_IN_ONE_VMS_API_ROADMAP.md).

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

## 2. Where the project actually is (2026-06-10)

Numbers are pulled from the repo, not prose. See `STATUS.md` for the regeneration commands.

| Metric | Value |
| --- | ---: |
| gRPC services | 51 |
| gRPC RPCs total | 361 |
| RPCs live-verified | 286 (79%) |
| RPCs fixture-blocked | 55 |
| RPCs pending | 20 |
| MCP tools registered | 291 all-enabled runtime tools |
| Capability groups | 47 |
| Generator templates | 14 (each Python + Node) |
| Services with intent-level tool coverage | 44 / 51 |
| Offline unit tests | 1106 passing |

**All four original layers shipped and went well past the original plan:**

| Layer | State |
| --- | --- |
| Knowledge (docs / search / examples / recipes) | shipped |
| Live read-only inventory + events + bounded streams | shipped |
| Operator (plan / apply / verify / rollback) — cameras, detectors, layouts, maps, macros, alarms, PTZ, videowall, settings, users/roles, archive policy | shipped |
| Generator (Python + Node integration skeletons, partner plugin scaffolds) | shipped |
| NL → operator recipe translator (`assemble_recipe`, `validate_recipe`, `resolve_device`, `run_recipe`) | shipped (Phase E depth) |

Original Phases 5A (live/archive view), 5C (alarms), 5D (videowall/layouts/maps),
5E (detector + archive depth), and 5F (security/users/system-health) are **done and on
`main`**. 5B (PTZ) shipped as a tool group; its remaining methods are fixture-blocked, not
unbuilt.

---

## 3. The remaining gap (re-derived from the current repo)

The verified-but-no-tool backlog (10 services with live RPCs that an LLM could not call) is
**closed** — Phase A exposed all 10 as tool groups, and the pre-existing groups were swept
live with 0 drift / 0 fail (`docs/api-audit/preexisting-tools-audit-latest.md`). What remains
is infra-blocked or deliberately deferred:

1. **55 fixture-blocked RPCs** need hardware / driver / infra the stand lacks (PTZ device
   modes, TFA/OTP, control panels, water-level, a configured Tag&Track component, isolated
   archive volume, LDAP server). Code is ready; fixtures are not.
2. **20 pending RPCs** are deliberately-deferred destructive / infra operations (license
   distribute/drop, node add/drop/proclaim, config revision set / restore, cloud bind,
   backup make/cancel, email/SMS send, installer download). These are Phase C, gated on the
   user.

### 3.1 The 10 verified-but-no-tool services — now exposed (Phase A)

These all flipped to `tool group? = yes` in `STATUS.md` §3:

| Service | Tool group | Verified RPCs |
| --- | --- | --- |
| DevicesCatalog | `devices_catalog` | `ListVendors(V2)`, `ListDevices(V2)`, `GetDevice` |
| SharedKVStorageService | `shared_kv` | `ListRecords`, `BatchGetRecords`, `Commit`, `GetRecordsStream` |
| FileSystemBrowser | `filesystem_browser` | `ListDirectory`, `GetFileInfo`, `GetSpace` |
| ConfigurationManager | `config_revisions` | `GetRevisionInfo`, `CollectBackup` |
| GlobalTrackerService | `global_tracker` | `GetProfile` (rest fixture-blocked) |
| StatisticService | `statistics` | `GetStatistics` |
| EventDescription | `event_taxonomy` | `GetEventGroupingTags` |
| DomainManager | `domain_topology` | `EnumerateNodes` (mutations pending) |
| NgpNodeService | `scene_description` | `ListSceneDescription` |
| InstallationPackageProvider | `package_availability` | `CheckPackageAvailability` |

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

## 5. Phase status

A, B (attainable subset), D, and E are **done and on `main`**, each through the proof loop
with sanitized evidence under `docs/api-audit/`. Only **Phase C** (destructive/infra RPCs)
remains as buildable work, and it is blocked on the user's go-ahead + throwaway targets.
The fixture-procurement tail is infra-blocked, not code.

### Phase A — Expose the verified-but-no-tool services — DONE

All 10 services now have a dedicated tool group (`devices_catalog`, `shared_kv`,
`filesystem_browser`, `statistics`, `config_revisions`, `event_taxonomy`, `domain_topology`,
`scene_description`, `package_availability`, `global_tracker`), each with validation/redaction
tests and a live smoke. Evidence: `docs/api-audit/phase-a-*-latest.md`. See `STATUS.md` §3.

### Phase B — Close fixture-blocked RPCs — attainable subset DONE; rest infra-blocked

Closed what the stand can satisfy: PTZ telemetry verification (move + presets with position
rollback), `state_control` (gated SetState), and GDPR cleanup. Evidence:
`docs/api-audit/phase-b-*-latest.md`. The remaining 55 fixture-blocked RPCs need hardware/infra
the stand lacks (PTZ device modes, TFA/OTP, control panel, isolated archive volume, GlobalTracker
profile, LDAP server). Tag&Track specifically needs a Tag&Track *component* configured on the
stand — the stand has trackers and PTZ but no bound Tag&Track unit, so `ListTrackers` resolves
nothing. These flip to `tested-pass` only as fixtures are procured.

### Phase D — Authoring kit + partner SDK depth — DONE

14 generator templates, each in Python AND Node (`tools/templates/*.{py,ts}.tmpl`), including
`alarm_responder`, `scheduled_exporter`, `dashboard_backend`, `ml_detector_bridge`,
`ptz_controller`, plus the consumer/producer/bridge set and `plugin_scaffold`. The partner SDK
(`scaffold_plugin` / `plugin_lint` / `plugin_package`) and the static verifier
(`verify_integration` / `verify_dir`) are shipped; `plugin_package` produces a versioned
`name-version/` archive with an embedded SHA-256 `manifest.json` and pinned dependencies.
**Deferred by choice:** bundle signing (no untrusted distribution channel to protect) and a
C# language branch (large mechanical surface, not compile-verifiable on this stand).

### Phase E — NL → plan translator depth — DONE

`assemble_recipe` composes only registered workflows; `validate_recipe` flags fixture gaps /
caps / missing approvals; `resolve_device` and `run_recipe` (dry by default) added. Evidence:
`docs/api-audit/phase-e-translator-depth-latest.md`.

### Phase C — Wire the pending destructive / infra RPCs behind hard gates — NOT STARTED (blocked on user)

**Why.** The 20 pending RPCs are the last of the desktop-client surface (multi-node domain,
license distribution, config restore, email/SMS notifications, cloud bind, backup).

**Scope.** Expose each only through the operator plan/apply/verify/rollback flow, with:
- explicit approval env var per group,
- dry-run plan that never mutates,
- rollback or "irreversible — no rollback" classification surfaced in the plan,
- email/SMS gated on an SMTP/GSM fixture (ship fixture-needed otherwise).

**Acceptance.** No pending RPC is callable without an approval flag + per-call token; every
irreversible op is labeled as such in its plan output.

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

A → D → E shipped in that order (highest value first, translator last since it composes the
rest). B's attainable subset shipped alongside; its remainder is fixture-blocked. C is the
only buildable phase left and is gated on the user (destructive ops need explicit go-ahead +
throwaway targets).

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

Within this historical phase plan, nothing is actionable without input. The only buildable
phase left is **Phase C** (wire the 20 pending destructive/infra RPCs behind hard gates),
which needs the user's explicit go-ahead plus throwaway targets before any work starts.
The fixture-blocked tail advances only as the stand gains hardware/infra. Broader future
capability polish is tracked in `docs/ALL_IN_ONE_VMS_API_ROADMAP.md`.
