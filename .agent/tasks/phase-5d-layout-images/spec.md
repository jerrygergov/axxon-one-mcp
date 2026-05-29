# Task Spec: phase-5d-layout-images

## Metadata
- Task ID: phase-5d-layout-images
- Created: 2026-05-29T13:40:44+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- None detected at init time.

## Original task statement
Close the Phase 5D list_layout_images gap. Root cause: list_layout_images in tools/axxon_mcp_view_objects.py calls client.list_layout_images which uses the HTTP /grpc bridge, but axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages returns HTTP 500 over /grpc on the stand. The method works correctly over direct gRPC and returns an empty images list for the 20 existing layouts. Fix: route list_layout_images over direct gRPC (LayoutImagesManager stub) with graceful handling, keep HTTP behavior as a documented fallback. Verify live against the stand that the tool returns status ok (not gap) for an existing layout. Optionally upload+list+remove a test image as a reversible round-trip to prove non-empty listing. Update unit tests and refresh phase-5d evidence.

## Acceptance criteria
- AC1: `list_layout_images(layout_id)` returns `status: ok` (not `gap`) for an existing layout on the live stand, with an `items` list and `count`. The HTTP `/grpc` bridge returns HTTP 500 for `LayoutImagesManager.ListLayoutImages`, so the tool routes the call over direct gRPC.
- AC2: A reversible live round-trip proves non-empty listing: upload a tiny test image to a writable layout over `UploadLayoutImage`, confirm `list_layout_images` then reports the image id, remove it via `RemoveLayoutImages`, and confirm the list is empty again (full rollback, no residue on the stand).
- AC3: Unit tests cover the new direct-gRPC path: ok result mapped from a stubbed gRPC response, and the HTTP-fallback gap path is preserved when direct gRPC is unavailable. All existing `tools/tests` stay green (>=500 tests).
- AC4: Phase 5D evidence (`docs/api-audit/phase-5d-view-objects-smoke-latest.md`) and the coverage corpus are refreshed and sanitized; the 5D smoke no longer reports a `gap` for `list_layout_images`.

## Constraints
- Direct-gRPC live runs need the local CA + proto files symlinked into the worktree; the symlink and proto/CA files must never be committed.
- Mutations (image upload) are reversible and must roll back fully; use `codex-*` image ids.
- No defensive try/except beyond what the rollback/transport-fallback guarantee requires.
- Sanitize all committed evidence (host, user, CA, tokens).

## Non-goals
- `DownloadLayoutImage` streaming retrieval (binary chunk download) is out of scope.
- Promoting layout-image upload to a first-class operator workflow (only the read tool is in 5D scope; the round-trip is verification-only).

## Verification plan
- Build: route `list_layout_images` over direct gRPC in `tools/axxon_api_client.py` + `tools/axxon_mcp_view_objects.py`.
- Unit tests: `python3.12 -m unittest discover -s tools/tests`.
- Integration tests: `python3.12 tools/axxon_view_objects_smoke.py` against the stand (CN=Server), plus a scripted upload/list/remove round-trip.
- Lint: n/a (no linter configured beyond tests).
- Manual checks: confirm `list_layout_images` returns `ok` for layout `a7cf0082-...` and the round-trip rolls back.
