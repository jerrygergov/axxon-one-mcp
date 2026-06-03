# Evidence: phase-6a-inc7-plugin-scaffold

## Summary
Added the `plugin_scaffold` template (Python + Node) as the fifth new Phase 6A template kind,
and the last buildable one this phase (ptz_controller needs a live PTZ fixture). Unlike the
single-entrypoint consumer templates, this emits a complete runnable repo skeleton: an
entrypoint that authenticates and lists cameras with a bounded retry, an env-only credential
loader, a smoke test, a CI workflow, a README with a Safety section, a LICENSE placeholder,
and an `.env.example`. The scaffold performs only a read (ListCameras); no mutation gate.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 catalog entry (python+node, name, env) | PASS | `test_catalog_entry` |
| AC2 python file set (entrypoint/README/req/env/test/CI/LICENSE) | PASS | `test_python_file_set`; manual 7-file set |
| AC3 entrypoint bakes NAME, os.environ, ListCameras, retry | PASS | `test_python_entrypoint` |
| AC4 README Safety section + .env.example, no real values | PASS | `test_readme_and_env_example` |
| AC5/AC7 verifier passes (test+CI present, no secrets) | PASS | `test_verifier_passes_python` |
| AC6 node file set + entrypoint (process.env, ListCameras, retry) | PASS | `test_node_file_set`, `test_node_entrypoint` |
| AC7 verifier passes node | PASS | `test_verifier_passes_node` |
| AC8 list_templates includes plugin_scaffold | PASS | `test_catalog_entry` |
| AC9 pre-existing tests pass, count grows | PASS | full suite 604/604 (was 596) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_generator_6a_inc7
Ran 8 tests in 0.041s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 604 tests in 0.597s
OK
```

## Manual file sets

```
PY files: ['.env.example', '.github/workflows/ci.yml', 'LICENSE', 'README.md', 'main.py', 'requirements.txt', 'test_smoke.py']  verify: True
NODE files: ['.env.example', '.github/workflows/ci.yml', 'LICENSE', 'README.md', 'package.json', 'src/index.ts', 'test/smoke.test.ts']  verify: True
```

## Live verification on the stand (sanitized)

Generated the Python scaffold to a temp dir and ran it against <demo-host>:20109 (CN=Server):

```
$ python3.12 main.py
INFO plugin=acme-bridge user=<demo-user> password=<redacted> host=<demo-host>:20109
{"plugin": "acme-bridge", "cameras": 37}
```

Ran the scaffold's own generated smoke test:

```
$ python3.12 -m unittest test_smoke
Ran 3 tests ... OK
```

## Files changed
- tools/axxon_mcp_generator.py (catalog, dispatch, `_build_plugin_scaffold`, `_env_example`,
  `_ci_workflow`, `_license_placeholder` helpers; ALLOWED_IMPORTS += unittest, main)
- tools/templates/README.md.tmpl (added Safety section)
- tools/templates/plugin_scaffold.py.tmpl, plugin_scaffold.ts.tmpl (new entrypoints)
- tools/templates/plugin_scaffold.test.py.tmpl, plugin_scaffold.test.ts.tmpl (new tests)
- tools/tests/test_axxon_mcp_generator_6a_inc7.py (new, 8 tests)
- tools/tests/test_axxon_mcp_generator.py (template-name list updated)

## Notes
- The scaffold authenticates with a bounded retry (MAX_RETRIES=3, linear backoff) and lists
  cameras read-only, so the live run leaves nothing changed on the stand.
