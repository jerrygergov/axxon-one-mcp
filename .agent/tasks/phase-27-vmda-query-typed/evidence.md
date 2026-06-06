# Evidence Bundle: phase-27-vmda-query-typed

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — typed ExecuteQueryTyped request — PASS
- `vmda_query` in `tools/axxon_mcp_metadata.py` now imports Query_pb2 +
  Primitives_pb2, builds a typed `QueryDescription(motion_in_area=...)`, sends
  `ExecuteQueryTypedRequest(...)`, and iterates `stub.ExecuteQueryTyped`. The
  deprecated ExecuteQuery string path (and MomentQuest template/language) is
  removed.
- Proof: `test_vmda_query_binding_uses_typed_query` (asserts a QueryDescription
  with a motion_in_area polygon); live status=ok.

## AC2 — _motion_in_area_query helper + preserved behavior — PASS
- `_motion_in_area_query(query_pb2, primitive_pb2, polygon)` builds the typed
  QueryDescription from a normalized polygon (full-frame default). query_type gap
  (no wire), database discovery + gap, time-range derivation, interval/object cap,
  and result shape are all preserved.
- Proof: `test_vmda_query_polygon_points_passed_through`,
  `test_vmda_query_bad_type_refused`, `test_vmda_query_missing_database_is_gap`,
  `test_vmda_query_zero_results_ok`.

## AC3 — accurate docstrings — PASS
- `vmda_query` docstring (metadata module) and the server tool docstring now say
  ExecuteQueryTyped / typed motion-in-area, fixing a real prior mismatch where the
  docstring claimed Typed but the code called the deprecated form. No other tool
  changed.

## AC4 — unit + full suite green — PASS
- Metadata suite 9 OK (typed binding + polygon passthrough added). Full suite
  `Ran 801 tests ... OK` (raw/test-unit.txt).

## AC5 — corpus restamp + coverage doc — PASS
- ExecuteQueryTyped -> tested-pass. Coverage 206 pass-class / 117 pending / 38
  fixture-warn; VMDAService 3/4 (only Cleanup pending); item 10n. Restamp dry-run
  reports 0 after --write.

## Stand hygiene
- Read-only forensic query: nothing on the stand was created, changed, or deleted.
  No proto/CA/PDF committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`. Access points
  (hosts/Server/...) may stay.
