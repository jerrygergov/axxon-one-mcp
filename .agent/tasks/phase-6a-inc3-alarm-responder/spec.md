# Task Spec: phase-6a-inc3-alarm-responder

## Metadata
- Task ID: phase-6a-inc3-alarm-responder
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A section)
- tools/axxon_mcp_generator.py (existing generator, 8 templates)
- tools/templates/event_consumer.py.tmpl (closest sibling: bounded consumer)
- tools/tests/test_axxon_mcp_generator_6a.py, test_axxon_mcp_generator_6a_inc2.py

## Original task statement

Phase 6A increment 3 (first of the 6 new template kinds): add the `alarm_responder`
template in both Python and Node. It mirrors `event_consumer` (bounded read loop) but
adds an alert-review lifecycle: read active alerts, then for each alert run
`BeginAlertReview` -> `CompleteAlertReview` (both mutating). Because the lifecycle calls
are mutating, the template must require `allow_mutation=True`; without it, generation
refuses with `refused_mutation`.

Corpus methods used (all present in api_methods.json):
- `axxonsoft.bl.logic.LogicService.GetActiveAlerts` (review)
- `axxonsoft.bl.logic.LogicService.BeginAlertReview` (mutating)
- `axxonsoft.bl.logic.LogicService.CompleteAlertReview` (mutating)
- `axxonsoft.bl.logic.LogicService.CancelAlertReview` (mutating, rollback path)

## Acceptance criteria

- AC1: `alarm_responder` appears in `TEMPLATE_CATALOG` with `languages=["python","node"]`,
  `required_params=["operator"]`, `required_env` covering host/TLS/user/password, and a
  summary mentioning the alert-review lifecycle.
- AC2: `Generator.generate(template="alarm_responder", language="python", allow_mutation=True)`
  returns a `GeneratedBundle` with `main.py`, `README.md`, `requirements.txt`.
- AC3: Without `allow_mutation=True`, generation returns `GenerationRefusal` with
  `reason="refused_mutation"`.
- AC4: The generated `main.py` bakes in `DURATION_SECONDS`, `COUNT_CAP`, and `OPERATOR`
  constants from `request.params`; caps default to existing module defaults and refuse
  with `cap_exceeded` when params exceed them.
- AC5: The generated `main.py` reads credentials from `os.environ`, never embeds them, and
  references `GetActiveAlerts`, `BeginAlertReview`, `CompleteAlertReview`.
- AC6: `language="node"` returns a `GeneratedBundle` with `src/index.ts`, `README.md`,
  `package.json`; `src/index.ts` bakes `DURATION_SECONDS`/`COUNT_CAP`, reads `process.env`,
  and references the same three lifecycle methods.
- AC7: The static `Verifier.verify_bundle` passes on both generated bundles.
- AC8: `list_templates()` includes `alarm_responder` with its `languages` field.
- AC9: All pre-existing unit tests still pass (count stays >= 558, grows with new tests).

## Constraints

- No defensive try/except beyond the existing bounded-stream `grpc.RpcError` pattern.
- Reuse `_render`, `_read_template`, `_read_ts_template`, `_read_aux_template`,
  `_ts_package_json`, and the existing `values`/readme/node-branch shape in `_build_*`.
- Mutation gate reuses the existing `allow_mutation` refusal pattern from `_build_grpc_consumer`.
- Match naming patterns; no new module-level imports in the generator.
- Credentials from env only; no IP/token/password literals (Verifier enforces).

## Non-goals

- The other 5 new template kinds (scheduled_exporter, ml_detector_bridge, dashboard_backend,
  plugin_scaffold, ptz_controller) — later increments.
- Live smoke against the demo stand (offline code-generation verify only; mutating lifecycle
  is not exercised live in this increment).
- C# support; bundle signing.

## Verification plan

- Build: none (pure Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows.
- Manual: inspect generated `main.py` and `src/index.ts` for cap constants, env usage, and
  the three lifecycle method references; confirm refusal without `allow_mutation`.
