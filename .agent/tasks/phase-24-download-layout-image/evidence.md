# Evidence Bundle: phase-24-download-layout-image

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — download_layout_image_grpc client helper — PASS
- `tools/axxon_api_client.py` gains `download_layout_image_grpc(layout_id,
  image_id, chunk_size_kb=32)` mirroring the existing upload/remove direct-gRPC
  helpers. It opens the `DownloadLayoutImage` server stream, accumulates
  `chunk_data`, and returns `etag` (first response), `total_size_bytes`,
  `chunk_count`, and assembled `data`.
- Proof: helper + `FakeClient.download_layout_image_grpc`; live probe (1 chunk,
  total_size_bytes=70, assembled bytes matched the uploaded PNG, etag present).

## AC2 — download_layout_image tool (metadata-only) — PASS
- `tools/axxon_mcp_view_objects.py` gains `download_layout_image(layout_id,
  image_id, max_bytes=MAP_IMAGE_BYTES_CAP)` returning metadata only: status, tool,
  layout_id, image_id, etag, total_size_bytes, bytes_returned (min(total,cap)),
  truncated, chunk_count, applied_cap. No raw bytes in the response. Unreadable
  image -> gap.
- Proof: `test_download_layout_image_returns_metadata_no_raw_bytes` (asserts no
  `data` key), `test_download_layout_image_truncates_at_cap`,
  `test_download_layout_image_missing_returns_gap`; live status=ok,
  raw_bytes_in_response=False, gap path confirmed.

## AC3 — server registration — PASS
- `download_layout_image` registered next to `list_layout_images` in the existing
  view-objects registration (no new flag/param).
- Proof: raw/test-unit.txt (server import OK).

## AC4 — unit + full suite green — PASS
- 3 new tests (28 in the view-objects suite). Full suite `Ran 793 tests ... OK`
  (raw/test-unit.txt).

## AC5 — corpus restamp + coverage doc — PASS
- DownloadLayoutImage -> tested-pass. Coverage 200 pass-class / 123 pending / 38
  fixture-warn; LayoutImagesManager 4/4. Restamp dry-run reports 0 after --write.

## Stand hygiene
- The download is read-only. A throwaway 1x1 PNG was uploaded as a fixture, then
  downloaded via the tool, then removed; the stand ends with 0 images on the
  layout. No raw image bytes are emitted by the tool or committed. No proto/CA/PDF
  committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`, layout/image
  GUIDs -> `<uuid>`.
