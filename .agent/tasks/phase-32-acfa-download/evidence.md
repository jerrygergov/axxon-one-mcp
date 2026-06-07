# Evidence Bundle: phase-32-acfa-download

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-07

## AC1 — list_unit_visualizations read tool — PASS
- Streams AcfaService.ListUnitsVisualizations; returns {status: ok, units:[{uid,
  visualizations:[{id,name,kind,image_data_ids}]}]}, surfacing icon image data_ids.
  Empty uids -> error, no wire call.
- Proof: tests test_list_unit_visualizations_surfaces_image_data_ids /
  test_list_unit_visualizations_empty_is_error_no_wire; live returned the lock's two
  icon data_ids (raw/live-verify.txt).

## AC2 — download_unit_data metadata-only tool — PASS
- Streams AcfaService.DownloadData; returns {status: ok, tool, uid, count, items:
  [{data_id, byte_count}], total_bytes}. Raw blob never returned. Missing uid or empty
  data_ids -> error, no wire call.
- Proof: test_download_unit_data_metadata_only (asserts no `data` key),
  test_download_unit_data_missing_uid_is_error_no_wire,
  test_download_unit_data_empty_ids_is_error_no_wire; live count=2, 344 bytes each, no
  data blob (raw/live-verify.txt).

## AC3 — read-only, no secret leak — PASS
- Both tools only call read RPCs (no mutation). The download payload is measured, not
  echoed. Config password absent from the response.
- Proof: test_download_unit_data_no_config_secret_leak; live-verify hygiene note.

## AC4 — wiring + suite green — PASS
- Both registered as @server.tool in the existing register_control_tools; added to
  CONTROL_TOOL_NAMES. control suite 17 OK (6 new). Full suite `Ran 830 ... OK`
  (raw/test-integration.txt), up from 824.

## AC5 — corpus restamp + coverage doc — PASS
- AcfaService.DownloadData -> tested-pass. Coverage 213 pass-class / 110 pending / 38
  fixture-warn; item 10s. Restamp dry-run 0 after --write. AcfaService now 7/7.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_acfa_vmda_control" (import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_acfa_vmda_control.py -v (17 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 830 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (1 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-32-acfa-download/raw/build.txt
- .agent/tasks/phase-32-acfa-download/raw/test-unit.txt
- .agent/tasks/phase-32-acfa-download/raw/test-integration.txt
- .agent/tasks/phase-32-acfa-download/raw/lint.txt
- .agent/tasks/phase-32-acfa-download/raw/live-verify.txt

## Stand hygiene
- Read-only download of existing icon images; nothing created/changed/deleted.
  Metadata-only surface (no raw media bytes). No proto/CA/PDF committed; secrets
  env-only.

## Known gaps
- None for AcfaService (7/7 complete). DownloadData returns metadata only by design;
  raw image bytes are not exposed through the MCP tool.
