# Evidence Bundle: phase-11-recognizer-lists

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + direct gRPC — PASS
- `tools/axxon_mcp_recognizer.py` adds `AxxonMcpRecognizer` with
  `recognizer_connect_axxon_profile`, `list_recognizer_lists`, `get_recognizer_list`,
  `list_recognizer_items`. Direct gRPC via
  `stub_from_proto(RECOGNIZER_PROTO, "RealtimeRecognizerService")`.

## AC2 — list_recognizer_lists + enum mapping — PASS
- Returns id/name/type/score/item_count; list_type maps to EListType
  (any/face/lpr/food).
- Proof: `test_list_lists_returns_summary_with_item_count`, `test_list_type_maps_to_enum`.

## AC3 — get_recognizer_list (streaming) — PASS
- Aggregates `GetListStream` pages into a list descriptor.
- Proof: `test_get_list_streams_descriptor`; live `get_recognizer_list` returned the
  real list id.

## AC4 — list_recognizer_items, metadata only — PASS
- Calls `GetItems` with empty required_items + load_images/vectors False; returns
  id + name/full_name (face) or value (LPR). No image/vector keys.
- Proof: `test_list_items_metadata_only_no_biometrics`; live run shows
  `contains biometric payload: False`.

## AC5 — unit tests + full suite green — PASS
- 5 tests in `tools/tests/test_axxon_mcp_recognizer.py`.
- Full suite `Ran 701 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp, live-justified — PASS
- Live (raw/live-verify.txt): GetLists -> 1 face list (6 items); GetListStream ->
  descriptor; GetItems -> 6 metadata items. Person names redacted in evidence.
- GetLists/GetListStream/GetItems restamped `tested-warn-fixture-needed -> tested-pass`.
  Mutations (ChangeLists/ChangeItems/Clear) stay pending.

## AC7 — server registration behind --enable-recognizer — PASS
- `register_recognizer_tools` registers the 4 tools; wired via `--enable-recognizer`
  (read-only, off by default); `recognizer` param threaded through `create_server`.
- Proof: register sanity check lists all 4 tool names.

## Sanitization
- raw/live-verify.txt: enrolled-person names/values replaced with `<redacted-name>` /
  `<redacted-value>`; only list/item GUIDs and the list name remain. No host IP / creds.
