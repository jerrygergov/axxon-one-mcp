# Phase 1 Coverage Reconciliation + Site Graph Spec

## Original Task Statement

Active TASK_ID: `phase-1-coverage-site-graph`

Freeze the repo-task-proof-loop spec at `.agent/tasks/phase-1-coverage-site-graph/spec.md` before implementation. Do not edit production code, tests, evidence, verdict, or problems files.

User clarified Phase 1 scope:

> Phase 1: Coverage Reconciliation + Site Graph. Build a unified site graph resource/tool joining cameras, archives, detectors, layouts, maps, permissions, health, access points, and event suppliers. This improves every future planner and integration generator.

## Source Reconciliation

- `AGENTS.md` and `CLAUDE.md` both require the repo-task-proof-loop sequence, with this spec frozen before implementation and all durable artifacts kept under `.agent/tasks/<TASK_ID>/`.
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` has no literal "Phase 1" heading. The user clarification is authoritative: Phase 1 means read-only coverage reconciliation plus a unified `site_graph` capability, not Phase C destructive or infrastructure work.
- The roadmap identifies the current domain/inventory gap as a higher-level site graph joining cameras, archives, detectors, layouts, maps, permissions, and health. It also lists `site_graph` among intent-polish backlog groups.
- `README.md` currently advertises 291 all-enabled MCP tools across 47 capability groups: 286 server-local tools plus 5 delegated translator tools.
- `docs/COVERAGE.md` currently reports 286 / 361 RPCs live-verified, 55 fixture-blocked, and 20 pending. Adding a high-level site graph does not by itself change per-RPC coverage unless the implementation also updates the authoritative corpus.
- Existing relevant surfaces are fragmented:
  - `tools/axxon_mcp_live.py`: cameras, archives, config units, detectors, appdata detectors, event suppliers, metadata endpoints, archive intervals, event types, detector kinds, bounded events and metadata.
  - `tools/axxon_mcp_view.py`: safe live/archive view helpers and DomainService batch reads for cameras/components, archives, and maps.
  - `tools/axxon_mcp_view_objects.py`: layouts, layout images metadata, maps, map images metadata, markers, map providers, and walls with byte caps and no raw image bytes.
  - `tools/axxon_mcp_admin.py`: security inventory, permissions, current-user security, license/time/system health, and bounded notifier reads with admin redaction helpers.
  - `tools/axxon_mcp_domain_topology.py`: read-only `DomainManager.EnumerateNodes`; mutations are intentionally not exposed.
  - `tools/axxon_mcp_devices_catalog.py`: read-only supported-device catalog, with default credentials intentionally omitted.
  - `tools/axxon_mcp_server.py`: capability group registry, `create_server` registration, CLI flags, open-by-default behavior, `--read-only`, and `list_capabilities`.
- There is currently no `tools/axxon_mcp_site_graph.py`, no `site_graph` capability group, and no `--enable-site-graph` flag.

## Assumptions

- Phase 1 is read-only coverage reconciliation plus the unified site graph capability.
- Phase 1 is not Phase C and must not expose destructive archive, backup/restore, license, cloud, domain-manager mutation, bulk onboarding, notification send, client/web API, export download, or tag-and-track work.
- The site graph may reuse existing helper functions/classes or shared client methods, but it must be independently enabled through its own capability group and must not require enabling `live`, `admin`, `view`, `view_objects`, `domain_topology`, or `devices_catalog` groups at runtime.
- Intrinsic Axxon object identifiers such as `hosts/Server/...` may appear in sanitized output. Secrets and secret-like material must not.
- The live stand configuration supplied by the user is for optional smoke verification only. The password and CA material must not be written into spec, evidence, logs, or artifacts.

## Acceptance Criteria

### AC1: New Read-Only Site Graph Module

Add `tools/axxon_mcp_site_graph.py` containing a read-only site graph implementation following the repository's dataclass-with-factories pattern.

The module must expose:

- `AxxonMcpSiteGraph`.
- `SITE_GRAPH_TOOL_NAMES`.
- `site_graph_connect_axxon_profile(profile: str = "env")`.
- `build_site_graph(...)`.

`site_graph_connect_axxon_profile` must support the existing `env` profile convention, lazy client construction, a redacted public connection summary, and `mode` set to `read-only` or `read`. Non-`env` profiles must return a `gap` response rather than attempting a connection.

### AC2: Unified Graph Content

`build_site_graph` must return one sanitized, deterministic response joining the currently fragmented live/view/admin/domain data into a graph useful to planners and generators.

At minimum, the response must include:

- `status`, `tool`, `summary`, `collections`, `nodes`, `edges`, `gaps`, and `source_sections`.
- Collections for cameras, archives, detectors, appdata detectors when present, layouts, maps, markers, permissions/security, health, access points, event suppliers, and metadata endpoints.
- Stable IDs for graph nodes, preferring access points, UIDs, layout IDs, map IDs, role IDs, and other intrinsic object identifiers.
- Deduplicated access points and event suppliers.
- Edges for the relationships the available data can infer, including camera-to-archive/source relationships, camera/detector/component relationships, detector-to-event-supplier relationships, layout/map references, map-to-marker/access-point references, permission-to-object references, node/host relationships, and health summaries.
- Counts in `summary` that reconcile with the returned collections and make missing or fixture-blocked sections visible.

The implementation may represent edges with a compact schema, but each edge must identify `source`, `target`, and `type`.

### AC3: Fixture-Aware Partial Results

The site graph must be fixture-aware. If optional live data is unavailable, unsupported by the stand, or blocked by missing proto/CA/client fixtures, `build_site_graph` must continue building the remaining graph and report the unavailable section in `gaps` or section status.

A section failure must not discard already collected sanitized data from unrelated sections. The top-level `status` must be `ok` when all requested sections succeed and `warn` when one or more optional sections are unavailable.

### AC4: Safety and Redaction

Site graph responses, docs examples, tests, smoke output, and task artifacts must not contain:

- Passwords, tokens, cookies, bearer values, session IDs, OTP/TFA secrets, authorization headers, or default device credentials.
- CA file contents, proto source text, private key material, license keys, hardware fingerprints, serial numbers, or machine IDs.
- Raw media bytes, raw map/layout image bytes, raw biometric vectors, or unbounded stream payloads.

Return metadata such as byte counts, caps, etags, object IDs, and intrinsic `hosts/Server/...` UIDs instead. Apply existing sanitizer/redaction helpers where possible and add site-graph-specific redaction for any fields not covered by existing helpers.

### AC5: Server Registration and Capability Discovery

Register the new capability in `tools/axxon_mcp_server.py` using the existing patterns.

Required behavior:

- `create_server` accepts a `site_graph` dependency.
- `CAPABILITY_GROUPS` includes key `site_graph`, example tool `build_site_graph`, and enable flag `--enable-site-graph`.
- `register_site_graph_tools` registers `site_graph_connect_axxon_profile` and `build_site_graph` only when a site graph instance is provided.
- `build_parser()` includes `--enable-site-graph` with read-only help text.
- `apply_enable_all()` and open-by-default behavior include the new flag through the existing generic enable-flag logic.
- `main()` instantiates `AxxonMcpSiteGraph` when `args.enable_site_graph` is true and passes it into `create_server`.
- `list_capabilities` reports `site_graph` correctly when disabled and enabled.

An optional resource `axxon://site-graph/summary` may be added only if it returns sanitized cached or freshly built metadata without introducing hidden live side effects. This resource is not required for PASS.

