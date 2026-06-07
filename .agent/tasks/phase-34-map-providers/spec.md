# Spec: phase-34-map-providers

## Original task statement
Complete MapService (currently 9/11). Close the two remaining methods:
ConfigureMapProviders (pending, a config write) and GetMapProvider (fixture-warn, a
read). Ship a new gated map-providers module with a gated configure tool and a read
tool. This brings MapService to 11/11.

Probe results (live, <demo-host>):
- ListMapProviders shows 2 real providers (Bitmap/vector, Google Map).
- Reversible round-trip verified: ConfigureMapProviders(changed=[MapProvider(id=<new
  guid>, name=...)]) creates it -> GetMapProvider(id) returns it ->
  ConfigureMapProviders(removed=[id]) deletes it -> GetMapProvider raises NOT_FOUND.
- MapProvider lives in MapProvider_pb2; the service stub is MapService.

## Acceptance criteria

- AC1: New module `tools/axxon_mcp_map_providers.py` defines `AxxonMcpMapProviders`
  with the gated idiom: env `AXXON_MAP_APPROVE=1` + token `CONFIRM-map-providers`.
  `_write_gate(confirmation)` returns disabled (env off) / gap (bad token) / None
  before any wire call.
- AC2: Gated tool `configure_map_providers(changed, removed, confirmation)` calls
  MapService.ConfigureMapProviders, where `changed` is a list of {id, name, api_key,
  copyright} dicts mapped to MapProvider and `removed` is a list of ids. Returns
  {status: applied, tool, changed_ids, removed_ids, etags}. Empty changed AND removed
  -> {status: error} with no wire call.
- AC3: Read tool `get_map_provider(provider_id)` calls MapService.GetMapProvider and
  returns {status: ok, tool, provider: {id, name, etag, map_types_count}}. Missing
  provider_id -> {status: error} no wire call.
- AC4: Server wired with the 6-edit pattern (--enable-map-providers flag, param,
  register, instantiation, create_server arg). Unit tests cover gate matrix + applied
  + read + error-no-wire + no-leak. Full suite green.
- AC5: Corpus restamp ("MapService","ConfigureMapProviders") and
  ("MapService","GetMapProvider") -> tested-pass; restamp dry-run 0 after --write.
  Coverage doc updated; MapService now 11/11. Live verify recorded (reversible:
  throwaway provider created then removed).

## Constraints
- Mutations approval-gated (env + token), default-off.
- Live verification reversible: any provider created is removed; nothing real touched.
- Reuse the groups/gdpr gating idiom and the 6-edit server pattern. MapProvider from
  MapProvider_pb2; stub from MapService.

## Non-goals
- MapService reads already covered in view_objects (list_map_providers etc.).

## Verification plan
- Build: pyimport smoke (server + new module)
- Unit tests: gate matrix + applied + read + error-no-wire + no-leak
- Integration tests: full suite discover
- Lint: n/a
- Manual checks: live create throwaway provider -> get -> remove -> confirm gone;
  gate disabled/gap; restamp dry 0 after write
