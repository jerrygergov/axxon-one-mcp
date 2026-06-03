# Task Spec: phase-6a-inc7-plugin-scaffold

## Metadata
- Task ID: phase-6a-inc7-plugin-scaffold
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A, line ~356: plugin_scaffold = full runnable repo with auth, retry, telemetry, tests, CI)
- tools/axxon_mcp_generator.py (existing generator, 12 templates)
- tools/templates/grpc_consumer.py.tmpl (auth + direct gRPC pattern to embed)

## Original task statement

Phase 6A increment 7 (fifth new template kind, last buildable one this phase): add the
`plugin_scaffold` template in both Python and Node. Unlike the consumer templates (which emit
a single entrypoint), this emits a complete runnable repo skeleton: an entrypoint that
authenticates and lists cameras, an env-only credential loader, a retry helper, a smoke test,
a CI workflow, a README with a safety section, a LICENSE placeholder, and an env example.
The scaffold performs only a read (ListCameras), so no mutation gate is required.

## Acceptance criteria

- AC1: `plugin_scaffold` is in `TEMPLATE_CATALOG` with `languages=["python","node"]`,
  `required_params=["name"]`, host/TLS/user/password `required_env`, and a summary mentioning
  the runnable plugin repo skeleton.
- AC2: `Generator.generate(template="plugin_scaffold", language="python")` returns a
  `GeneratedBundle` whose `files` includes a Python entrypoint, `README.md`,
  `requirements.txt`, `.env.example`, a test file, a CI workflow, and a `LICENSE`.
- AC3: The generated entrypoint bakes the plugin `NAME` from params, reads credentials from
  `os.environ`, references `ListCameras`, and includes a bounded retry helper.
- AC4: The generated README contains a "Safety" section and references env-only credentials;
  `.env.example` lists the required env names with no real values.
- AC5: No secret literals anywhere in the bundle (Verifier passes); the test file and CI
  workflow are present.
- AC6: `language="node"` returns a `GeneratedBundle` with a TS entrypoint (`src/index.ts`),
  `package.json`, `README.md`, `.env.example`, a test file, a CI workflow, and `LICENSE`;
  `src/index.ts` reads `process.env`, references `ListCameras`, includes a retry helper.
- AC7: `Verifier.verify_bundle` passes on both generated bundles.
- AC8: `list_templates()` includes `plugin_scaffold` with its `languages` field.
- AC9: All pre-existing unit tests still pass (count grows from 596).

## Constraints

- No defensive try/except beyond the bounded retry helper and the existing stream guard.
- Reuse `_render`, `_read_template`, `_read_ts_template`, `_read_aux_template`,
  `_ts_package_json`, and the existing `values`/readme/node-branch shape; extend with the
  extra scaffold files inline in the build method.
- The Verifier must accept the new file types it scans (.py, .ts); non-code files
  (.env.example, .yml, LICENSE) must not break verification.
- Credentials from env only; no IP/token/password literals.
- Match naming patterns; no new module-level imports in the generator.

## Non-goals

- The 6B partner-SDK tools (`scaffold_plugin`/`plugin_lint`/`plugin_package`) — Phase 6B.
- `ptz_controller` (needs a live PTZ fixture) — deferred.
- C# support; bundle signing.

## Verification plan

- Build: none (pure Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows.
- Manual: inspect the generated file set, the entrypoint (NAME, env, ListCameras, retry),
  README safety section, .env.example.
- Live: generate the Python scaffold entrypoint and run it against the demo stand; it must
  authenticate and list cameras.
