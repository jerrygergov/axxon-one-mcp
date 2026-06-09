# Phase A — full live verification (Step 10 / AC9)

**Date:** 2026-06-09
**Target:** `%3Cdemo-host%3E` (HTTP :80 `/grpc` bridge for reads; direct gRPC :20109, `AXXON_TLS_CN=Server`)
**Scope:** every one of the new Phase A tools exercised against the real stand (not just one read
per group). Run via a Sonnet sub-agent. Inputs discovered at runtime (real vendor/model, real
directory path), not hardcoded.

## Result — PASS=32, WARN=1, FAIL=0

| Tool | Verdict | Detail |
| --- | --- | --- |
| get_statistics | PASS | count=0 (no streams active) |
| get_event_grouping_tags | PASS | count=0 |
| list_scene_description | PASS | count=10 (dotted-proto `Node.Ancillary` stub resolves live) |
| check_package_availability | WARN | server `UNIMPLEMENTED` — subsystem not active on this stand |
| enumerate_nodes | PASS | node_count=1 |
| get_revision_info (LOCAL_CONFIG) | PASS | 1 node |
| get_revision_info (SHARED_CONFIG) | PASS | 1 node |
| collect_backup_probe | PASS | chunks_seen=2, bytes_seen=65536, truncated=True (chunk cap) — blob never returned |
| list_directory (root) | PASS | count=2; first dir `C:\` |
| get_file_info | PASS | type=DIRECTORY for discovered path |
| get_space | PASS | capacity≈509 GB, free≈141 GB |
| list_vendors | PASS | count=318 |
| list_vendors_v2 | PASS | 318, 1 page, truncated=False |
| list_devices | PASS | count=1000 (first `3S/N1011`) |
| list_devices_v2 | PASS | 2000 across 2 pages, truncated=True (page cap) |
| get_device | PASS | `3S/N1011`; **no credential leak in output** |
| get_profile | PASS | count=0 (no tracker fixture on stand — expected) |
| list_records | PASS | count=8 |
| get_records | PASS | absent key returns empty revision (presence == revision != "") |
| get_records_stream | PASS | chunks_seen=3, bytes_seen=73728, truncated=True (chunk cap) |
| commit_record (set→readback→remove) | PASS | error_code=EOK; **reverted=True, key gone, stand clean** |

## What live verification confirmed (beyond unit tests)

- **Headline `devices_catalog` works end-to-end:** 318 vendors, 1000+ models, `get_device` with a
  real vendor/model pair, and device default credentials are never surfaced.
- **All streaming tools stream and cap correctly** against the real server: `list_devices_v2`,
  `collect_backup_probe`, `get_records_stream` each truncate at their cap with partial-result
  reporting; the backup blob is never returned.
- **The dotted-proto module** (`axxonsoft.bl.node.Node.Ancillary.proto` → `..Node.Ancillary_pb2`)
  resolves and streams at runtime — the one runtime risk flagged during the build.
- **The one mutation is reversible:** `shared_kv.commit_record` set→remove round-trip reverts and
  leaves no `codex-*` residue.
- **The single WARN** (`package_availability`) is a stand capability gap (`UNIMPLEMENTED`), not a
  tool defect; the tool faithfully surfaces the server response.

## Sanitization

Host → `%3Cdemo-host%3E`, user/password → `%3Credacted%3E`. `AXXON_TLS_CN=Server` retained
(non-secret fact). No proto files, CA, credentials, or symlink committed; the gitignored CA +
protos already live at `docs/grpc-proto-files/`.
