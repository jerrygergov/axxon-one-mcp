# Evidence Bundle: phase-22-recognizer-stream

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — gated streaming method, reuses helpers — PASS
- `recognizer_change_lists_stream` added to `tools/axxon_mcp_recognizer_write.py`,
  reusing the existing `_gate`, `_build_list`, `_stub_and_pb2`. Gated the same as
  `recognizer_change_lists` (`disabled` env-unset / `gap` bad token, no wire call);
  returns `error` (no wire call) when no edit field is given.
- Proof: `ChangeListsStreamTests` (disabled/gap/no-edit); live `[gating]` block.

## AC2 — _list_packets streaming + EPS_LAST — PASS
- `_list_packets` yields one ChangeListsStreamRequest per added/changed list plus a
  `removed_lists=ListIds(ids=[...])` packet, setting `status=EPS_LAST` only on the
  last packet. The method streams them through `stub.ChangeListsStream`, drains the
  response stream, returns `{"status":"applied","failed_lists":[...]}`.
- Proof: `ChangeListsStreamTests.test_packet_sequence_and_last_status` (3-packet
  sequence, EPS_LAST only on last, oneof fields), `test_failed_lists_passthrough`;
  live stream add LPR list -> stream remove (0 -> 1 -> 0).

## AC3 — server registration — PASS
- `recognizer_change_lists_stream` registered inside the existing
  `register_recognizer_write_tools` (no new flag/param; module already wired behind
  `--enable-recognizer-write`). Name added to `RECOGNIZER_WRITE_TOOL_NAMES`.
- Proof: raw/test-unit.txt (server import OK).

## AC4 — unit + full suite green — PASS
- 5 new tests (18 in the recognizer-write suite). Full suite `Ran 786 tests ... OK`
  (raw/test-unit.txt).

## AC5 — corpus restamp + coverage doc — PASS
- ChangeListsStream -> tested-pass. Coverage 198 pass-class / 125 pending /
  38 fixture-warn. All 7 non-fixture RealtimeRecognizerService methods now pass
  (only GetData stays fixture-warn). Restamp dry-run reports 0 after --write.

## Stand hygiene
- A throwaway LPR list was added via the stream then removed via the stream. LPR
  string lists only; no biometric image bytes/vectors built or emitted. Stand ends
  at its original 0 lists. No proto/CA/PDF committed; secrets env-only; no
  biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`, list GUID
  -> `<uuid>`.
