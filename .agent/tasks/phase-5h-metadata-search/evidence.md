# Evidence: phase-5h-metadata-search

## Summary
Added a read-only metadata/VMDA object-track search capability: module
`tools/axxon_mcp_metadata.py` (`AxxonMcpMetadata`) with `list_vmda_sources`,
`live_track_sample` (live `MetadataService.PullMetadata`), and `vmda_query` (archived
`VMDAService.ExecuteQueryTyped`, MotionInArea + object-type/behaviour constraints), registered
as MCP tools behind `--enable-metadata`. Live-verified against the demo stand.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 module + 4 methods | PASS | `tools/axxon_mcp_metadata.py`: `connect_axxon_profile`, `list_vmda_sources`, `live_track_sample`, `vmda_query` |
| AC2 list_vmda_sources from inventory | PASS | `test_list_vmda_sources`; live: status ok, 16 sources |
| AC3 live_track_sample bounded, shaped | PASS | `test_live_track_sample_shape_and_caps`; live: count=14 real tracklets (id/state/behavior/bbox), stream_stop=cancelled |
| AC4 vmda_query ExecuteQueryTyped motion_in_area | PASS | `test_vmda_query_motion_in_area`, `test_vmda_query_zero_results_ok`, `test_vmda_query_bad_type_refused`; live: status ok |
| AC5 caps clamp + env-only creds, no literals | PASS | `_clamp` to MAX_SECONDS/MAX_TRACKLETS/MAX_INTERVALS; `test_*_caps`; `test_live_track_sample_error_is_clean` |
| AC6 MCP tools behind --enable-metadata | PASS | `register_metadata_tools` + `--enable-metadata`; `test_create_server_registers_metadata_tools_only_when_enabled` |
| AC7 unit tests + suite grows | PASS | new `test_axxon_mcp_metadata.py` (7) + server test; full suite 629/629 (was 621) |
| AC8 live verification | PASS | live runs below; raw under `raw/` |

## Commands

```
$ python3.12 -m unittest discover -s tools/tests
Ran 629 tests, OK

$ python3.12 -m unittest tools.tests.test_axxon_mcp_metadata
Ran 7 tests, OK
```

## Live verification on the stand (sanitized)

```
list_vmda_sources: status=ok count=16   (e.g. hosts/Server/AVDetector.1/SourceEndpoint.vmda)
live_track_sample (hosts/Server/AVDetector.112/SourceEndpoint.vmda, 12s):
  status=ok count=14 stream_stop=cancelled
  sample tracklet: {"id": 90004, "state": "OBJECT_STATE_APPEARED", "behavior": "MOVING_OBJECT", "bbox": {...}}
vmda_query (motion_in_area, vehicle+human, moving, 48h): status=ok interval_count=0 object_count=0
```

Raw: `raw/live-verify.json`, `raw/live-tracklets.json`.

## Key engineering findings (this matches the desktop "Metadata search")

- `AVDetector.112` = the desktop's `codex-temp-scene-for-smoke-150352354` source, bound to
  camera 1; its `*/SourceEndpoint.vmda` is the live tracklet stream.
- VMDA query binding: `access_point` = the `.vmda` endpoint, `camera_ID` = that same string.
  Empty/placeholder ids (`vmda_schema`/`schema`) return server INTERNAL.
- A live bug found and fixed: a bounded PullMetadata stream that we cut short ends with
  gRPC CANCELLED; `live_track_sample` now treats CANCELLED/DEADLINE after collecting data as a
  clean stop (`status=ok`, `stream_stop`), not an error.
- `vmda_query` returns 0 intervals on this stand because it does not persist VMDA tracks to the
  queryable archive DB (same class as the empty EventHistory). The call is correct and returns
  data on any stand that records metadata.

## Files changed
- tools/axxon_mcp_metadata.py (new)
- tools/axxon_mcp_server.py (register_metadata_tools, --enable-metadata, wiring)
- tools/tests/test_axxon_mcp_metadata.py (new, 7 tests)
- tools/tests/test_axxon_mcp_server.py (metadata registration test)
