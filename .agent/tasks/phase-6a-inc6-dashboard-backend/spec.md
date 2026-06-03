# Task Spec: phase-6a-inc6-dashboard-backend

## Metadata
- Task ID: phase-6a-inc6-dashboard-backend
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A section)
- tools/axxon_mcp_generator.py (existing generator, 11 templates)
- tools/templates/inventory_sync.py.tmpl (closest sibling: read-only aggregation to a file)
- tools/templates/scheduled_exporter.py.tmpl (bounded loop pattern)

## Original task statement

Phase 6A increment 6 (fourth new template kind): add the `dashboard_backend` template in both
Python and Node. It is a read-only aggregation: it collects a dashboard snapshot from three
read-safe sources and writes a single JSON file to OUTPUT_PATH, enforcing a BYTE_CAP on the
serialised output. No mutation gate is required.

Corpus methods used (all read/review, read-safe):
- `axxonsoft.bl.domain.DomainService.ListCameras` (read, server stream)
- `axxonsoft.bl.logic.LogicService.GetActiveAlerts` (review, unary)
- `axxonsoft.bl.events.EventHistoryService.ReadEvents` (read, server stream)

## Acceptance criteria

- AC1: `dashboard_backend` is in `TEMPLATE_CATALOG` with `languages=["python","node"]`,
  `required_params=["output_path"]`, host/TLS/user/password `required_env`, and a summary
  mentioning the read-only dashboard snapshot.
- AC2: `Generator.generate(template="dashboard_backend", language="python")` returns a
  `GeneratedBundle` with `main.py`, `README.md`, `requirements.txt`. No mutation gate.
- AC3: The generated `main.py` bakes `OUTPUT_PATH` and `BYTE_CAP` from `request.params`
  (BYTE_CAP defaults to the module export byte cap).
- AC4: The generated `main.py` reads credentials from `os.environ`, never embeds them, writes
  to OUTPUT_PATH, and references all three sources: `ListCameras`, `GetActiveAlerts`,
  `ReadEvents`.
- AC5: `language="node"` returns a `GeneratedBundle` with `src/index.ts`, `README.md`,
  `package.json`; `src/index.ts` bakes the same constants, reads `process.env`, writes
  OUTPUT_PATH, and references the same three sources.
- AC6: `Verifier.verify_bundle` passes on both generated bundles.
- AC7: `list_templates()` includes `dashboard_backend` with its `languages` field.
- AC8: All pre-existing unit tests still pass (count grows from 588).

## Constraints

- No defensive try/except beyond the existing bounded-stream `grpc.RpcError` pattern.
- Reuse `_render`, `_read_template`, `_read_ts_template`, `_read_aux_template`,
  `_ts_package_json`, and the existing `values`/readme/node-branch shape.
- Reuse `DEFAULT_EXPORT_BYTE_CAP`; cap each source collection to keep the snapshot bounded.
- Credentials from env only; no IP/token/password literals (Verifier enforces).
- Match naming patterns; no new module-level imports in the generator.

## Non-goals

- Serving HTTP (the template produces a JSON snapshot file, not a live server).
- The other 2 new template kinds (plugin_scaffold, ptz_controller) — later increments.
- Live smoke against the demo stand (offline code-generation verify only).
- C# support; bundle signing.

## Verification plan

- Build: none (pure Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows.
- Manual: inspect generated `main.py` and `src/index.ts` for OUTPUT_PATH/BYTE_CAP, env usage,
  and references to the three sources.
