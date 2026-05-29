# Task Spec: phase-6a-authoring-kit

## Metadata
- Task ID: phase-6a-authoring-kit
- Created: 2026-05-29T14:49:56+00:00
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6A section)
- tools/axxon_mcp_generator.py (existing generator)
- tools/tests/test_axxon_mcp_generator.py (existing tests)

## Original task statement

Phase 6A first increment: introduce a language-agnostic renderer seam + Node/TypeScript support
for the `event_consumer` template, with the static Verifier extended to cover TypeScript.

## Acceptance criteria

- AC1: `GenerationRequest` accepts a `language` field; defaults to `"python"`.
- AC2: `Generator.generate()` with `template="event_consumer"` and `language="node"` returns a
  `GeneratedBundle` whose `files` contains `src/index.ts`, `README.md`, `package.json`.
- AC3: The generated `src/index.ts` contains `DURATION_SECONDS` and `COUNT_CAP` constants baked in
  from `request.params`.
- AC4: The generated `src/index.ts` reads credentials from `process.env`, never embeds them.
- AC5: `Verifier.verify_bundle` passes a clean TS bundle (files with `.ts` extension).
- AC6: `Verifier.verify_bundle` rejects a TS bundle with an embedded secret.
- AC7: `Verifier.verify_bundle` rejects a TS bundle that imports `child_process`.
- AC8: `Generator.generate()` with `language="node"` for a template that has no TS renderer returns
  a `GenerationRefusal` with `reason="unsupported_language"`.
- AC9: All 505 pre-existing unit tests still pass after the changes.
- AC10: `list_templates()` returns a `languages` field for `event_consumer` containing both
  `"python"` and `"node"`.

## Constraints

- No defensive try/except unless protecting a user-facing safety guarantee.
- Reuse `_render()` and `string.Template` for TS templates (same substitution mechanism).
- Minimal diffs: existing Python paths unchanged, existing tests unchanged.
- Match existing naming patterns (`_scan_python` → `_scan_typescript`).
- Credentials must come from `process.env` in generated TS code.

## Non-goals

- C# support (later increment).
- New template kinds (`alarm_responder`, `ptz_controller`, etc.) — later increments.
- TS variants of any template other than `event_consumer` — later increments.
- Bundle signing — later increment.
- Live smoke against the demo stand (offline code-generation verify only).

## Verification plan

- Build: no build step (Python generator).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` must show green with count > 505.
- Lint: Python static analysis via `_scan_python` on the generator itself (no new imports).
- Manual checks: inspect generated `src/index.ts` for cap constants and `process.env` usage.
