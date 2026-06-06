# Spec: phase-26-domain-batch-reads

## Original task statement
Close the three pending DomainService read methods — `GetCamerasByComponents`,
`BatchGetArchives`, `SearchMaps` — so DomainService reaches 21/21 tested-pass.
All three are read-only batch lookups taking `repeated ResourceLocator{access_point,
view}` and returning entities plus not_found / unreachable lists. Add three client
helpers plus three read-only MCP tools to the existing `tools/axxon_mcp_view.py`
view module, live-verify them, and restamp the corpus.

Context: AcfaService PerformAction/DownloadData were probed first and rejected as
this phase's target — the stand has only ACFA unit *type* definitions (no
configured units), and PerformAction is a non-reversible physical access-control
side effect. DomainService reads are the clean, reversible-by-nature alternative.

## Acceptance criteria
- **AC1**: `tools/axxon_api_client.py` gains three direct-gRPC helpers that each
  build `repeated ResourceLocator(access_point=...)`, drain the server stream, and
  return `{items, not_found_objects, unreachable_objects}` (SearchMaps returns
  `maps` instead of `items`):
  `get_cameras_by_components(access_points)`,
  `batch_get_archives_domain(access_points)`,
  `search_maps(access_points)`. They reuse the DomainService stub idiom.
- **AC2**: `tools/axxon_mcp_view.py` gains three read-only tools that connect,
  call the helper, and return a summarized result (`status`, `tool`, `count`,
  `not_found`, `unreachable`, and a compact item list of access points / ids —
  URL/metadata only, never media bytes, consistent with the module contract). An
  empty access-points input returns `{"status":"gap"}` with no wire call.
- **AC3**: The three tools (`get_cameras_by_components`, `batch_get_archives`,
  `search_maps`) are registered in `tools/axxon_mcp_server.py` inside the existing
  `register_view_tools` (no new flag/param; the view module is already wired).
- **AC4**: Unit tests in `tools/tests/test_axxon_mcp_view.py` (or the view test
  module) cover, with fake stub/client: each tool summarizes items + not_found +
  unreachable from a fake stream; the empty-input gap path (no wire call); and the
  ResourceLocator request shape (access points passed through). Full suite stays
  green.
- **AC5**: `tools/axxon_corpus_restamp.py` restamps all three to `tested-pass`;
  `docs/api-audit/mcp-corpus/api_methods.json` reflects it (DomainService 21/21).
  Coverage doc count moves to 205 pass-class / 118 pending / 38 fixture-warn and
  notes the DomainService batch reads. Restamp dry-run reports 0 after `--write`.

## Constraints
- Probe-first already done: all three live round-tripped read-only through direct
  gRPC against the stand using real camera/archive access points from ListCameras/
  ListArchives. GetCamerasByComponents -> 1 camera; BatchGetArchives -> 1 archive;
  SearchMaps -> 1 map locator. See raw/live-verify.txt.
- Wire shape: each request is `{repeated ResourceLocator items}` where
  ResourceLocator is `{string access_point; View view}`. All three are
  server-streaming; responses carry items (or `maps` for SearchMaps) plus
  `not_found_objects` and `unreachable_objects`.
- Read-only: no mutation, no rollback, no approval gate. The view module never
  proxies media bytes; these tools return access points / ids and counts only.
- Reuse the DomainService stub idiom and the view module's connect/inventory
  pattern. Do not duplicate stream-drain logic across the three helpers (share a
  private drain).
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`, access points may stay (hosts/Server/...). No proto/CA/PDF
  committed.
- TDD: add the failing tests first, then implement.

## Non-goals
- No camera/archive/map mutation; read-only batch lookups only.
- No media-byte proxying (URLs / ids / metadata only).
- No new server flag or create_server param.
- AcfaService PerformAction/DownloadData stay pending (fixture-walled /
  non-reversible physical action; out of scope here).

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_view; import axxon_api_client"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_view.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
