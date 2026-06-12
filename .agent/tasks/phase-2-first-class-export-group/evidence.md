# Phase 2 First-Class Export Group Evidence

Builder evidence for AC1-AC19 is complete. No `verdict.json` was written; the fresh verifier owns the final verdict.

## Raw Artifacts

- `raw/red_export_unittest.txt`: expected RED, `ModuleNotFoundError: No module named 'axxon_mcp_export'`, `exit_code=1`.
- `raw/red_server_unittest.txt`: expected RED, missing `export` capability and missing `AXXON_EXPORT_APPROVE`, `exit_code=1`.
- `raw/green_export_unittest.txt`: `Ran 11 tests ... OK`, `exit_code=0`.
- `raw/green_server_unittest.txt`: `Ran 30 tests ... OK`, `exit_code=0`.
- `raw/adjacent_export_regressions.txt`: `Ran 103 tests ... OK`, `exit_code=0`.
- `raw/full_unittest.txt`: `Ran 1127 tests ... OK`, `exit_code=0`.
- `raw/tool_count.txt`: `server_local_tool_count=296`, `delegated_translator_tool_count=5`, `all_enabled_runtime_tool_count=301`, `capability_group_count=49`, `export_tool_count=8`, `exit_code=0`.
- `raw/help_enable_export.txt`: `--enable-export` appears in CLI help, `exit_code=0`.
- `raw/git_diff_check.txt`: refreshed after evidence creation; expected `exit_code=0`.
- `raw/secret_scan.txt`: noisy scan reports only test sentinels/API parameter names/policy text and unit-test byte fixtures, no live secrets or downloaded export artifacts, `exit_code=0`.
- `raw/coverage_diff.txt`: no `docs/COVERAGE.md` diff, `exit_code=0`.

## Acceptance Criteria

| AC | Status | Proof |
| --- | --- | --- |
| AC1 | PASS | `tools/axxon_mcp_export.py` defines the export constants and tool names at lines 25-55, uses dataclasses/factories at lines 102-165, and default construction does not create a client until connect at lines 171-193. `raw/green_export_unittest.txt` passes. |
| AC2 | PASS | `EXPORT_TOOL_NAMES` contains the eight required names at `tools/axxon_mcp_export.py:46`; `register_export_tools` registers the same eight names at `tools/axxon_mcp_server.py:1575`. `raw/tool_count.txt` proves `export_tool_count=8`. |
| AC3 | PASS | `export_connect_axxon_profile` is env-only, factory-backed, reports mode/approval env, and returns public config at `tools/axxon_mcp_export.py:171`. Redaction/laziness are tested in `tools/tests/test_axxon_mcp_export.py:265`. |
| AC4 | PASS | `export_plan_snapshot` validates required inputs, caps file/download/chunk/time values, returns plan metadata and confirmation without wire access at `tools/axxon_mcp_export.py:216` and `:261`. Tested at `tools/tests/test_axxon_mcp_export.py:280`. |
| AC5 | PASS | Start uses approval/token gate at `tools/axxon_mcp_export.py:201` and `:329`, builds `StartSession` options with codex filename/marker and `store_result_by_export_agent=False` at `:295`, and records ownership at `:353`. Tested at `tools/tests/test_axxon_mcp_export.py:305` and `:316`. |
| AC6 | PASS | `export_status` requires owned sessions and returns normalized state/file metadata only at `tools/axxon_mcp_export.py:373` and `:396`. Tested at `tools/tests/test_axxon_mcp_export.py:332`. |
| AC7 | PASS | `export_download` requires approval/ownership, caps bytes/chunks/chunk size/time, hashes bytes, reports truncation and MIME metadata, and never returns raw bytes at `tools/axxon_mcp_export.py:427`. Tested at `tools/tests/test_axxon_mcp_export.py:348`. |
| AC8 | PASS | Safe destination policy rejects absolute paths, separators, traversal, symlink roots, symlink destinations, and resolved escapes at `tools/axxon_mcp_export.py:408`. Tested at `tools/tests/test_axxon_mcp_export.py:379`. |
| AC9 | PASS | Stop/destroy/cleanup share the approval/token gate, use `_owned_or_refused`, and remove only owned sessions after destroy at `tools/axxon_mcp_export.py:516`, `:531`, and `:546`. Tested at `tools/tests/test_axxon_mcp_export.py:420`. |
| AC10 | PASS | Owned sessions are represented by `OwnedExportSession` at `tools/axxon_mcp_export.py:138`, starts add ownership at `:353`, destroys remove it at `:541`, and cleanup reports attempted/stopped/destroyed/skipped/failed at `:546`. Cleanup/failure tests are at `tools/tests/test_axxon_mcp_export.py:441` and `:454`. |
| AC11 | PASS | Server wiring includes `CAPABILITY_GROUPS` export entry at `tools/axxon_mcp_server.py:37`, `create_server(export=...)` at `:143`, enabled groups at `:213`, registration at `:397`, CLI flag at `:2598`, approval env at `:2647`, `main()` construction at `:2970`, and create_server argument at `:3033`. Server tests pass in `raw/green_server_unittest.txt`. |
| AC12 | PASS | README documents 301 tools, 49 groups, 296 server-local plus 5 translator tools at `README.md:21`; roadmap documents the same at `docs/ALL_IN_ONE_VMS_API_ROADMAP.md:35`; `raw/tool_count.txt` independently proves counts. |
| AC13 | PASS | Roadmap now describes the first-class export group at `docs/ALL_IN_ONE_VMS_API_ROADMAP.md:64` and `:119`, and removes export from intent-polish backlog at `:160`. `raw/coverage_diff.txt` proves `docs/COVERAGE.md` stayed unchanged. |
| AC14 | PASS | RED artifacts were captured before production implementation: `raw/red_export_unittest.txt` has `ModuleNotFoundError`; `raw/red_server_unittest.txt` has missing export capability/env failures. |
| AC15 | PASS | `tools/tests/test_axxon_mcp_export.py` includes fake proto/stub/client tests for constants, lazy/redacted connect, planning, gates, start options, ownership, status, download caps/path policy/no bytes, stop/destroy, and cleanup at lines 15-472. `raw/green_export_unittest.txt` passes. |
| AC16 | PASS | `tools/tests/test_axxon_mcp_server.py` covers export stubs and registration at lines 339-418, server registration/capability/flag at lines 538-585, all-groups duplicate protection in the existing full-group test, and default approval env at lines 1159-1167. `raw/green_server_unittest.txt` passes. |
| AC17 | PASS | Adjacent regression command covers server, export_preflight, export_smoke, http_export_smoke, generator, generator_6a_inc2, generator_6a_inc4, and customer_templates; `raw/adjacent_export_regressions.txt` reports `Ran 103 tests ... OK`. |
| AC18 | PASS | Evidence files and raw artifacts exist under `.agent/tasks/phase-2-first-class-export-group/`; raw artifacts include red/green logs, focused/adjacent/full tests, `git diff --check`, count proof, help proof, coverage diff, and scan output. |
| AC19 | PASS | Required final checks pass: `raw/full_unittest.txt` reports `Ran 1127 tests ... OK`; `raw/git_diff_check.txt` has `exit_code=0`. |

## Optional / Verifier-Owned Criteria

- AC20: Fresh verifier owns `verdict.json`; builder did not create it.
- AC21: Controlled live smoke was not attempted. Offline completion was sufficient and avoids proto symlink/secrets risk.
- AC22: Commit/push intentionally not performed; parent/verifier owns that after PASS.
