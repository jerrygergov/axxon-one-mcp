# Task Spec: phase-38-bookmark-extras

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (BookmarkService rows)
- tools/axxon_mcp_archive_volume.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close the three remaining BookmarkService methods
(UpdateBookmark, SetExportedTime, RenderTrack) via a new gated module mirroring the
archive_volume idiom. Live-verify reversibly. This brings BookmarkService to 7/7.

## Live probe findings (2026-06-07, demo stand)
Reversible round-trip on camera hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0:
CreateBookmark (existing pass) -> UpdateBookmark (message changed) -> SetExportedTime
(exported_time set, confirmed via GetBookmark HasField) -> RenderTrack (returns a bookmark)
-> DeleteBookmark (existing pass; GetBookmark afterward errors = gone). All three target
methods SERVICEABLE. The probe bookmark was fully cleaned up.

## Message shapes (confirmed live)
- Bookmark{message, boundary, range(TimeRangeTS{begin_time, end_time as Timestamp}),
  protection, access, camera_descriptions{descriptions[CameraDescription{camera_access_point}]},
  categories, id(out), user_id(out), timestamp(out), exported_time, creation_time(out)}.
- UpdateBookmarkRequest{bookmark}; UpdateBookmarkResponse{bookmark}.
- SetExportedTimeRequest{id, exported_time(Timestamp)}; SetExportedTimeResponse{}.
- RenderTrackRequest{bookmark}; RenderTrackResponse{bookmark}.
- GetBookmarkRequest{id, mode}; DeleteBookmarkRequest{id}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_bookmark_extras.py exposes update_bookmark (gated write),
  set_bookmark_exported_time (gated write), render_bookmark_track (read), with connect helper
  + ensure_client + _stub_and_pb2 + _write_gate matching archive_volume. Approval env
  AXXON_BOOKMARK_EXTRAS_APPROVE=1, confirmation token CONFIRM-bookmark-extras.
- AC2: update_bookmark and set_bookmark_exported_time enforce the gate before any wire call:
  env-off -> {"status":"disabled"}; bad token -> {"status":"gap"}; missing id -> {"status":"error"}.
  Unit tests assert client.calls==[] in each case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_bookmark_extras_tools with @server.tool entries, --enable-bookmark-extras flag,
  flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: full reversible Create->Update->SetExportedTime->RenderTrack->Delete
  round-trip; the probe bookmark is created and then deleted, GetBookmark afterward confirms
  it is gone. Raw transcript raw/live-verify.txt with host/creds sanitized.
- AC5: Corpus restamp marks UpdateBookmark, SetExportedTime, RenderTrack tested-pass.
  Dry-run after --write reports 0 restamped. Coverage doc updated; BookmarkService 7/7.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- The verification creates a throwaway bookmark and deletes it; no residual bookmark.
- update_bookmark requires the caller to pass the bookmark id (operates on an existing
  bookmark only); the tool does not create bookmarks.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>.
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- Re-implementing CreateBookmark/DeleteBookmark (already covered; used only to set up and
  tear down the verification fixture).
- Bookmark boundary/track geometry editing beyond passing through RenderTrack.

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_bookmark_extras.py (read, gate, no-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript + restamp dry-run clean.
