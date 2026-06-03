# Evidence: phase-6a-inc4-scheduled-exporter

## Summary
Added the `scheduled_exporter` template (Python + Node) as the second new Phase 6A template
kind. It wraps the `export_job` inspector pattern in a bounded scheduled loop: every
INTERVAL_SECONDS it runs `ExportService.ListSessions` for a camera, up to MAX_RUNS times,
enforcing a per-run BYTE_CAP. The call is read-safe, so no mutation gate is required.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 catalog entry (python+node, camera_ap, env) | PASS | `test_catalog_entry` |
| AC2 python bundle, no mutation gate | PASS | `test_python_returns_bundle`; manual files=['README.md','main.py','requirements.txt'] |
| AC3 bakes INTERVAL/MAX_RUNS/BYTE_CAP/CAMERA_AP | PASS | `test_python_bakes_constants`; manual baked=True |
| AC4 cap_exceeded on interval floor / max_runs cap | PASS | `test_refuses_interval_too_small`, `test_refuses_max_runs_too_large`; manual both cap_exceeded |
| AC5 os.environ + ListSessions | PASS | `test_python_env_and_method` |
| AC6 node bundle bakes constants, process.env, ListSessions | PASS | `test_node_returns_bundle`, `test_node_bakes_env_method` |
| AC7 verifier passes both bundles | PASS | `test_verifier_passes_python`, `test_verifier_passes_node`; manual verify py/node True |
| AC8 list_templates includes scheduled_exporter | PASS | `test_catalog_entry` |
| AC9 pre-existing tests pass, count grows | PASS | full suite 578/578 (was 568) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_generator_6a_inc4
Ran 10 tests in 0.039s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 578 tests in 0.442s
OK
```

## Manual generation check (sanitized)

```
PY files: ['README.md', 'main.py', 'requirements.txt']
baked: True True True True
verify py: True
verify node: True
interval refusal: cap_exceeded
max_runs refusal: cap_exceeded
```

## Files changed
- tools/axxon_mcp_generator.py (constants, catalog entry, dispatch, `_build_scheduled_exporter`)
- tools/templates/scheduled_exporter.py.tmpl (new)
- tools/templates/scheduled_exporter.ts.tmpl (new)
- tools/tests/test_axxon_mcp_generator_6a_inc4.py (new, 10 tests)
- tools/tests/test_axxon_mcp_generator.py (template-name list updated)

## Notes
- Offline code-generation verify only; the real export start/poll/destroy lifecycle stays
  operator-owned and is not exercised here (per spec non-goals).
