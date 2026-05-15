# MCP Phase 4: Integration And Plugin Generation

**Date:** 2026-05-15
**Status:** Proposed
**Predecessor:** `docs/plans/2026-05-01-axxon-api-gap-coverage.md` (Phases 0-3 and 5 complete; Phase 4 is the only outstanding work in that plan)
**Repo:** https://github.com/jerrygergov/axxon-one-mcp

## Goal

Turn the verified MCP corpus and live-inspection layer into a code generator that emits ready-to-run third-party integrations. The generator must produce Axxon One client code that compiles, runs against a live profile, redacts secrets, and refuses to reference unverified surfaces.

The deliverable is a new MCP tool family (`generate_*`) plus a small library of templates and an output verifier. Generated code targets six concrete integration shapes pulled from the verified evidence under `docs/api-audit/`:

1. Direct gRPC consumer.
2. HTTP `/grpc` consumer.
3. Legacy HTTP consumer (only for surfaces with no gRPC equivalent).
4. Bounded detector-event consumer.
5. External event producer through a real `DetectorEx.*` fixture.
6. Archive export job (gRPC `MMExportAgent` or legacy `/export/`).

Inventory sync and webhook-bridge skeletons are deferred to a follow-up plan because they need more design.

## Non-goals

- No new live API surfaces. Phase 4 only repackages what is already verified in the matrix.
- No fixture-blocked integrations (PTZ, Client HTTP, Tag&Track, control panels, water level, TFA, WebSocket `/events`).
- No mutation outside the existing operator workflows. Generated code can plan, but apply still routes through Phase 3.
- No new runtime dependencies in the MCP server itself; templates may use `requests`/`grpcio` but the generator is pure stdlib.

## Inputs we already have

- `docs/api-audit/mcp-corpus/api_methods.json` (361 gRPC methods, safety class, streaming mode).
- `docs/api-audit/mcp-corpus/http_endpoints.json` (221 endpoints, auth mode, verified status).
- `docs/api-audit/mcp-corpus/task_recipes.json` (13 task recipes).
- `docs/api-audit/mcp-corpus/fixtures.json` (6 fixture-needed rows + known demo fixtures).
- `docs/api-audit/mcp-corpus/safety_policies.json` (redaction, caps, approval rules).
- `docs/api-audit/mcp-corpus/known_behaviors.json` (false paths, demo-stand quirks).
- `tools/axxon_api_client.py` is the reference transport; generated code copies its auth and import pattern, not the file itself.

## Architecture

```
tools/
  axxon_mcp_generator.py        new   pure generator (templates + corpus -> code)
  templates/                    new
    grpc_consumer.py.j2
    http_grpc_consumer.py.j2
    legacy_http_consumer.py.j2
    event_consumer.py.j2
    external_event_producer.py.j2
    export_job.py.j2
    README.md.j2
    requirements.txt.j2
  tests/
    test_axxon_mcp_generator.py new   unit tests for each template + verifier

docs/
  api-audit/
    mcp-generation-smoke-latest.md  new   evidence file for a full live run
```

`axxon_mcp_generator.py` exposes a single `Generator` class with one method per integration shape. Each method takes a typed `GenerationRequest` dataclass and returns a `GeneratedBundle` (file path -> content string). The generator does not write to disk; the MCP tool wrapper does, into an explicit output directory chosen by the caller.

The MCP server gains four new tools, all docs-mode safe:

- `list_integration_templates()` -> names, summaries, required fixtures, required env vars.
- `plan_integration(template, params)` -> dry-run that returns the file tree, required fixtures, required env vars, refusal reasons (if any). No disk write.
- `generate_integration(template, params, output_dir)` -> writes the bundle. Refuses if `output_dir` is inside the repo and a `--allow-in-repo` flag is not set in the request, to keep generated junk out of git.
- `verify_integration(output_dir)` -> runs the verifier (see below) on a previously generated bundle.

## Template contract

Every template emits a self-contained Python module plus a minimal `README.md` and `requirements.txt`. Every template must:

- Read credentials only from environment variables (`AXXON_HOST`, `AXXON_HTTP_URL`, `AXXON_TLS_CN`, `AXXON_USERNAME`, `AXXON_PASSWORD`). Never embed.
- Print a startup banner that lists the env vars in use with values redacted.
- Apply byte/time caps for any stream (default: 30 s, 500 events, 1 MiB per HTTP body, matching `safety_policies.json`).
- Use `AuthenticateEx2` for direct gRPC, Bearer from `/grpc` for legacy HTTP, and the documented `Authorization: Bearer` shape for `/v1`.
- Refuse to start if the corpus marks the requested surface as `fixture-needed` and the fixture is not discoverable through `discover_fixtures()` at runtime.
- Redact tokens, passwords, full license keys, full plate values, and raw images from any log output.
- Exit non-zero on any verification failure rather than continuing.

