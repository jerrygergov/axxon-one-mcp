# Spec: phase-24-download-layout-image

## Original task statement
Close the pending LayoutImagesManager method `DownloadLayoutImage` (the last of
4) so the service reaches 4/4 tested-pass. It is a server-streaming read that
returns an image in chunks. Add a `download_layout_image_grpc` client helper plus
a read-only `download_layout_image` tool to the existing
`tools/axxon_mcp_view_objects.py` module (which already hosts the layout-image
reads), live-verify it, and restamp the corpus. Like `get_map_image`, the tool
returns image METADATA + a capped byte count only, never raw image bytes.

## Acceptance criteria
- **AC1**: `tools/axxon_api_client.py` gains
  `download_layout_image_grpc(layout_id, image_id, chunk_size_kb=32)` mirroring the
  existing `upload_layout_image_grpc`/`remove_layout_images_grpc` direct-gRPC
  helpers (the HTTP /grpc bridge 500s for LayoutImagesManager). It opens the
  server stream `DownloadLayoutImage(DownloadLayoutImageRequest{layout_id,image_id,
  chunk_size_kb})`, accumulates `chunk_data`, and returns a dict with `etag`
  (first response), `total_size_bytes`, `chunk_count`, and the assembled `data`
  bytes (helper-level; the tool layer caps/strips them).
- **AC2**: `tools/axxon_mcp_view_objects.py` gains
  `download_layout_image(layout_id, image_id, max_bytes=MAP_IMAGE_BYTES_CAP)` that
  calls the helper and returns metadata only: `status`, `tool`, `layout_id`,
  `image_id`, `etag`, `total_size_bytes`, `bytes_returned` (min(total, cap)),
  `truncated`, `chunk_count`, `applied_cap`. It does NOT include raw bytes in the
  response. A not-found / unreadable image returns `{"status":"gap", ...}`.
- **AC3**: The tool `download_layout_image` is registered in
  `tools/axxon_mcp_server.py` next to `list_layout_images` inside the existing
  view-objects registration (no new flag/param; module already wired).
- **AC4**: Unit tests cover: the helper assembles chunks + etag/total from a fake
  stream (in the client test module if present, else view-objects test); the tool
  returns metadata-only with correct `bytes_returned`/`truncated` against the cap
  and excludes raw bytes; and a gap path. Full suite stays green.
- **AC5**: `tools/axxon_corpus_restamp.py` restamps `DownloadLayoutImage` to
  `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json` reflects it
  (LayoutImagesManager 4/4). Coverage doc count moves to 200 pass-class /
  123 pending / 38 fixture-warn and notes the layout-image download. Restamp
  dry-run reports 0 after `--write`.

## Constraints
- Probe-first already done: live round-tripped reversibly through direct gRPC
  (uploaded a throwaway 1x1 PNG to a real layout, downloaded it via the streaming
  RPC — 1 chunk, total_size_bytes=70, bytes matched the upload, etag present —
  then removed it; stand restored). See raw/live-verify.txt.
- Wire shape: `DownloadLayoutImageRequest{layout_id, image_id, chunk_size_kb}` ->
  server stream of `{etag, total_size_bytes, chunk_index, chunk_data}`; etag and
  total_size_bytes are only guaranteed on the first response.
- The tool is READ-ONLY (downloads an existing image); no mutation, no gate. The
  probe's upload/remove were fixture setup only and were fully reversed.
- Do NOT return raw image bytes in the tool response (mirror `get_map_image`:
  metadata + bytes_returned + truncated only). Cap with MAP_IMAGE_BYTES_CAP.
- Reuse the existing direct-gRPC helper idiom in axxon_api_client.py and the
  view_objects `_ensure_client`/gap-shaping idiom.
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`, layout/image GUIDs -> `<uuid>`, etag -> `<etag>`. No proto/CA/PDF
  committed; no real image bytes committed.
- TDD: add the failing tests first, then implement.

## Non-goals
- No image upload/remove tool surfacing (those stay client-helper / smoke level).
- No raw-byte exfiltration through the MCP response; metadata only.
- No new server flag or create_server param.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_view_objects; import axxon_api_client"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_view_objects.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
