# Spec: phase-22-recognizer-stream

## Original task statement
Close the last pending RealtimeRecognizerService mutation, `ChangeListsStream`,
so the service reaches 7/7 tested-pass. `ChangeLists` (the deprecated unary form)
is already shipped and tested-pass; `ChangeListsStream` is the bidirectional
streaming replacement the proto recommends. Add it to the existing
`tools/axxon_mcp_recognizer_write.py` module (already gated and registered),
live-verify reversibly, and restamp the corpus. Reversible: add a throwaway LPR
list via the stream then remove it via the stream.

## Acceptance criteria
- **AC1**: `tools/axxon_mcp_recognizer_write.py` gains
  `recognizer_change_lists_stream(added=None, changed=None, removed_ids=None,
  confirmation="")`, reusing the existing `_gate`, `_build_list`, and
  `_stub_and_pb2`. It is gated the same way as `recognizer_change_lists`
  (`disabled` when `AXXON_RECOGNIZER_WRITE_APPROVE` != "1", `gap` on wrong token)
  with no wire call before the gate passes, and returns `{"status":"error"}` (no
  wire call) when none of added/changed/removed_ids is given.
- **AC2**: A private `_list_packets(pb2, added, changed, removed_ids)` generator
  yields `ChangeListsStreamRequest` packets — one per added_list / changed_list,
  plus one `removed_lists=ListIds(ids=[...])` packet when removed_ids is given —
  and sets `status=EPS_LAST` on the final packet only. The method streams the
  packets through `stub.ChangeListsStream`, drains the response stream, and
  returns `{"status":"applied","failed_lists":[...]}`.
- **AC3**: The new tool `recognizer_change_lists_stream` is registered inside the
  existing `register_recognizer_write_tools` in `tools/axxon_mcp_server.py`
  (no new flag/param needed; the module is already wired behind
  `--enable-recognizer-write`). `RECOGNIZER_WRITE_TOOL_NAMES` includes the new
  name.
- **AC4**: Unit tests in `tools/tests/test_axxon_mcp_recognizer_write.py` (or the
  existing recognizer-write test module) cover: gating (disabled/gap, no wire
  call), no-edit error (no wire call), and packet shape — add+change+remove
  yields the right packet sequence with EPS_LAST only on the last and the oneof
  fields set correctly. Full suite stays green.
- **AC5**: `tools/axxon_corpus_restamp.py` restamps `ChangeListsStream` to
  `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json` reflects it
  (RealtimeRecognizerService 6/7 -> ChangeListsStream tested-pass; GetData stays
  fixture-warn so the service is 7 pass / 1 warn of 8 listed, i.e. all 7 non-fixture
  methods pass). Coverage doc count moves to 198 pass-class / 125 pending /
  38 fixture-warn and notes the recognizer stream. Restamp dry-run reports 0 after
  `--write`.

## Constraints
- Probe-first already done: ChangeListsStream live round-tripped reversibly through
  direct gRPC (add throwaway LPR list via stream -> remove via stream). Stand ends
  at its original 0 lists. See raw/live-verify.txt.
- Wire shape: `ChangeListsStreamRequest(status=EPS_LAST, added_list=List)` /
  `changed_list=List` / `removed_lists=ChangeListsStreamRequest.ListIds(ids=[...]))`;
  bidirectional stream; response packets carry `failed_lists`.
- Reuse the existing module helpers; do NOT duplicate `_build_list` or `_gate`.
  Mirror the existing `_item_packets` / `recognizer_change_items` streaming idiom.
- Biometric ingestion stays out of scope (LPR lists only; no image bytes/vectors).
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`, list GUID -> `<uuid>`. No proto/CA/PDF committed.
- TDD: add the failing tests first, then implement.

## Non-goals
- No change to the deprecated unary `recognizer_change_lists` (kept as-is).
- No biometric item ingestion; no GetData fixture work.
- No new server flag or create_server param (module already registered).

## Gating idiom
- Existing env `AXXON_RECOGNIZER_WRITE_APPROVE=1`, token `CONFIRM-recognizer-write`.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_recognizer_write"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_recognizer_write.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
