# Task Spec: phase-6a-inc5-ml-detector-bridge

## Metadata
- Task ID: phase-6a-inc5-ml-detector-bridge
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A section)
- tools/axxon_mcp_generator.py (existing generator, 10 templates)
- tools/templates/alarm_responder.py.tmpl (closest sibling: direct-gRPC, mutation-gated)
- tools/templates/external_event_producer.py.tmpl (existing event raiser, HTTP)

## Original task statement

Phase 6A increment 5 (third new template kind): add the `ml_detector_bridge` template in both
Python and Node. It bridges external ML inference results into Axxon: it reads a bounded batch
of inference results from a local JSON file (RESULTS_PATH), and for each result raises an
external detector event via `ExternalDetectorService.RaiseOccasionalEvent` (direct gRPC).
Raising events is mutating, so generation refuses without `allow_mutation=True`. The batch is
bounded by COUNT_CAP and a DURATION_SECONDS deadline.

Corpus method used (present in api_methods.json, mutating):
- `axxonsoft.bl.detectors.ExternalDetectorService.RaiseOccasionalEvent`
  (via ExternalDetectorService_pb2 / ExternalDetectorService_pb2_grpc)

## Acceptance criteria

- AC1: `ml_detector_bridge` is in `TEMPLATE_CATALOG` with `languages=["python","node"]`,
  `required_params=["access_point","results_path"]`, host/TLS/user/password `required_env`,
  and a summary mentioning bridging ML results to external detector events.
- AC2: `Generator.generate(template="ml_detector_bridge", language="python", allow_mutation=True)`
  returns a `GeneratedBundle` with `main.py`, `README.md`, `requirements.txt`.
- AC3: Without `allow_mutation=True`, generation returns `GenerationRefusal` with
  `reason="refused_mutation"`.
- AC4: The generated `main.py` bakes `ACCESS_POINT`, `RESULTS_PATH`, `COUNT_CAP`, and
  `DURATION_SECONDS` from `request.params`; refuses with `cap_exceeded` when `count` exceeds
  the module event-count cap.
- AC5: The generated `main.py` reads credentials from `os.environ`, never embeds them, reads
  results from RESULTS_PATH, and references `RaiseOccasionalEvent`.
- AC6: `language="node"` returns a `GeneratedBundle` with `src/index.ts`, `README.md`,
  `package.json`; `src/index.ts` bakes the same constants, reads `process.env`, reads
  RESULTS_PATH, and references `RaiseOccasionalEvent`.
- AC7: `Verifier.verify_bundle` passes on both generated bundles.
- AC8: `list_templates()` includes `ml_detector_bridge` with its `languages` field.
- AC9: All pre-existing unit tests still pass (count grows from 578).

## Constraints

- No defensive try/except beyond the existing bounded-loop `grpc.RpcError` pattern.
- Reuse `_render`, `_read_template`, `_read_ts_template`, `_read_aux_template`,
  `_ts_package_json`, and the existing `values`/readme/node-branch shape.
- Mutation gate reuses the existing `allow_mutation` refusal pattern.
- Credentials from env only; no IP/token/password literals (Verifier enforces).
- Match naming patterns; no new module-level imports in the generator.

## Non-goals

- Running ML inference itself (the bridge consumes already-produced results).
- The other 3 new template kinds — later increments.
- Live smoke against the demo stand (offline code-generation verify only; the mutating raise
  is not exercised live in this increment).
- C# support; bundle signing.

## Verification plan

- Build: none (pure Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows.
- Manual: inspect generated `main.py` and `src/index.ts` for baked constants, env usage,
  RESULTS_PATH read, the `RaiseOccasionalEvent` reference; confirm refusal without allow_mutation
  and cap_exceeded.
