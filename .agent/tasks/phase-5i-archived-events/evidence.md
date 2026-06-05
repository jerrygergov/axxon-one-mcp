# Evidence: phase-5i-archived-events (archived-events gap closed)

## Summary
The archived-events read path was wrongly recorded as a stand-fixture gap ("no archived events"). Events
exist in abundance (300+ over 7 days, dominated by DetectorEvent). The real defects were two bugs in the
production `AxxonMcpLive.search_events`:

1. Any-body decode crash: `message_to_dict` (wrapping `MessageToDict`) raised
   `TypeError: Can not find message descriptor by type_url: ...mmexport.ExportEvent` whenever a page carried an
   `ExportEvent`-bodied event. `ExportEvent` ships in `axxonsoft.bl.mmexport.ExportEvent_pb2`, never imported;
   all other body types live in `Events_pb2`, already imported.
2. Wrong timestamp format: the `TimeRange` was built from numeric epoch-1900-millisecond strings, which
   silently returns 0 events. `EventHistoryService` expects the millisecond string format `YYYYMMDDThhmmss.mmm`.

## What changed
- `tools/axxon_mcp_live.py` `search_events`: import `axxonsoft.bl.mmexport.ExportEvent_pb2`; build `TimeRange`
  with the millisecond string format instead of numeric epoch-1900 ms.
- `tools/axxon_event_search.py` `setup`: import the same `ExportEvent_pb2` module.
- Tests: `test_search_events_registers_export_event_body_type` (server path, asserts import + string timestamp)
  and `test_setup_registers_export_event_body_type` (CLI path).

## Acceptance criteria
- AC1 PASS: `search_events` registers the `ExportEvent` body type; unit test green.
- AC2 PASS: `axxon_event_search.py setup` imports `ExportEvent_pb2`; unit test green.
- AC3 PASS: `python3.12 -m unittest discover -s tools/tests` -> Ran 671 tests, OK (was 669).
- AC4 PASS: live `search_events(hours=168, limit=300)` -> status ok, count 300, includes 3 `ExportEvent`
  items, no crash. Raw: `raw/live-verify.json`.
- AC5 PASS: `TimeRange` uses the `YYYYMMDDThhmmss.mmm` string format; numeric form live-confirmed to return 0
  while the string form returns >= 1000 over the same 168h window.

## Tests
```
python3.12 -m unittest discover -s tools/tests
Ran 671 tests, OK
```

## Files changed
- tools/axxon_mcp_live.py
- tools/axxon_event_search.py
- tools/tests/test_axxon_mcp_live.py
- tools/tests/test_event_search_and_examples.py
