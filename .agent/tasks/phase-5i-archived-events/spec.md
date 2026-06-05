# Spec: phase-5i-archived-events (close the archived-events gap)

## Problem
The archived-events read path was reported as a "stand-fixture-blocked gap" with the claim
"no archived events on the stand". That conclusion was false. It came from `EventHistoryService.ReadCount`
returning 0, the same wrong-binding mistake that affected VMDA. `ReadEvents` actually returns thousands of
events over a multi-day window.

The real defect: `AxxonApiClient.message_to_dict` (which wraps `google.protobuf.json_format.MessageToDict`)
crashes when a `ReadEventsResponse` item carries an `Any` `body` whose message type is not registered in the
descriptor pool. On this stand the offending type is `axxonsoft.bl.mmexport.ExportEvent`, defined in
`axxonsoft/bl/mmexport/ExportEvent.proto` (module `ExportEvent_pb2`), which neither the production
`AxxonMcpLive.search_events` nor the `axxon_event_search.py` CLI imports. Every other observed body type
(DetectorEvent, MacroEvent, AuditEvent, Alert, AlertState, etc.) lives in `Events_pb2`, already imported.

Live-reproduced crash:
`TypeError: Can not find message descriptor by type_url: type.googleapis.com/axxonsoft.bl.mmexport.ExportEvent`

A second defect surfaced during live verification: `search_events` built the `TimeRange` with numeric
epoch-1900-millisecond strings, which silently returns 0 events. `EventHistoryService` expects the millisecond
string format `YYYYMMDDThhmmss.mmm`.

## Acceptance criteria
- AC1: `AxxonMcpLive.search_events` registers the `ExportEvent` body module so `message_to_dict` decodes
  event pages containing `ExportEvent` Any bodies without raising. Unit-tested.
- AC2: `axxon_event_search.py` (`AxxonEventSearch.setup`) imports the same `ExportEvent_pb2` module. Unit-tested.
- AC3: Full suite green: `python3.12 -m unittest discover -s tools/tests` (>= 671 tests, no failures).
- AC4: Live verification: corrected `search_events` returns real archived events over a multi-day window with
  no crash, including at least one `ExportEvent`-named item; sanitized raw evidence under `raw/`.
- AC5: `search_events` builds the `TimeRange` with the millisecond string format `YYYYMMDDThhmmss.mmm`, not the
  numeric epoch-1900-millisecond format. Unit-tested.

## Constraints
- Smallest defensible diff. Do not rewrite `message_to_dict`; only register the missing body type and fix the
  timestamp on the event read path.
- TDD: failing test first.
- Never commit proto files, CA, or the PDF. Remove the `docs/grpc-proto-files` symlink before any commit.
- Sanitize all committed evidence; intrinsic `hosts/Server/...` UIDs may stay.
- Retry transient `urlopen`/`DEADLINE_EXCEEDED` up to 3x during live verification.
