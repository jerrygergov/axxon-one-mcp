# Evidence: phase-5h-vmda-fix (archived VMDA query gap closed)

## Summary
Corrected `vmda_query` in `tools/axxon_mcp_metadata.py` to the documented MomentQuest binding and
live-verified real archived object data on the demo stand. This closes the previously
"environment-limited" archived-VMDA gap.

## Root cause
Phase 5H used `VMDAService.ExecuteQueryTyped` with `camera_ID == access_point == .vmda endpoint`.
That call returned `ok` but always 0 intervals (and INTERNAL for some bindings). The Integration
APIs 3.0 guide (pages 295, 447, "gRPC API MomentQuest smart search (VMDA)") documents the real
binding:

| Field | Was (wrong) | Now (correct) |
|---|---|---|
| RPC | `ExecuteQueryTyped` | `ExecuteQuery` (string MomentQuest query) |
| `access_point` | the `.vmda` source | `hosts/Server/VMDA_DB.0/Database` (the VMDA database) |
| `camera_ID` | `vmda_schema` / the endpoint | `AVDetector.1/SourceEndpoint.vmda` (host-relative source) |
| `schema_ID` | `schema` | `vmda_schema` |
| `query` | typed MotionInArea proto | `figure fZone=polygon(...); ... result = r.res;` + `language="EVENT_BASIC"` |
| timestamps | microseconds | milliseconds (`YYYYMMDDThhmmss.mmm`) |

## What changed
- `vmda_query` now takes `camera_id` + optional `database` (auto-discovered as `*/VMDA_DB.N/Database`),
  builds the MomentQuest motion-in-area program, strips the host prefix for `camera_ID`, emits
  millisecond timestamps, and streams `ExecuteQuery`. Returns intervals with time range + object
  bounding boxes. Added a `timeout` param (default 60s, cap 120s) for large windows.
- Server tool `vmda_query` updated to the new signature.
- Tests rewritten to the `ExecuteQuery` binding; added binding-matches-PDF and missing-database-gap
  cases.

## Live verification (sanitized)
- 14-day per-day sweep across both DBs x both camera-1 trackers found data:
  `VMDA_DB.0 / AVDetector.1, day-5 -> 3931 intervals`.
- Rewritten module `vmda_query` over a 30-min slice of that day:
  `status=ok database=hosts/Server/VMDA_DB.0/Database interval_count=5 object_count=5`, each
  interval carrying object bounding boxes (e.g. id "14" left 0.0575 right 0.1912 bottom 0.1028).
- Raw: `raw/live-verify.json`.

## Tests
```
python3.12 -m unittest discover -s tools/tests
Ran 669 tests, OK   (was 668)
```

## Files changed
- tools/axxon_mcp_metadata.py (vmda_query rewrite + helpers + constants)
- tools/axxon_mcp_server.py (vmda_query tool signature)
- tools/tests/test_axxon_mcp_metadata.py (binding tests)
- tools/tests/test_axxon_mcp_server.py (stub signature)