Templates pull method/endpoint metadata at generation time, not at runtime. The generated file therefore has no dependency on the MCP corpus; it can be copied to a third-party machine and run standalone.

## Per-template scope

### 1. Direct gRPC consumer

- Inputs: gRPC FQMN (e.g. `axxon.bl.config.ConfigurationService.ListUnits`), optional request fields.
- Output: a script that authenticates with `AuthenticateEx2`, imports the proto module, calls the method once, prints the response with redaction, exits.
- Refusal: corpus `safety_class != safe-read` unless `--allow-mutation` is passed and the FQMN matches a verified mutation in `task_recipes.json`.

### 2. HTTP `/grpc` consumer

- Inputs: gRPC FQMN plus optional body JSON.
- Output: a `requests`-based script that POSTs to `/grpc/<service>/<method>` with Bearer auth, prints the JSON response with redaction.
- Refusal: same as above.

### 3. Legacy HTTP consumer

- Inputs: a legacy HTTP path from `http_endpoints.json` with `family=legacy`.
- Output: a `requests` script that calls the endpoint with the verified auth mode (Bearer by default on this stand, Basic when the endpoint requires it).
- Refusal: endpoint not in catalog, or marked `not-verified`.

### 4. Bounded detector-event consumer

- Inputs: target subject (camera AP or detector AP), optional event-type filter, optional duration (default 30 s), optional count cap (default 500).
- Output: script wraps `DomainNotifier.PullEvents` with the documented `SearchFilterArray` shape, exits when either cap is reached. Includes the AppDataDetector preference from `known_behaviors.json` (semantic analytics live on child AppDataDetector subjects, not the parent AVDetector).
- Refusal: subject not found by a runtime `ListUnits` lookup.

### 5. External event producer

- Inputs: `DetectorEx.*` access point, event type (`Event1`, `Event2`, or `TargetList`), optional payload.
- Output: script calls `/v1/detectors/external:raiseOccasionalEvent` for single events or `:raisePeriodicalEvent` for `TargetList`, then optionally subscribes to event history to confirm.
- Refusal: target AP does not resolve at runtime, or `detector != ExternalDetector`. This is the only template that needs a pre-existing fixture; the corpus already records that public `ChangeConfig` cannot create one.

### 6. Archive export job

- Inputs: camera AP, time range (bounded to <=1 h by default), format (`mp4` or `jpeg`), download path.
- Output: script that starts an export session, polls until `S_COMPLETED` or timeout, downloads with byte caps, destroys the session. Cleanup runs in a `finally` block so a Ctrl-C never leaves a live session.
- Refusal: requested range exceeds the cap unless `--allow-large` is set; or no `MMExportAgent.*` discovered at runtime.

## Verifier

A second module, `axxon_mcp_generation_verifier.py`, runs static checks on a generated bundle without executing it:

