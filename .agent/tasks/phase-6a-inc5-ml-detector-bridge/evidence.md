# Evidence: phase-6a-inc5-ml-detector-bridge

## Summary
Added the `ml_detector_bridge` template (Python + Node) as the third new Phase 6A template
kind. It reads a bounded batch of external ML inference results from a local JSON file
(RESULTS_PATH) and raises one external detector event per result via
`ExternalDetectorService.RaiseOccasionalEvent` (direct gRPC). Raising events is mutating, so
generation refuses without `allow_mutation=True`. The batch is bounded by COUNT_CAP and a
DURATION_SECONDS deadline.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 catalog entry (python+node, access_point+results_path, env) | PASS | `test_catalog_entry` |
| AC2 python bundle (main.py/README/requirements) | PASS | `test_python_returns_bundle`; manual files=['README.md','main.py','requirements.txt'] |
| AC3 refuses without allow_mutation | PASS | `test_refuses_without_allow_mutation`; manual reason=refused_mutation |
| AC4 bakes ACCESS_POINT/RESULTS_PATH/COUNT_CAP/DURATION + cap_exceeded | PASS | `test_python_bakes_constants`, `test_python_cap_exceeded`; manual baked True, cap_exceeded |
| AC5 os.environ + RESULTS_PATH + RaiseOccasionalEvent | PASS | `test_python_env_results_method` |
| AC6 node bundle bakes constants, process.env, RESULTS_PATH, method | PASS | `test_node_returns_bundle`, `test_node_bakes_env_results_method` |
| AC7 verifier passes both bundles | PASS | `test_verifier_passes_python`, `test_verifier_passes_node`; manual verify py/node True |
| AC8 list_templates includes ml_detector_bridge | PASS | `test_catalog_entry` |
| AC9 pre-existing tests pass, count grows | PASS | full suite 588/588 (was 578) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_generator_6a_inc5
Ran 10 tests in 0.042s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 588 tests in 0.475s
OK
```

## Manual generation check (sanitized)

```
PY files: ['README.md', 'main.py', 'requirements.txt']
baked: True True True True True
verify py: True
verify node: True
no-mutation: refused_mutation
cap: cap_exceeded
```

## Files changed
- tools/axxon_mcp_generator.py (catalog entry, dispatch, `_build_ml_detector_bridge`)
- tools/templates/ml_detector_bridge.py.tmpl (new)
- tools/templates/ml_detector_bridge.ts.tmpl (new)
- tools/tests/test_axxon_mcp_generator_6a_inc5.py (new, 10 tests)
- tools/tests/test_axxon_mcp_generator.py (template-name list updated)

## Notes
- Offline code-generation verify only; the mutating RaiseOccasionalEvent call is not exercised
  live on the demo stand in this increment (per spec non-goals).
