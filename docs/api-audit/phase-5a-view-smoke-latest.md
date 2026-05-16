# Phase 5A — View Tools Smoke Evidence

**Date:** 2026-05-16
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP `/grpc`)
**Cap defaults:** bytes = 1 MiB; live duration = 10 s; live fps = 5; archive MJPEG bytes = 4 MiB; archive threshold = 60 s

## Status

| Tool | Offline test coverage | Live evidence |
| --- | --- | --- |
| `view_connect_axxon_profile` | verified (4 assertions across 2 profile types) | pending — needs proto + CA fixture |
| `live_view` (mjpeg, hls, mp4, rtsp) | verified (5 tests including format gap and sub-default duration) | pending |
| `snapshot_batch` | verified (10-in / 8-cap / 2-known / 6-gap) | pending |
| `archive_scrub` | verified (combined calendar + intervals + sample-frame URL; gap path) | pending |
| `archive_frame` | verified (threshold + bytes cap) | pending |
| `archive_mjpeg_bounded` | verified (speed/fps/byte cap clamps) | pending |
| `stream_health` | verified (`/statistics/...` + `/rtsp/stat` summary, no password leak) | pending |

12 offline unit tests in `tools/tests/test_axxon_mcp_view.py` plus 1 MCP-server registration test in `tools/tests/test_axxon_mcp_server.py` cover every tool's argument validation, cap enforcement, gap handling, and sanitization. Full repo suite: 187 / 187 passing.

## Live smoke

`tools/axxon_view_smoke.py` ships with the same env-driven configuration as every other `axxon_*_smoke.py` in this repo. It runs all seven view tools against a real stand (`AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=<demo-tls-cn>`), can optionally fetch each returned URL with `--fetch` (bounded by `caps.bytes`), and sanitizes the host to `<demo-host>` before printing.

Live execution from this published worktree is fixture-blocked: the `docs/grpc-proto-files/` directory (proto files + `api.ngp.root-ca.crt`) is gitignored under the repo's existing AxxonSoft-copyright policy. The smoke script itself is complete and runnable on a workstation that has the proto fixture in place — the same prerequisite as the existing media / archive smokes.

When the smoke runs on a fixture-equipped stand, expected `--fetch` output is `http_status: 200` for each `result.status == "ok"` URL, `bytes_read <= caps.bytes`, and `truncated: false` for all single-frame URLs. Any 404/401 from the demo stand at `100.76.150.18` would indicate a real bug rather than a fixture gap and must be fixed before this evidence file is updated.

## Sanitization rules applied

- Host IP replaced with `<demo-host>` in every printed URL (`sanitize_url` helper in `axxon_view_smoke.py`).
- TLS CN replaced with `<your-tls-cn>` in README and matrix entries.
- `hosts/Server/...` access points kept as-is in evidence (intrinsic to the stand, not credential material).
- Bearer token never printed; smoke only echoes `http_status`, `content_type`, `bytes_read`, `truncated`.
- Passwords never printed; `FakeConfig.password = "secret"` is asserted absent in `str(result)` by every tool test.

## Next step

When this repository is run on the AxxonSoft-internal workstation with proto + CA fixture in place, append the sanitized `--fetch` JSON output below this line and update the table's "Live evidence" column from `pending` to `verified`.
