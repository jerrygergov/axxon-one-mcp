# Task Spec: phase-6a-inc4-scheduled-exporter

## Metadata
- Task ID: phase-6a-inc4-scheduled-exporter
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A section)
- tools/axxon_mcp_generator.py (existing generator, 9 templates)
- tools/templates/export_job.py.tmpl (closest sibling: ExportService.ListSessions inspector)

## Original task statement

Phase 6A increment 4 (second of the new template kinds): add the `scheduled_exporter`
template in both Python and Node. It wraps the existing `export_job` inspector pattern in a
bounded scheduled loop: every INTERVAL_SECONDS it runs `ExportService.ListSessions` for a
camera, up to MAX_RUNS times, enforcing a per-run BYTE_CAP. Like `export_job`, the call it
makes is read-safe (ListSessions), so no mutation gate is required.

Corpus method used (present in api_methods.json, read-safe):
- `axxonsoft.bl.mmexport.ExportService.ListSessions` (via ExportService_pb2 / ExportService_pb2_grpc)

## Acceptance criteria

- AC1: `scheduled_exporter` appears in `TEMPLATE_CATALOG` with `languages=["python","node"]`,
  `required_params=["camera_ap"]`, host/TLS/user/password `required_env`, and a summary
  mentioning the bounded scheduled loop.
- AC2: `Generator.generate(template="scheduled_exporter", language="python")` returns a
  `GeneratedBundle` with `main.py`, `README.md`, `requirements.txt`. No mutation gate.
- AC3: The generated `main.py` bakes `INTERVAL_SECONDS`, `MAX_RUNS`, `BYTE_CAP`, and
  `CAMERA_AP` from `request.params`, defaulting to module defaults.
- AC4: Generation refuses with `cap_exceeded` when `interval` < a sane floor or `max_runs`
  exceeds the cap (interval >= MIN_INTERVAL_SECONDS, max_runs <= MAX_SCHEDULED_RUNS).
- AC5: The generated `main.py` reads credentials from `os.environ`, never embeds them, and
  references `ListSessions`.
- AC6: `language="node"` returns a `GeneratedBundle` with `src/index.ts`, `README.md`,
  `package.json`; `src/index.ts` bakes the same constants, reads `process.env`, and
  references `ListSessions`.
- AC7: `Verifier.verify_bundle` passes on both generated bundles.
- AC8: `list_templates()` includes `scheduled_exporter` with its `languages` field.
- AC9: All pre-existing unit tests still pass (count grows from 568).

## Constraints

- No defensive try/except beyond the existing bounded-stream pattern.
- Reuse `_render`, `_read_template`, `_read_ts_template`, `_read_aux_template`,
  `_ts_package_json`, and the existing `values`/readme/node-branch shape.
- Add module constants `MIN_INTERVAL_SECONDS` and `MAX_SCHEDULED_RUNS` next to the existing
  DEFAULT_* constants; reuse `DEFAULT_EXPORT_BYTE_CAP`.
- Credentials from env only; no IP/token/password literals (Verifier enforces).
- Match naming patterns; no new module-level imports in the generator.

## Non-goals

- Actually starting/destroying exports (the real export lifecycle stays operator-owned).
- The other 4 new template kinds — later increments.
- Live smoke against the demo stand (offline code-generation verify only).
- C# support; bundle signing.

## Verification plan

- Build: none (pure Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows.
- Manual: inspect generated `main.py` and `src/index.ts` for the four baked constants,
  env usage, and the `ListSessions` reference; confirm `cap_exceeded` refusals.