- Required files present (`main.py`, `README.md`, `requirements.txt`).
- No literal IP, password, bearer, or license key (regex sweep matching the audit's secret-scan rule).
- `python -m py_compile` on every `.py` file.
- `ast.parse` confirms the script reads credentials only from `os.environ`.
- The script imports nothing outside an allowed list (`grpc`, `requests`, `os`, `sys`, `json`, `time`, `logging`, `argparse`, `dataclasses`, `axxonsoft.*`).
- Byte/time cap constants exist and are <= the policy limits.

Verifier exit code drives `verify_integration()`.

## MCP server wiring

`axxon_mcp_server.py` gains an optional `--enable-generator` flag. When enabled:

- `list_integration_templates` and `plan_integration` are always exposed.
- `generate_integration` is exposed but refuses to write inside the repo unless `AXXON_GENERATOR_ALLOW_IN_REPO=1`.
- `verify_integration` is always exposed.

Docs-only mode (no `--enable-live`) can still call `plan_integration` because the generator runs against the corpus, not the live stand. `generate_integration` does not need live access either; only the *generated script* does.

## Tests (TDD order)

1. `test_generator_lists_templates` — names, summaries, required fixtures match expectations.
2. `test_plan_grpc_consumer_safe_read` — plan for a `safe-read` method returns no refusal.
3. `test_plan_grpc_consumer_refuses_mutation` — plan for a `mutation` method without `--allow-mutation` refuses with a typed reason referencing the safety class.
4. `test_plan_legacy_http_refuses_unverified` — unknown legacy path refuses.
5. `test_generate_event_consumer_emits_caps` — generated file contains the documented duration and count caps as integer literals.
6. `test_generate_event_consumer_prefers_appdata` — when the subject is a parent AVDetector, the script logs the AppDataDetector recommendation from `known_behaviors.json`.
7. `test_generate_external_event_producer_requires_detectorex` — script's startup check looks up the AP via `ListUnits` and aborts if not `ExternalDetector`.
8. `test_generate_export_job_cleanup_in_finally` — AST inspection of generated source confirms `DestroySession` lives in a `finally` block.
9. `test_verifier_rejects_embedded_secrets` — verifier flags a file with a literal password/bearer/IP.
10. `test_verifier_rejects_disallowed_import` — verifier flags a file that imports `subprocess` or `socket` directly.
11. `test_verifier_accepts_clean_bundle` — round-trip: generate, then verify, with no errors.
12. `test_generate_refuses_in_repo_without_flag` — `generate_integration` refuses an `output_dir` inside the repo unless allow-flag is set.
13. `test_mcp_server_exposes_generator_only_when_enabled` — server without `--enable-generator` does not expose generator tools.

Target: tests 1-13 raise total test count from 159 to 172. All must pass before any live smoke.

## Live smoke

After unit tests are green, run a single end-to-end smoke on the demo stand. The smoke is read-only from the MCP server side; the generated scripts execute against the live profile with full caps.

1. Generate a gRPC consumer for `ConfigurationService.ListUnits` -> run -> expect non-empty unit list, no secrets in log.
2. Generate an HTTP `/grpc` consumer for the same -> run -> compare counts match the gRPC run.
3. Generate a legacy HTTP consumer for `/product/version` -> run -> verify body shape.
4. Generate a bounded event consumer for `hosts/Server/AppDataDetector.27/EventSupplier` -> run with `--duration 10 --count 20` -> expect <=20 events, exit on cap.
5. Generate an external event producer for `hosts/Server/DetectorEx.1/EventSupplier` with `Event1` -> run -> verify history match.
6. Generate an export job for camera 1 with a 5-minute window, JPEG output -> run -> verify file exists, byte cap respected, session destroyed.

Evidence file: `docs/api-audit/mcp-generation-smoke-latest.md`. Sanitization rules match the rest of the audit (host -> `<demo-host>`, TLS CN -> `<your-tls-cn>`).

## Execution order

1. Land scaffolding: `axxon_mcp_generator.py` skeleton, `templates/` directory, `tests/test_axxon_mcp_generator.py` with all 13 tests written and failing.
2. Implement templates 1-3 (gRPC, HTTP `/grpc`, legacy HTTP) and the verifier. Tests 1-5, 9-13 green.
3. Implement templates 4 and 5 (event consumer, external event producer). Tests 6, 7 green.
4. Implement template 6 (export job). Test 8 green.
5. Wire `--enable-generator` into `axxon_mcp_server.py`. Confirm `test_mcp_server_exposes_generator_only_when_enabled` green.
6. Run unit tests: 172/172.
7. Run live smoke (6 steps above), save evidence, sanitize.
8. Update `README.md` in the repo: new tool count (19 live tools, 11 operator workflows, 6 generator templates), Phase 4 status.
9. Update `docs/plans/2026-05-01-axxon-api-gap-coverage.md` MCP Phase 4 section to point at this plan and the smoke evidence.
10. Commit and push.

## Stop conditions

Pause before:

- Running a generated script against any target other than the agreed demo stand.
- Adding any template that maps to a `fixture-needed` matrix row.
- Adding any template that emits mutation code outside the existing operator workflows.
- Generating into a path that exists and is non-empty.

## Acceptance criteria

- 172/172 unit tests pass.
- Six templates generate bundles that the verifier accepts.
- Live smoke evidence file exists and is sanitized.
- The MCP server exposes generator tools only behind `--enable-generator`.
- Generated bundles run successfully end-to-end against the demo stand for the six smoke cases.
- `docs/plans/2026-05-01-axxon-api-gap-coverage.md` MCP Phase 4 entry is updated to "done" with a link to the smoke evidence.
