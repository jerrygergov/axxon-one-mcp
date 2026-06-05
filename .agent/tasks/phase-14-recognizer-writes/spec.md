# Spec: phase-14-recognizer-writes

## Original task statement
Extend the Axxon One MCP server with write/mutation tools for
`RealtimeRecognizerService`, covering the watchlist mutation RPCs that are
currently `pending` in the corpus: `ChangeLists`, `ChangeItems`, and `Clear`.
Mutations are authorized on the test stand. The tools must be approval-gated and
confirmation-tokened, consistent with the existing audit-injector mutation tool.

This complements the read-only recognizer tools shipped in phase 11
(`GetLists`/`GetListStream`/`GetItems`).

## Background (live-verified before freeze)
- Stand has one node `Server` and one list "Intersec Face List" (ELT_Face, 6 faces).
- `ChangeLists` (unary): add/change/remove lists. Live-proven reversible
  (add temp LPR list -> present -> rename -> remove -> gone, zero failures).
- `ChangeItems` (bidi stream): add/change/remove items. Live-proven: an LPR plate
  item added via `ChangeItems` is then visible via `GetItems`. The server returns
  an empty response stream on success and assigns its own item id (the client
  proposed id is not echoed back), so success is confirmed by content readback,
  not by id match.
- `Clear` (unary): wipes ALL lists/items on a node; only scopes by `node_name`,
  no list-level scope. On this single-node stand, Clear destroys the real
  "Intersec Face List" irreversibly. The user explicitly authorized live-firing
  Clear and accepts deletion of those 6 enrolled faces.

## Acceptance criteria

### AC1 — module + dataclass + gating
`tools/axxon_mcp_recognizer_write.py` adds `AxxonMcpRecognizerWrite` (dataclass),
mirroring `AxxonMcpAudit`: `client_factory`/`config_factory`/`client`/`enabled`
fields; `recognizer_write_connect_axxon_profile`, `ensure_client`. Writes are
gated by `AXXON_RECOGNIZER_WRITE_APPROVE=1` plus a per-call confirmation token
`CONFIRM-recognizer-write`. When approval env is unset, every mutating tool
returns `{"status": "disabled", ...}` without touching the stand. When the
confirmation token is wrong, returns `{"status": "gap", ...}`.

### AC2 — recognizer_change_lists
A tool `recognizer_change_lists(added, changed, removed_ids, confirmation)` calls
`ChangeLists`. `added`/`changed` are lists of dicts (id optional for added,
name/description/score/type/item_ids honored); `removed_ids` a list of guids.
Returns `{"status": "applied", "failed_lists": [...]}` on success, surfacing the
server's `failed_lists`. Unknown/empty payload returns a clear error, not a crash.

### AC3 — recognizer_change_items
A tool `recognizer_change_items(list_id, added, removed_item_ids, confirmation)`
calls the bidi `ChangeItems`. Supports adding LPR items (`data_string`) and
removing items by id. It sends `EPS_LAST` on the final packet and drains the
response stream (which may be empty on success). Returns
`{"status": "applied", "failed_items": [...]}`. Biometric image/vector payloads
are out of scope (LPR string items only); the tool never accepts or emits raw
image bytes or vectors.

### AC4 — recognizer_clear (destructive, double-gated)
A tool `recognizer_clear(node_name, confirmation)` calls `Clear`. Because it is
irreversible and node-wide, it requires BOTH the standard confirmation token AND
a second explicit acknowledgement token `CONFIRM-clear-node-wipe`. Returns
`{"status": "cleared", "node_name": ...}` on success. Docstring and return
payload state plainly that this deletes all lists and items on the node.

### AC5 — server registration behind a flag
`register_recognizer_write_tools` registers the three mutating tools plus
`recognizer_write_connect_axxon_profile`, wired through `create_server` via a
`recognizer_write` param and a `--enable-recognizer-write` CLI flag (off by
default). Follows the existing 6-edit registration pattern in
`tools/axxon_mcp_server.py`.

### AC6 — unit tests + full suite green
`tools/tests/test_axxon_mcp_recognizer_write.py` covers, with a fake client (no
network): disabled-without-approval, gap-on-bad-token, change_lists payload
shaping + failed_lists passthrough, change_items add/remove packet generation +
EPS_LAST + empty-stream drain, clear double-gate (rejects without the second
token), and that no image/vector bytes appear in any request the tool builds.
Full suite `python3.12 -m unittest discover -s tools/tests` stays green.

### AC7 — corpus restamp, live-justified
After a live run against the stand (recorded under `raw/live-verify.txt`,
sanitized), restamp via `tools/axxon_corpus_restamp.py`:
`ChangeLists`, `ChangeItems`, `Clear` `pending -> tested-pass` with per-method
evidence citations. `ChangeListsStream` stays pending (not exercised). Update the
coverage doc counts.

## Constraints
- No biometric data (face images/vectors) committed or required by the tools.
- All non-Clear mutations exercised live must be reversible and rolled back,
  except the one authorized destructive Clear.
- Secrets stay env-only; sanitize all committed evidence (host/user/creds).
- Mirror the audit-injector gating idiom; do not invent a new safety pattern.
- Smallest defensible diff; reuse `public_config_summary`, `message_to_dict`,
  `stub_from_proto`, `import_module`.

## Non-goals
- Face/food image item ingestion (DT_ImageFace/DT_ImagesFood with raw bytes).
- `ChangeListsStream` (bidi list mutation) — `ChangeLists` covers the same intent.
- Vector ingestion (DT_Vector).
- Any read-tool changes (phase 11 already covers reads).

## Verification plan
- Unit: the fake-client suite above; full discover run.
- Live: temp LPR list add/change/remove (reversible) for ChangeLists; temp LPR
  list+item add/readback/remove for ChangeItems; then the authorized Clear with a
  pre-Clear metadata snapshot and post-Clear empty verification.
