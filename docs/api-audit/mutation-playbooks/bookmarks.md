# Mutation Playbook: Bookmarks And Delete Video

- PDF pages: 124-128.
- APIs involved: bookmark create/edit/delete/export-time APIs; legacy delete-video endpoint.
- Fixture requirements: archived camera AP, short known time range, `codex-` bookmark label.
- Preflight read snapshot: list bookmarks/events for the target time range and record count/shape.
- Mutation request: create or edit only a `codex-` bookmark; never delete video outside an isolated archive.
- Verification command: read bookmarks for the same time range and verify the `codex-` object only.
- Rollback request: delete the created bookmark by id.
- Post-rollback verification: read bookmarks again and verify the `codex-` id is absent.
- Demo stand result: `bookmark-smoke-latest.md` verifies Bearer bookmark reads, but both documented legacy HTTP create variants return HTTP 501 on the demo stand. A broad `future/past` read after the smoke found zero sampled `codex-` bookmarks.
- gRPC fallback result: `grpc-bookmark-smoke-latest.md` verifies `BookmarkService.CreateBookmark`, filtered `ListBookmarks`, `UpdateBookmark`, filtered `ListBookmarks`, `DeleteBookmark`, and post-delete filtered `ListBookmarks` with a temporary `codex-grpc-bookmark-smoke-*` bookmark.
- Delete-video no-op result: `delete-video-noop-probe-latest.md` verifies the PDF `DELETE /archive/contents/bookmarks/` shape reaches the server and returns HTTP 404 for a `codex-nonexistent-*` endpoint/storage pair. This is dispatch evidence only; real archive deletion still requires an exact target interval and maintenance-window approval.
- Risk level: high for delete-video, medium for bookmark edits.
- Approval requirement: explicit target stand approval and exact time range approval.
