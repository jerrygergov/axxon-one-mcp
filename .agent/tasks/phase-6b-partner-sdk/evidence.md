# Evidence: phase-6b-partner-sdk

## Summary
Phase 6B Partner SDK kit shipped. New module `tools/axxon_mcp_partner.py` with a `PartnerKit`
class exposing three offline capabilities, registered as MCP tools behind `--enable-partner`:
- `scaffold_plugin(name, language)` — reuses the generator's `plugin_scaffold` template (py+node).
- `plugin_lint(path)` — static Verifier (secrets/imports) plus repo-level checks
  (`.env.example` present, a test file present, README has a "Safety" section).
- `plugin_package(path, fmt, output)` — zip or tar.gz archive plus a SHA-256 manifest; refuses
  to package a repo that does not lint clean.

End-to-end acceptance (roadmap): scaffold -> lint -> package -> a runnable plugin that connects
to the demo stand and lists cameras. Verified live below.

## Acceptance criteria

| AC | Status | Evidence |
|----|--------|----------|
| AC1 scaffold py/node file set + README safety + env example | PASS | `test_scaffold_python`, `test_scaffold_node`; manual 7 files |
| AC2 unsupported language refused | PASS | `test_scaffold_bad_language` |
| AC3 lint clean for fresh py + node repos | PASS | `test_lint_clean_python`, `test_lint_clean_node`; manual ok=True |
| AC4 lint flags committed secret (embedded_secret) | PASS | `test_lint_flags_secret` |
| AC5 lint flags missing env_example / test / safety | PASS | `test_lint_flags_missing_*` (3 tests) |
| AC6 package writes archive + sha256 manifest of every file | PASS | `test_package_zip`; manifest file_count==len(files), 64-char digests |
| AC7 package refuses a dirty (non-clean) repo | PASS | `test_package_refuses_dirty_repo`; manual dirty -> refused/lint_failed |
| AC8 zip + tar.gz supported; bad format refused | PASS | `test_package_targz`, `test_package_bad_format` |
| AC9 MCP tools registered behind --enable-partner | PASS | `test_create_server_registers_partner_tools_only_when_enabled` |
| AC10 pre-existing tests pass, count grows | PASS | full suite 618/618 (was 604) |

## Commands run

```
$ python3.12 -m unittest tools.tests.test_axxon_mcp_partner
Ran 13 tests in 0.107s
OK

$ python3.12 -m unittest discover -s tools/tests
Ran 618 tests in 0.676s
OK
```

## Manual end-to-end flow

```
scaffold: ok files: 7
lint clean: True scanned: 7
package zip: ok files: 7
package tgz: ok files: 7
dirty package: refused lint_failed
-rw-r--r--  acme.tar.gz (3107 bytes)
-rw-r--r--  acme.zip (3758 bytes)
```

## Live verification on the stand (sanitized)

Scaffolded a clean python plugin via the kit and ran its entrypoint against <demo-host>:20109
(CN=Server):

```
$ python3.12 main.py
INFO plugin=acme-bridge user=<demo-user> password=<redacted> host=<demo-host>:20109
{"plugin": "acme-bridge", "cameras": 37}
```

This satisfies the roadmap acceptance: scaffold_plugin -> plugin_lint -> plugin_package ends
with a runnable plugin that connects to the stand and lists cameras.

## Files changed
- tools/axxon_mcp_partner.py (new; PartnerKit)
- tools/axxon_mcp_server.py (register_partner_tools, --enable-partner flag, wiring)
- tools/tests/test_axxon_mcp_partner.py (new, 13 tests)
- tools/tests/test_axxon_mcp_server.py (partner registration test)

## Notes
- No new third-party deps: zipfile/tarfile/hashlib/pathlib only.
- The kit is fully offline; only the scaffolded plugin connects to a server.
- Hosting / registry is explicitly out of scope per the roadmap.
