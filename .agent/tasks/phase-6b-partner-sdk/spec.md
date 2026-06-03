# Task Spec: phase-6b-partner-sdk

## Metadata
- Task ID: phase-6b-partner-sdk
- Created: 2026-06-03
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Guidance sources
- STATUS.md
- docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md (Phase 6B section, lines ~367-380)
- tools/axxon_mcp_generator.py (Generator, Verifier, plugin_scaffold template)
- tools/axxon_mcp_server.py (register_generator_tools / register_operator_tools patterns)

## Original task statement

Phase 6B: Partner SDK kit. Add a `PartnerKit` (new module `tools/axxon_mcp_partner.py`) with
three capabilities, and register them as MCP tools in `axxon_mcp_server.py`:
- `scaffold_plugin(name, language, output_dir)` — emit a complete runnable plugin repo. Reuses
  the generator's `plugin_scaffold` template (py+node).
- `plugin_lint(path)` — run the existing static Verifier on the repo plus repo-level checks:
  no committed secrets, `.env.example` present, a test file present, README has a "Safety"
  section. Returns a structured pass/fail with the list of findings.
- `plugin_package(path, fmt)` — produce a distributable archive (`zip` or `tar.gz`) plus a
  manifest with the capability/file list and a SHA-256 of every file. Refuses to package a
  repo that does not lint clean.

## Acceptance criteria

- AC1: `PartnerKit.scaffold_plugin(name, language)` returns a dict of files for `language` in
  {python, node}; the file set matches the generator's `plugin_scaffold` output and contains
  a README with a "Safety" section and an `.env.example`.
- AC2: `PartnerKit.scaffold_plugin` with an unsupported language returns a refusal
  (`status="refused"`, reason mentions language).
- AC3: `PartnerKit.plugin_lint(path)` returns `{"ok": True, "findings": []}` for a freshly
  scaffolded clean repo (python and node).
- AC4: `plugin_lint` flags a repo with a committed secret (e.g. a password literal or a JWT)
  with an `embedded_secret` finding and `ok=False`.
- AC5: `plugin_lint` flags a repo missing `.env.example`, missing a test file, or whose README
  lacks a "Safety" section, each with a distinct finding code, `ok=False`.
- AC6: `PartnerKit.plugin_package(path, fmt)` for a clean repo writes an archive in the chosen
  format and returns a manifest dict with `name`, `format`, `file_count`, and a `files` map of
  relative path -> sha256; the archive exists on disk and contains every repo file.
- AC7: `plugin_package` refuses (`status="refused"`) when the repo does not lint clean.
- AC8: `plugin_package` supports both `zip` and `tar.gz`; an unsupported format is refused.
- AC9: The three capabilities are registered as MCP tools in `register_partner_tools` and the
  server wiring exposes them behind a `--enable-partner` flag (mirroring `--enable-generator`).
- AC10: All pre-existing unit tests still pass (count grows from 604).

## Constraints

- Reuse `Generator` (for plugin_scaffold) and `Verifier.verify_bundle` (for code-file lint);
  do not duplicate scanning logic. Repo-level checks (env example, test present, README safety)
  are new and live in `PartnerKit`.
- No new third-party deps: use stdlib `zipfile`, `tarfile`, `hashlib`, `pathlib`.
- No defensive try/except beyond what protects a user-facing guarantee.
- `plugin_package` must write only to the chosen output path; never inside the repo unless the
  caller's path is outside the repo (reuse the generator's in-repo-write guard for the MCP tool).
- Sanitize any committed evidence; no secrets/proto/CA committed.
- Match existing naming/registration patterns.

## Non-goals

- Hosting / a plugin registry (explicitly out of scope per roadmap).
- C# scaffolds.
- Live stand calls from the kit itself (the scaffolded plugin connects live; the kit is offline).

## Verification plan

- Build: none (pure Python).
- Unit tests: `python3.12 -m unittest discover -s tools/tests` green, count grows. New test
  module `tools/tests/test_axxon_mcp_partner.py` covering AC1-AC8.
- Manual: scaffold a python plugin to a temp dir, lint it (clean), package it (zip + tar.gz),
  verify the archive contents and the sha256 manifest; corrupt a file and confirm lint flags it.
- Live: scaffold + run the plugin entrypoint against the demo stand (lists cameras), reusing
  the increment-7 live path.
