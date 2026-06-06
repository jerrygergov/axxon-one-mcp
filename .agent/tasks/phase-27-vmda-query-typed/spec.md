# Spec: phase-27-vmda-query-typed

## Original task statement
Close the pending VMDAService `ExecuteQueryTyped` method (the non-deprecated
replacement for the already-shipped, deprecated `ExecuteQuery`) so VMDAService
reaches 3/4 tested-pass (only the destructive `Cleanup` stays pending). The
existing `vmda_query` tool in `tools/axxon_mcp_metadata.py` currently calls the
deprecated `ExecuteQuery` with a MomentQuest query STRING, even though its
docstring already claims `ExecuteQueryTyped`. Switch it to `ExecuteQueryTyped`
with a structured `QueryDescription` (motion_in_area), fixing that real
code/docstring inconsistency, live-verify it, and restamp the corpus.

## Acceptance criteria
- **AC1**: `vmda_query` in `tools/axxon_mcp_metadata.py` builds a typed
  `QueryDescription` for `motion_in_area` — `QueryDescription(motion_in_area=
  MotionInArea(area=Polyline(points=[Point(x,y), ...], closed=True)))` from the
  `primitive` Point/Polyline messages — and sends
  `ExecuteQueryTypedRequest(access_point, camera_ID, schema_ID,
  dt_posix_start_time, dt_posix_end_time, query=QueryDescription)` via
  `stub.ExecuteQueryTyped`. The deprecated `ExecuteQuery` string path is removed.
- **AC2**: A private helper `_motion_in_area_query(pb2 modules, polygon)` builds
  the typed `QueryDescription` from a normalized [0,1] polygon (full-frame default
  when polygon is omitted), reusing the primitive Point/Polyline messages. The
  rest of `vmda_query` behavior is preserved: query_type gap for unsupported
  types (no wire call), database discovery + gap when none, the time-range
  derivation, the interval/object cap, and the returned result shape (status,
  camera_id, database, query_type, time_range, interval_count, object_count,
  intervals).
- **AC3**: The `vmda_query` docstring now accurately reflects ExecuteQueryTyped
  and the typed QueryDescription; no other tool's behavior changes. (The tool is
  already registered; no server registration change needed.)
- **AC4**: Unit tests in `tools/tests/test_axxon_mcp_metadata.py` cover, with a
  fake stub/pb2: vmda_query sends an ExecuteQueryTypedRequest (not ExecuteQuery)
  carrying a QueryDescription with a motion_in_area polygon; the unsupported
  query_type gap path (no wire call); and the result summarization from a fake
  interval stream. Full suite stays green.
- **AC5**: `tools/axxon_corpus_restamp.py` restamps `ExecuteQueryTyped` to
  `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json` reflects it
  (VMDAService 3/4 — EnumerateSchemes/ExecuteQuery/ExecuteQueryTyped pass, only
  Cleanup pending). Coverage doc count moves to 206 pass-class / 117 pending /
  38 fixture-warn and notes the typed VMDA query. Restamp dry-run reports 0 after
  `--write`.

## Constraints
- Probe-first already done: ExecuteQueryTyped live-verified read-only through
  direct gRPC against the stand. Built QueryDescription(motion_in_area=
  MotionInArea(area=full-frame Polyline)), sent ExecuteQueryTypedRequest against a
  real VMDA database + source (AVDetector.*/SourceEndpoint.vmda); the stream
  returned cleanly (0 intervals for an idle camera window, which is a valid empty
  result, not a failure). See raw/live-verify.txt.
- Wire shape: ExecuteQueryTypedRequest{access_point, camera_ID, schema_ID,
  dt_posix_start_time, dt_posix_end_time, QueryDescription query} -> stream of
  ExecuteQueryResponse{intervals, progress, origin}. QueryDescription has a oneof;
  motion_in_area is MotionInArea{Polyline area; EnterExit enter_exit}. Polyline is
  primitive {repeated Point points; bool closed; ...}; Point {double x; double y}.
- Read-only: a forensic archive query, no mutation, no rollback, no gate.
- Reuse the existing metadata helpers (_axxon_ts, _interval_summary, caps,
  QUERY_TYPES, VMDA_SCHEMA_ID) and the ensure_client/import_module idiom. Remove
  the now-unused MomentQuest string helper/template/language constant if nothing
  else references them; keep them only if still used elsewhere.
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`. Access points (hosts/Server/...) may stay. No proto/CA/PDF
  committed.
- TDD: add/adjust the failing tests first, then implement.

## Non-goals
- No Cleanup (destructive VMDA database wipe; stays pending).
- No new query types beyond motion_in_area (the only one in QUERY_TYPES).
- No new server flag, create_server param, or tool name change.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_metadata"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_metadata.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
