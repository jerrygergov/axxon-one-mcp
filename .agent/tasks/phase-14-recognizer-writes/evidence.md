# Evidence Bundle: phase-14-recognizer-writes

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + gating — PASS
- `tools/axxon_mcp_recognizer_write.py` adds `AxxonMcpRecognizerWrite` (dataclass),
  mirroring `AxxonMcpAudit`. Gated by `AXXON_RECOGNIZER_WRITE_APPROVE=1` +
  `WRITE_CONFIRMATION="CONFIRM-recognizer-write"`. `_gate` returns `disabled` when
  approval env unset, `gap` on bad token, before any wire call.
- Proof: `GatingTests` (disabled-without-approval, gap-on-bad-token); live
  [GATE] line in raw/live-verify.txt.

## AC2 — recognizer_change_lists — PASS
- Builds `ChangeListsRequest` from added/changed dicts + removed_ids; surfaces
  `failed_lists`. Empty payload -> error, no wire call.
- Proof: `ChangeListsTests` (payload shaping, failed_lists passthrough, empty
  errors); live add/rename/remove round-trip (raw/live-verify.txt).

## AC3 — recognizer_change_items — PASS
- Bidi `ChangeItems`: LPR `data_string` items only; sends `EPS_LAST` on the last
  packet; drains the (possibly empty) response stream. No image/vector bytes
  built or emitted.
- Proof: `ChangeItemsTests` (EPS_LAST on last packet, no data_images field,
  empty errors); live LPR plate add confirmed by readback (raw/live-verify.txt).

## AC4 — recognizer_clear (destructive, double-gated) — PASS
- Requires both `WRITE_CONFIRMATION` and `CLEAR_ACK="CONFIRM-clear-node-wipe"`.
  Docstring + return payload state the node-wide irreversible deletion.
- Proof: `ClearTests` (rejects without each token, fires with both); live
  authorized wipe of node Server: pre=1 list/6 faces, post=[] (raw/live-verify.txt).

## AC5 — server registration behind a flag — PASS
- `register_recognizer_write_tools` registers the 3 mutating tools +
  `recognizer_write_connect_axxon_profile`; wired via `--enable-recognizer-write`
  (off by default) and `recognizer_write` param through `create_server`
  (6-edit pattern). Server module imports clean.
- Proof: `python3.12 -c "import axxon_mcp_server"` OK (raw/test-unit.txt).

## AC6 — unit tests + full suite green — PASS
- 13 tests in `tools/tests/test_axxon_mcp_recognizer_write.py`.
- Also fixed a latent phase-11 bug: `list_recognizer_items(list_ids=...)` passed a
  non-existent `list_ids` field to `GetItemsRequest` (crashes on real server). The
  fake pb2 in the phase-11 test masked it. Removed the unsupported param across
  module + server tool + added a regression assertion. `GetItems` is node-wide;
  the proto has no list-scoped item filter.
- Full suite: `Ran 718 tests ... OK` (raw/test-unit.txt).

## AC7 — corpus restamp, live-justified — PASS
- `ChangeLists`, `ChangeItems`, `Clear` restamped `pending -> tested-pass` with
  per-method evidence citations via `tools/axxon_corpus_restamp.py --write`.
  `ChangeListsStream` stays pending. Coverage 181 pass / 145 pending / 35 warn.
- Coverage doc updated (RealtimeRecognizer 6/7).

## Sanitization
- raw/live-verify.txt: host/creds redacted; only list/item metadata (name, type,
  count, guids) recorded. No biometric images or vectors read, emitted, or
  committed. The face-list guid is an object id, not a secret.
