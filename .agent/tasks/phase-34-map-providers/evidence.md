# Evidence Bundle: phase-34-map-providers

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-07

## AC1 - gated module + gate matrix - PASS
- tools/axxon_mcp_map_providers.py defines AxxonMcpMapProviders with env
  AXXON_MAP_APPROVE=1 + token CONFIRM-map-providers. _write_gate returns disabled
  (env off) / gap (bad token) / None before any wire call.
- Proof: tests test_disabled_when_env_off / test_gap_on_bad_token; live gate matrix
  (raw/live-verify.txt).

## AC2 - configure_map_providers gated tool - PASS
- Calls MapService.ConfigureMapProviders; changed[] -> MapProvider (from
  MapProvider_pb2; api_key/copyright wrapped as StringValue), removed[] -> ids.
  Returns applied + changed_ids/removed_ids/etags. Empty changed AND removed -> error
  no wire. Ids normalized uppercase (server is case-sensitive).
- Proof: test_create_applied_records_provider / test_remove_applied /
  test_error_on_empty_no_wire; live create+remove (raw/live-verify.txt).

## AC3 - get_map_provider read tool - PASS
- Calls MapService.GetMapProvider; returns provider {id,name,etag,map_types_count}.
  Missing provider_id -> error no wire.
- Proof: test_get_map_provider_shape / test_get_missing_id_is_error_no_wire; live get
  ok then NOT_FOUND after remove (raw/live-verify.txt).

## AC4 - 6-edit wiring + suite green - PASS
- create_server param map_providers, conditional register_map_providers_tools,
  register fn with 3 @server.tool, --enable-map-providers flag, flag-gated
  instantiation, create_server arg. map suite 8 OK; full suite Ran 844 OK
  (raw/test-integration.txt), up from 836. No secret leak.

## AC5 - corpus restamp + coverage doc - PASS
- ConfigureMapProviders + GetMapProvider -> tested-pass. Coverage 229 pass-class /
  106 pending / 26 fixture-warn; item 10u. Restamp dry-run 0 after --write. MapService
  now 11/11.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_map_providers" (import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_map_providers.py -v (8 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 844 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (2 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-34-map-providers/raw/build.txt
- .agent/tasks/phase-34-map-providers/raw/test-unit.txt
- .agent/tasks/phase-34-map-providers/raw/test-integration.txt
- .agent/tasks/phase-34-map-providers/raw/lint.txt
- .agent/tasks/phase-34-map-providers/raw/live-verify.txt

## Stand hygiene
- Reversible: a throwaway provider was created then removed; the 2 stock providers
  untouched. Writes default-off (env + token). No proto/CA/PDF committed; secrets
  env-only.

## Known gaps
- None for MapService (11/11 complete).
