# Task Spec: phase-36-config-change

## Metadata
- Task ID: phase-36-config-change
- Created: 2026-06-07T07:46:20+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- AGENTS.md
- CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (ConfigurationService rows)
- tools/axxon_mcp_logic_alerts.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close the serviceable pending ConfigurationService
methods: ChangeConfig, ChangeConfigStream, ListSimilarUnits, BatchGetFactories. Add MCP
tools via a new gated module, mirroring the existing gated-module idiom (approval env +
confirmation token for mutations). Live-verify reversibly against the demo stand. Only
restamp methods the device actually services; leave environment-walled methods honest.

## Live probe findings (2026-06-07, demo stand)
- ChangeConfig: reversible round-trip on hosts/Server/DeviceIpint.1 `display_name`
  property (Tracker -> "Tracker [probe]" -> Tracker), failed=0 both directions. SERVICEABLE.
- ChangeConfigStream: same request shape, streamed response, reversible round-trip,
  failed=0 both directions. SERVICEABLE.
- ListSimilarUnits: returns valid ListSimilarUnitsResponse with next_page_token paging.
  SERVICEABLE (read).
- BatchGetFactories: reachable, returns structured items but status=NOT_FOUND for every
  unit_type/parent_uid combination tried on this build (DeviceIpint, AudioMonitor,
  GSMModule, EMailModule, VideoChannel; parents '', Server, hosts/Server, variants).
  Factory metadata is instead exposed via ListUnits display_mode=VM_WITH_FACTORY (already
  pass). ENVIRONMENT-WALLED -> fixture-warn, NOT restamped pass.

## Message shapes (confirmed live)
- ChangeConfigRequest{added, changed, removed, reset_units, force_add_units}; Unit{uid,
  type, properties[Property{id, value_string, ...}]}.
- ChangeConfigResponse{failed[Unit], failed_reason, added[str], added_macros, removed_macros}.
- ChangeConfigStream returns stream of ChangeConfigResponse.
- ListSimilarUnitsRequest{uid, node_name, page_size, page_token, search_mode}.
- ListSimilarUnitsResponse{similar_units[SimilarUnit{uid,type,display_name,display_id}], next_page_token}.
- BatchGetFactoriesRequest{factories[RequestedFactory{unit_type, parent_uid, ignore_possible_limits}]}.
- BatchGetFactoriesResponse{items[Item{requested, status(OK/NOT_FOUND/UNREACHABLE), factory}]}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_config_change.py exposes:
  list_similar_units (read), batch_get_factories (read), change_unit_property (gated write),
  change_unit_property_stream (gated write). connect helper + ensure_client + _write_gate
  match the logic_alerts idiom. Approval env AXXON_CONFIG_CHANGE_APPROVE=1, confirmation
  token CONFIRM-config-change.
- AC2: change_unit_property / change_unit_property_stream enforce the gate: env-off ->
  {"status":"disabled"} no wire call; bad token -> {"status":"gap"} no wire call; empty
  uid -> {"status":"error"} no wire call. Verified by unit tests asserting client.calls==[].
- AC3: Server wiring complete via the 6-edit pattern (create_server param, conditional
  register, register_config_change_tools with @server.tool entries, --enable-config-change
  flag, flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: ChangeConfig and ChangeConfigStream reversible round-trips
  (read original -> change -> verify changed -> restore -> verify restored), ListSimilarUnits
  returns a valid response. Raw transcript in raw/live-verify.txt with host/creds sanitized.
- AC5: Corpus restamp marks ChangeConfig, ChangeConfigStream, ListSimilarUnits as
  tested-pass; BatchGetFactories left tested-warn-fixture-needed (honest, not faked). Dry-run
  restamp reports 0 method(s) restamped after --write. Coverage doc updated.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- Mutations reversible and restored within the verification; no residual config change.
- Never fake live evidence; only restamp what the device services.
- .env stays gitignored and unstaged; sanitize the demo host -> <demo-host> and
  creds -> <redacted> in all committed artifacts.
- Smallest defensible diff; reuse public_config_summary and existing client helpers.
- Metadata-only tool surface; no raw blobs.

## Non-goals
- Unit creation/removal (added/removed/reset_units) beyond a reversible property change.
- Making BatchGetFactories pass (environment-walled on this build).
- Template/assignment RPCs (already covered or out of scope).

## Verification plan
- Build: python3.12 -c import of module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_config_change.py (reads, gate, no-leak).
- Integration tests: full suite via existing runner.
- Lint: ruff/existing lint command.
- Manual checks: live round-trip transcript (raw/live-verify.txt), restamp dry-run clean.
