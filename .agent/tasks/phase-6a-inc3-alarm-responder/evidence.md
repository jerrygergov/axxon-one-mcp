# Evidence: phase-6a-inc3-alarm-responder

## Summary
Added the `alarm_responder` template (Python + Node) as the first of the 6 new Phase 6A
template kinds. It reads active alerts via `LogicService.GetActiveAlerts`, then runs the
`BeginAlertReview` -> `CompleteAlertReview` review lifecycle per alert, bounded by count and
duration caps. Because the lifecycle is mutating, generation refuses without
`allow_mutation=True`.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 catalog entry (python+node, operator param, env) | PASS | `test_catalog_entry`; `list_templates()` includes alarm_responder |
| AC2 python bundle (main.py/README/requirements) | PASS | `test_python_returns_bundle`; manual: files=['README.md','main.py','requirements.txt'] |
| AC3 refuses without allow_mutation | PASS | `test_refuses_without_allow_mutation`; manual: GenerationRefusal reason=refused_mutation |
| AC4 bakes DURATION/COUNT/OPERATOR + cap_exceeded | PASS | `test_python_bakes_caps_and_operator`, `test_python_cap_exceeded` |
| AC5 os.environ + 3 lifecycle methods | PASS | `test_python_env_and_lifecycle`; manual: caps baked True, lifecycle True |
| AC6 node bundle bakes caps, process.env, lifecycle | PASS | `test_node_returns_bundle`, `test_node_bakes_caps_env_lifecycle` |
| AC7 verifier passes both bundles | PASS | `test_verifier_passes_python`, `test_verifier_passes_node`; manual: verify py True, node True |
| AC8 list_templates includes alarm_responder | PASS | `test_catalog_entry` |
| AC9 pre-existing tests pass, count grows | PASS | full suite 568/568 (was 558) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_generator_6a_inc3
Ran 10 tests in 0.043s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 568 tests in 0.373s
OK
```

## Manual generation check (sanitized)

```
PY type: GeneratedBundle | files: ['README.md', 'main.py', 'requirements.txt']
caps baked: True True True
lifecycle: True
no env literal: True
verify py: True
NODE verify: True
no-mutation refusal: GenerationRefusal refused_mutation
```

## Files changed
- tools/axxon_mcp_generator.py (catalog entry, dispatch branch, `_build_alarm_responder`)
- tools/templates/alarm_responder.py.tmpl (new)
- tools/templates/alarm_responder.ts.tmpl (new)
- tools/tests/test_axxon_mcp_generator_6a_inc3.py (new, 10 tests)
- tools/tests/test_axxon_mcp_generator.py (template-name list updated)

## Notes
- Offline code-generation verify only; the mutating alert lifecycle is not exercised live
  on the demo stand in this increment (per spec non-goals).
