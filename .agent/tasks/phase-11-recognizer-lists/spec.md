# Task Spec: phase-11-recognizer-lists

## Metadata
- Task ID: phase-11-recognizer-lists
- Created: 2026-06-05
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- docs/api-audit/capability-vs-coverage-2026-06-05.md (RealtimeRecognizerService 0 pass)
- Pattern: tools/axxon_mcp_bookmarks.py (read-only dataclass module + server reg).
- Live probe (this session): the stand has a real "Intersec Face List" (ELT_Face,
  6 enrolled faces, names redacted). GetLists/GetListStream/GetItems all return data.

## Original task statement
Expose RealtimeRecognizerService as READ-ONLY MCP tools so integrations can inspect
face/LPR recognition watchlists (which lists exist, which people/plates are enrolled).
Privacy-first: never load face images or biometric vectors by default — GetItems with
empty required_items returns metadata only.

Mutations (ChangeLists, ChangeListsStream, ChangeItems, Clear) are OUT OF SCOPE
(bidi-streaming, would edit a real watchlist on a shared stand).

## Acceptance criteria
- AC1: New module `tools/axxon_mcp_recognizer.py` with an `AxxonMcpRecognizer`
  dataclass exposing `recognizer_connect_axxon_profile`, `list_recognizer_lists`,
  `get_recognizer_list`, `list_recognizer_items`. Direct gRPC via
  `RealtimeRecognizerService` (`axxonsoft/bl/realtimeRecognizer/RealtimeRecognizer.proto`).
- AC2: `list_recognizer_lists(list_type="any")` calls `GetLists`, returns each list's
  id, name, type, score, and item count (len of item_ids). list_type maps to the
  EListType enum (any/face/lpr/food).
- AC3: `get_recognizer_list(list_id)` calls the server-streaming `GetListStream` and
  returns the aggregated list descriptor.
- AC4: `list_recognizer_items(list_ids=None, limit=200)` calls the server-streaming
  `GetItems` with EMPTY required_items (so NO images/vectors are loaded), aggregates
  pages up to `limit`, and returns per-item id + type + a safe metadata summary
  (name / full_name / data_string for LPR). Never returns image bytes or vectors.
- AC5: Unit tests under `tools/tests/` cover the three reads against a fake streaming
  client, the list_type enum mapping, the item-summary shape (no image/vector keys),
  and the limit cap. Full suite stays green.
- AC6: `GetLists`, `GetListStream`, `GetItems` restamped to `tested-pass` in the corpus
  via `tools/axxon_corpus_restamp.py` with a cited live-evidence string (they are
  currently `tested-warn-fixture-needed`; the fixture now exists). Mutations stay pending.
- AC7: Registered in `tools/axxon_mcp_server.py` behind `--enable-recognizer`
  (read-only, off by default), consistent with the other module wiring.

## Constraints
- Reuse `AxxonApiClient` direct gRPC (`stub_from_proto` + `import_module`); no new client.
- Read-only: no mutation RPCs. Bounded: cap aggregated items at `limit`.
- PRIVACY: default path loads no images/vectors. Do not surface biometric payloads.
- Env-only secrets; sanitize evidence; `hosts/Server/...` and list/item GUIDs may stay
  (they are not credential material), but redact enrolled-person names in committed
  evidence (replace with `<redacted-name>`) since they are personal data.
- Google-style docstrings, no banned words, no defensive programming beyond validation.

## Non-goals
- ChangeLists / ChangeItems / Clear (watchlist mutation).
- Loading face images or vectors (privacy; large payloads).
- Realtime recognition event streams (separate from list management).

## Verification plan
- Build: new tools/axxon_mcp_recognizer.py + tests + server registration + restamp.
- Unit: `python3.12 -m unittest discover -s tools/tests` green incl. new tests.
- Integration: live read of the stand's face list (GetLists -> GetListStream ->
  GetItems), record counts/shape in raw/ with person names redacted. AXXON_TIMEOUT=30,
  retry 3x on transient DEADLINE_EXCEEDED.
- Lint: n/a.
- Manual: confirm item summaries contain NO image/vector keys.
