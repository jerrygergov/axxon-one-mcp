# Evidence: Phase 1 Coverage Reconciliation + Site Graph

## Summary

Phase 1 implemented a read-only `site_graph` capability that joins inventory, archives,
detectors, layouts, maps, markers, permissions, health, access points, event suppliers, and
metadata endpoints into one sanitized graph. It also reconciled README and roadmap tool/group
counts. No destructive Phase C work, proto files, CA material, or live credentials were added.

## Acceptance Criteria

| AC | Status | Evidence |
| --- | --- | --- |
| AC1 | PASS | `tools/axxon_mcp_site_graph.py` defines `AxxonMcpSiteGraph`, `SITE_GRAPH_TOOL_NAMES`, `site_graph_connect_axxon_profile`, lazy `ensure_client`, and `build_site_graph`. `tools/tests/test_axxon_mcp_site_graph.py::test_connect_env_profile_is_lazy_and_redacted` covers env/non-env connect behavior and redacted profile output. |
| AC2 | PASS | `tools/axxon_mcp_site_graph.py` returns `status`, `tool`, `summary`, `collections`, `nodes`, `edges`, `gaps`, and `source_sections`. `test_build_graph_joins_inventory_layouts_maps_security_and_health` verifies cameras, archives, detectors, appdata detectors, layouts, maps, markers, event suppliers, metadata endpoints, permissions, health summaries, stable node IDs, and representative edge types. |
| AC3 | PASS | Optional sections are collected through `_collect`, which records section gaps without discarding other graph data. `test_partial_section_failure_warns_without_dropping_inventory` proves a map-section failure returns top-level `warn`, preserves camera inventory, and records a sanitized `maps` gap. |
| AC4 | PASS | `redact_site_graph` redacts secret-like keys/text and converts raw bytes to metadata. `test_redacts_secret_like_fields_and_raw_bytes` verifies password/token/CA/license/serial/media sentinels do not leak while raw-byte metadata keeps `byte_count`. |
| AC5 | PASS | `tools/axxon_mcp_server.py` adds `site_graph` to `CAPABILITY_GROUPS`, `create_server`, enabled group reporting, conditional registration, `register_site_graph_tools`, `--enable-site-graph`, `main()` construction, and `list_capabilities`. `test_create_server_registers_site_graph_tools_only_when_enabled`, `test_list_capabilities_reports_site_graph_disabled_and_enabled`, and raw `help_enable_site_graph.txt` prove the wiring. |
| AC6 | PASS | `README.md` now reports 293 all-enabled MCP tools across 48 groups and documents the site graph layer. `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` reports 293 tools / 48 groups and marks `site_graph` implemented. `docs/COVERAGE.md` was not changed because no per-RPC coverage status changed. Raw `tool_count.txt` proves 288 server-local tools, 5 delegated translator tools, 293 runtime tools, 48 groups, and zero duplicate server-local tool names. |
| AC7 | PASS | New `tools/tests/test_axxon_mcp_site_graph.py` covers connect/redaction, graph joins, summary counts, node IDs, edge schema/types, dedupe, optional-section gaps, and raw-byte/secret redaction. `tools/tests/test_axxon_mcp_server.py` covers parser flag, disabled/enabled registration, and capabilities. Focused raw outputs: `green_site_graph_unittest.txt`, `green_server_unittest.txt`. |
| AC8 | PASS | No optional live smoke script was added or run. No live credentials, proto files, CA files, raw images, raw media, or symlinks were written or committed. |

## Raw Artifacts

- `raw/red_site_graph_unittest.txt`: RED proof for missing `axxon_mcp_site_graph`.
- `raw/red_server_unittest.txt`: RED proof for missing server signature/capability wiring.
- `raw/green_site_graph_unittest.txt`: `python3.12 -m unittest discover -s tools/tests -p 'test_axxon_mcp_site_graph.py'` passed, 6 tests.
- `raw/green_server_unittest.txt`: `python3.12 -m unittest tools/tests/test_axxon_mcp_server.py` passed, 28 tests.
- `raw/help_enable_site_graph.txt`: CLI help includes `--enable-site-graph`.
- `raw/tool_count.txt`: server-local tool count, duplicate check, runtime tool count, capability group count.
- `raw/git_diff_check.txt`: `git diff --check` clean.
- `raw/full_unittest.txt`: required `python3.12 -m unittest discover -s tools/tests` passed, 1114 tests.

## Verification Commands

```bash
python3.12 -m unittest discover -s tools/tests -p 'test_axxon_mcp_site_graph.py'
python3.12 -m unittest tools/tests/test_axxon_mcp_server.py
python3.12 tools/axxon_mcp_server.py --help | rg -- '--enable-site-graph'
python3.12 -m unittest discover -s tools/tests
git diff --check
```