### AC6: Documentation and Count Reconciliation

Update documentation affected by the new group and tool count so it is internally consistent.

Required documentation updates:

- `README.md` must mention the `site_graph` capability and update all-enabled tool and capability-group counts to match the implemented registration.
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` must no longer describe site graph as only a future gap after implementation; it should identify the implemented Phase 1 read-only site graph and leave destructive/fixture-heavy gaps in the backlog.
- `docs/COVERAGE.md` must remain accurate. If no authoritative per-RPC status changes are made, the 286 / 361 RPC counts must remain unchanged and the docs must not imply new live RPC verification from the site graph alone.

If the implementation adds only the two required server-local tools and no delegated tools, the expected all-enabled runtime count becomes 293 MCP tools across 48 capability groups: 288 server-local tools plus 5 delegated translator tools.

### AC7: Unit Test Coverage

Add `tools/tests/test_axxon_mcp_site_graph.py` with focused offline tests using fake clients/fixtures.

Tests must cover:

- Connect behavior and redacted profile output.
- Building a graph from fake inventory with cameras, archives, detectors, appdata detectors, access points, event suppliers, layouts, maps, markers, permissions/security, and health.
- Correct summary counts, node IDs, and representative edge types.
- Deduplication of repeated access points and event suppliers.
- Fixture-aware partial results when one section raises or is absent.
- Secret/raw-byte redaction, including password/token/CA/license/serial-like fields and image/media bytes.

Extend `tools/tests/test_axxon_mcp_server.py` to cover:

- The `--enable-site-graph` parser flag.
- Disabled-by-default registration in docs-only `create_server`.
- Enabled registration of `site_graph_connect_axxon_profile` and `build_site_graph`.
- `list_capabilities` output for disabled and enabled `site_graph`.
- `--enable-all` / explicit flag parity continues to pass with the new flag.

### AC8: Optional Live Smoke

An optional live smoke script may be added as `tools/axxon_site_graph_smoke.py`.

If added, it must:

- Use environment variables for all live stand configuration.
- Write only sanitized output under `.agent/tasks/phase-1-coverage-site-graph/raw/`.
- Never write passwords, tokens, CA contents, license keys, proto files, raw images, or raw media.
- Treat transient live stand timeouts as retryable up to three attempts.

The smoke script is not required for unit-test PASS, and the implementation must not commit proto files, CA files, live credentials, or symlinks to them.

## Constraints

- Keep task artifacts under `.agent/tasks/phase-1-coverage-site-graph/`.
- Do not edit evidence, verdict, or problems files during implementation until the proof-loop phase requires them.
- Preserve the repository's existing patterns for client factories, lazy profile connection, caps, redaction, and `gap` responses.
- Keep the feature read-only. No confirmation token or mutation approval env var should be necessary for `site_graph`.
- Do not introduce new runtime dependencies unless already present in the repo or clearly justified by existing project patterns.
- Do not make live server credentials mandatory for offline unit tests or server startup.
- Do not alter authoritative API corpus status files unless actual coverage evidence is produced and reconciled in the appropriate proof-loop evidence phase.

## Non-Goals

- Phase C destructive operations: archive clear/format/reindex/delete, backup restore/set revision, domain add/drop/proclaim, license distribute/drop/document creation, cloud bind/unbind, destructive maintenance, or irreversible settings changes.
- Bulk onboarding/import planners, CSV camera onboarding, export job/download tools, notification send tools, Tag&Track, client-local HTTP API, WebSocket/web API groups, embeddable video components, or new generator templates beyond documentation references to site graph.
- Returning raw map/layout images, snapshots, video, media streams, biometric data, or unbounded event streams in the graph.
- Live verification against fixtures not available in the current stand as a prerequisite for unit-test PASS.

## Verification Plan

1. Red test pass before implementation, if feasible:
   - Add or run focused tests that initially fail for missing `axxon_mcp_site_graph`, `--enable-site-graph`, and `site_graph` capability registration.

2. Focused green checks after implementation:
   - `python3.12 -m unittest discover -s tools/tests -p 'test_axxon_mcp_site_graph.py'`
   - `python3.12 -m unittest tools/tests/test_axxon_mcp_server.py`

3. Capability/help checks:
   - `python3.12 tools/axxon_mcp_server.py --help | rg -- '--enable-site-graph'`
   - A small import/create-server check or unit assertion proving `list_capabilities` includes `site_graph` with `--enable-site-graph` when disabled and omits the enable flag when enabled.

4. Full required verification:
   - `python3.12 -m unittest discover -s tools/tests`

5. Optional live smoke, only after unit verification and only with sanitized artifacts:
   - Use the live stand environment supplied by the user, with the password redacted from all commands/artifacts.
   - Include `AXXON_HOST=100.76.150.18`, `AXXON_HTTP_URL=http://100.76.150.18`, `AXXON_USERNAME=root`, `AXXON_TLS_CN=Server`, `AXXON_CA=docs/grpc-proto-files/api.ngp.root-ca.crt`, and `AXXON_PROTO_DIR=docs/grpc-proto-files` in the local environment as needed.
   - Set `AXXON_PASSWORD` locally from the user-supplied value without writing it to repo files, shell history artifacts, evidence, or logs.
   - If `tools/axxon_site_graph_smoke.py` exists, run it with output under `.agent/tasks/phase-1-coverage-site-graph/raw/` and inspect the artifact for secret/raw-byte leakage before using it as evidence.
