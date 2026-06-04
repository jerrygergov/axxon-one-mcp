# Evidence: phase-7-nl-translator

## Summary
Added the Phase 7 NL -> plan translator: module `tools/axxon_mcp_translator.py`
(`AxxonMcpTranslator`) with `assemble_recipe` (English intent -> ordered steps over existing
operator workflows), `validate_recipe` (dry-run each step via `OperatorRegistry.plan`, aggregate
risk/approvals/gaps), and `explain_recipe` (offline risk + rollback + wall-clock preview).
Registered as MCP tools behind `--enable-translator`. The translator composes known workflows
only and never invents API shapes; unsupported intents (PTZ, role, permission) return a
structured `unsupported_intent` gap. Live-verified end to end against the demo stand.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 module + 3 methods | PASS | `tools/axxon_mcp_translator.py`: `AxxonMcpTranslator.assemble_recipe/validate_recipe/explain_recipe`; imports with no side effects |
| AC2 assemble maps >=10 reference intents | PASS | `_INTENT_RULES` maps I-1..I-10 to known WORKFLOWS keys; tests assert every emitted `workflow` is in `WORKFLOWS` |
| AC3 unsupported intent gap | PASS | `_UNSUPPORTED_PATTERNS` (PTZ/preset/role/permission/user/password/assign/grant); returns `status=unsupported_intent` |
| AC4 validate dry-runs via operator.plan | PASS | `validate_recipe` calls only `.plan`; aggregates `valid`/`steps`/`risk_classes`/`required_approvals`/`gaps`; happy + gapped tests |
| AC5 explain risk+rollback+time, offline | PASS | `explain_recipe` static wall-clock by risk class; no network; gapped recipe does not raise |
| AC6 MCP tools behind --enable-translator | PASS | `register_translator_tools` + `--enable-translator`; `test_create_server_registers_translator_tools_only_when_enabled` |
| AC7 unit tests + suite grows | PASS | new `test_axxon_mcp_translator.py` (38) + server test; full suite 668/668 (was 629) |
| AC8 live: >=3 ephemeral recipes round-trip | PASS | 3 recipes assemble -> validate -> apply -> verify -> rollback -> verify-absent on the stand; raw below |

## Commands

```
$ python3.12 -m unittest discover -s tools/tests
Ran 668 tests, OK

$ python3.12 -m unittest tools.tests.test_axxon_mcp_translator
Ran 38 tests, OK
```

## Live verification on the stand (sanitized)

3 reversible recipes, each assemble_recipe -> validate_recipe (valid=true) -> apply (real UID
created) -> verify (present) -> rollback (rolled_back) -> verify (absent):

```
"add a camera for phase7 testing"    -> create_camera        applied -> DeviceIpint.8585 -> rolled_back -> absent
"create a macro for phase7 testing"  -> create_macro         applied -> <macro guid>      -> rolled_back -> absent
"inject an external alarm event"     -> external_event_inject applied (no created uid)    -> rolled_back -> absent
```

Every `post_verify_still_present` is empty (clean rollback). Risk class for all three is
`mutation`; `validation_valid` is `true` and `explain_has_text` is `true` for each.

Raw: `raw/live-verify.json` (host IP and credentials never appear in the output; intrinsic
`hosts/Server/...` UIDs retained per the sanitization policy).

## Key engineering notes

- `validate_recipe`/`explain_recipe` take the steps list (not the recipe envelope);
  `assemble_recipe` returns `{"steps": [...]}` or `{"status": "unsupported_intent", ...}`.
- The translator composes persistent workflows (`create_camera`/`create_macro`) which are
  reversible via `remove_created_uids`; the live driver applies then rolls back explicitly,
  satisfying the reversible-recipe acceptance.
- `assemble_recipe` needs an operator only for `known_workflows()` in the gap path; live and
  unit paths both inject it via `operator_factory`.

## Files changed
- tools/axxon_mcp_translator.py (new)
- tools/axxon_mcp_server.py (register_translator_tools, --enable-translator, wiring)
- tools/tests/test_axxon_mcp_translator.py (new, 38 tests)
- tools/tests/test_axxon_mcp_server.py (translator registration test)
- tools/axxon_mcp_translator_live.py (new, live driver; not a unit test)
