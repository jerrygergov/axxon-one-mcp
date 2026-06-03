# Evidence: phase-6a-inc6-dashboard-backend

## Summary
Added the `dashboard_backend` template (Python + Node) as the fourth new Phase 6A template
kind. It is a read-only aggregation: it collects a dashboard snapshot from three read-safe
sources (`DomainService.ListCameras`, `LogicService.GetActiveAlerts`,
`EventHistoryService.ReadEvents`) and writes one JSON file to OUTPUT_PATH, enforcing BYTE_CAP
on the serialised output. No mutation gate.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 catalog entry (python+node, output_path, env) | PASS | `test_catalog_entry` |
| AC2 python bundle, no mutation gate | PASS | `test_python_returns_bundle`; manual files=['README.md','main.py','requirements.txt'] |
| AC3 bakes OUTPUT_PATH and BYTE_CAP | PASS | `test_python_bakes_constants`; manual baked True |
| AC4 os.environ + OUTPUT_PATH + 3 sources | PASS | `test_python_env_output_sources`; manual sources/env True |
| AC5 node bundle bakes constants, process.env, 3 sources | PASS | `test_node_returns_bundle`, `test_node_bakes_env_sources`; manual sources node True |
| AC6 verifier passes both bundles | PASS | `test_verifier_passes_python`, `test_verifier_passes_node`; manual verify py/node True |
| AC7 list_templates includes dashboard_backend | PASS | `test_catalog_entry` |
| AC8 pre-existing tests pass, count grows | PASS | full suite 596/596 (was 588) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_generator_6a_inc6
Ran 8 tests in 0.038s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 596 tests in 0.521s
OK
```

## Manual generation check (sanitized)

```
PY files: ['README.md', 'main.py', 'requirements.txt']
baked: True True
sources py: True env: True
verify py: True
sources node: True
verify node: True
```

## Files changed
- tools/axxon_mcp_generator.py (catalog entry, dispatch, `_build_dashboard_backend`)
- tools/templates/dashboard_backend.py.tmpl (new)
- tools/templates/dashboard_backend.ts.tmpl (new)
- tools/tests/test_axxon_mcp_generator_6a_inc6.py (new, 8 tests)
- tools/tests/test_axxon_mcp_generator.py (template-name list updated)

## Notes
- Offline code-generation verify only; the three read calls are not exercised live against the
  demo stand in this increment (per spec non-goals).
- `GetActiveAlerts` and `ReadEvents` are wrapped in the existing bounded `grpc.RpcError` guard
  so a single source closing does not abort the whole snapshot.
