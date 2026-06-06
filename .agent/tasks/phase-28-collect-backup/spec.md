# Spec: phase-28-collect-backup

## Original task statement
Close the next safe, reversible pending-API gap. From the destructive/side-effect
review, `ConfigurationManager.CollectBackup` is the read-only member of the
backup/restore cluster: it streams the current configuration out as backup chunks
and mutates nothing. Surface it as a read-only MCP admin tool and mark it
tested-pass after live verification.

Probe results (live, <demo-host>, node "Server"):
- CollectBackup(type=[LOCAL], node="Server", chunk_size_kb=64) streamed 28 chunks /
  ~1.82 MB. Response shape: {total_size_bytes, chunk_index, chunk_data}. Read-only:
  no config was changed; this is a config export, the inverse of RestoreBackup.

## Acceptance criteria

- AC1: `AxxonApiClient.collect_backup_grpc(node, backup_types, chunk_size_kb)` drains
  the `ConfigurationManager.CollectBackup` server stream and returns
  `{total_size_bytes, chunk_count, byte_count, node, backup_types}` plus the assembled
  `data` bytes. backup_types maps human names (LOCAL/SHARED/LICENSE/TICKETS) to the
  CollectBackupRequest enum; an unknown name yields no wire call. Mirrors the existing
  `download_layout_image_grpc` drain idiom.
- AC2: `AxxonMcpAdmin.collect_config_backup(node, backup_types, chunk_size_kb,
  max_bytes)` returns metadata only (status, tool, node, backup_types,
  total_size_bytes, chunk_count, byte_count, truncated) and NEVER the raw `data`
  bytes. Empty/invalid input (no node, or unknown backup type) returns
  `{"status": "gap"}` with NO wire call. Added to ADMIN_TOOL_NAMES and registered as
  a `@server.tool` in register_admin_tools.
- AC3: Tool is read-only. The probe and the shipped tool make no SetRevision /
  RestoreBackup / any mutating call. Unit tests assert the fake client records only
  a CollectBackup-style read and that the response carries no `data` key. Config
  secrets (password) never appear in the response.
- AC4: Unit tests added to tools/tests for the client helper and the admin tool
  (gap-on-empty, metadata-only shape, no-leak). Full suite
  `python3.12 -m unittest discover -s tools/tests` stays green.
- AC5: Corpus restamp `("ConfigurationManager","CollectBackup") -> tested-pass`;
  restamp dry-run reports 0 after --write. Coverage doc updated (count + new item).
  Live verify through the shipped tool recorded under raw/live-verify.txt.

## Constraints
- Read-only against the live stand. No mutation, no fixture wall.
- Reuse the download_layout_image_grpc drain pattern and the admin module idiom
  (ensure_client, redact, ADMIN_TOOL_NAMES, register_admin_tools).
- No module-level `time` import in axxon_api_client.py (prior phase-25 bug).
- Metadata-only tool surface: never return raw backup bytes to the MCP caller.

## Non-goals
- RestoreBackup, SetRevision, persisting the backup to disk.
- CollectBackup default stays LOCAL; the helper accepts SHARED/LICENSE/TICKETS but
  the tool default is LOCAL.

## Verification plan
- Build: pyimport smoke (server + admin import clean)
- Unit tests: client helper + admin tool (gap-on-empty, metadata-only, no-leak)
- Integration tests: full suite discover
- Lint: n/a (matches repo convention)
- Manual checks: live collect_config_backup(node="Server") -> status ok,
  total_size_bytes>0, chunk_count>0, no data key; gap on unknown backup type with no
  wire call; restamp dry-run == 0 after write
