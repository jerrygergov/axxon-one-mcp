# Evidence Bundle: phase-28-collect-backup

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — collect_backup_grpc drain helper — PASS
- `AxxonApiClient.collect_backup_grpc(node, backup_types, chunk_size_kb)` in
  `tools/axxon_api_client.py` drains the ConfigurationManager.CollectBackup server
  stream and returns {node, backup_types, total_size_bytes, chunk_count, byte_count,
  data}. Human backup-type names map to the EBackupType enum via
  `CollectBackupRequest.EBackupType.Value`. Mirrors download_layout_image_grpc.
- Proof: live LOCAL export streamed 28 chunks / 1,822,820 bytes
  (raw/live-verify.txt). Wire shape probed before building.

## AC2 — collect_config_backup metadata-only admin tool — PASS
- `AxxonMcpAdmin.collect_config_backup(node, backup_types, chunk_size_kb)` returns
  metadata only (status, tool, node, backup_types, total_size_bytes, chunk_count,
  byte_count, caps) and never the raw `data` bytes. Empty node or an unknown backup
  type returns {"status":"gap"} with NO wire call. Added to ADMIN_TOOL_NAMES and
  registered as a @server.tool in register_admin_tools.
- Proof: test_collect_config_backup_metadata_only (asserts no `data` key),
  test_collect_config_backup_no_node_is_gap_no_wire,
  test_collect_config_backup_unknown_type_is_gap_no_wire; live status=ok with
  data-key absent (raw/live-verify.txt).

## AC3 — read-only, no secret leak — PASS
- The tool only calls CollectBackup (a config export, the inverse of RestoreBackup).
  No SetRevision / RestoreBackup / mutating call. The fake client records only a
  collect_backup_grpc read. The config password never appears in the response.
- Proof: test_collect_config_backup_no_secret_leak; live-verify hygiene note
  (nothing created/changed/deleted on the stand).

## AC4 — unit + full suite green — PASS
- Admin suite 28 OK (4 new CollectConfigBackup tests). Full suite
  `Ran 805 tests ... OK` (raw/test-integration.txt), up from 801.

## AC5 — corpus restamp + coverage doc — PASS
- ConfigurationManager.CollectBackup -> tested-pass. Coverage 207 pass-class / 116
  pending / 38 fixture-warn; item 10o added. Restamp dry-run reports 0 after --write.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_admin" (build.txt: import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_admin.py -v (28 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 805 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (1 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-28-collect-backup/raw/build.txt
- .agent/tasks/phase-28-collect-backup/raw/test-unit.txt
- .agent/tasks/phase-28-collect-backup/raw/test-integration.txt
- .agent/tasks/phase-28-collect-backup/raw/lint.txt
- .agent/tasks/phase-28-collect-backup/raw/live-verify.txt

## Stand hygiene
- Read-only config export: nothing on the stand was created, changed, or deleted.
  No proto/CA/PDF committed; secrets env-only; raw backup bytes dropped, not surfaced.

## Known gaps
- Tool default is LOCAL; SHARED/LICENSE/TICKETS are accepted but not separately
  live-verified. RestoreBackup/SetRevision (the mutating siblings) stay pending.
