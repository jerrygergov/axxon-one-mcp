# Phase 2: First-Class Export Group

## Original Task Statement

"Phase 2: First-Class Export Group. Export is currently covered mostly by templates/smokes, not a dedicated MCP intent group. Add export_* tools for plan/start/status/download/stop/destroy with byte/path caps and cleanup. Read docs/ALL_IN_ONE_VMS_API_ROADMAP.md, README.md, docs/COVERAGE.md, and relevant tools/tests. Freeze spec first. Then execute with subagent-driven development. Use TDD. Create evidence.md/evidence.json/raw artifacts. Run python3.12 -m unittest discover -s tools/tests. Fresh verifier must PASS. Commit and push to main."

## Scope

Add a first-class `export` MCP capability group backed by gRPC `ExportService`, using the existing dataclass-with-factories module pattern and the existing server capability wiring. The group must cover snapshot export planning, starting, status, capped download, stop, destroy, and owned-session cleanup.

Implementation likely touches:

- `tools/axxon_mcp_export.py` (new)
- `tools/axxon_mcp_server.py`
- `tools/tests/test_axxon_mcp_export.py` (new)
- `tools/tests/test_axxon_mcp_server.py`
- `README.md`
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md`

`docs/COVERAGE.md` should remain count-stable because `ExportService` is already `6 / 0 / 0 / 6`, unless a small explanatory note is needed. Do not rewrite generator/templates except for unavoidable compatibility with the new group.

## Assumptions

- The initial first-class surface is gRPC `ExportService`; legacy HTTP export smokes remain adjacent regression coverage, not the primary MCP group.
- In-memory ownership tracking is sufficient for this phase. A process restart can lose ownership state, so stop/destroy/cleanup must refuse sessions that are not known-owned in memory or otherwise proven by a strict codex-owned marker.
- Saved downloads use a module-owned export artifact root under the repository, with tests allowed to inject a temp root. Tool inputs may choose a safe filename/stem, but may not provide arbitrary directories or raw output paths.
- Offline unit tests are the required completion bar. A controlled live smoke is optional and may only add WARN evidence when remote fixtures/timeouts are unavailable.

## Constraints

- Use TDD: write failing export/server tests first and preserve red evidence before implementation.
- Use subagent-driven development after this spec is frozen, with evidence ownership kept by one builder and verdict ownership by one fresh verifier.
- Keep task artifacts under `.agent/tasks/phase-2-first-class-export-group/`.
- Do not include live secrets, credentials, CA material, tokens, cookies, raw media bytes, or downloaded export bytes in responses or evidence.
- Mutating/export-byte actions require `AXXON_EXPORT_APPROVE=1` and `confirmation == "CONFIRM-export"`.
- Enforce byte, chunk, file-size, poll/time, and destination/path caps.
- For downloadable sessions, create export options with `store_result_by_export_agent=False`.
- Reject absolute paths, parent traversal, symlink escapes, and any attempt to write outside the allowed export artifact directory.
- Stop, destroy, and cleanup may affect only sessions started/owned by this export tool, or sessions with a strict codex-owned marker accepted by the implementation.

## Non-Goals

- No broad generator/template rewrite.
- No DomainSettingsService export-settings mutation.
- No backup/license/domain/archive-destructive work.
- No arbitrary cleanup of existing user export sessions.
- No raw media/export bytes in MCP responses or evidence.
- No mandatory live stand run.
- No change to the `docs/COVERAGE.md` service/RPC counts unless the API corpus itself changes.

## Acceptance Criteria

AC1. A new `tools/axxon_mcp_export.py` module exists with a dataclass-with-factories implementation consistent with adjacent modules. It exports constants equivalent to `EXPORT_APPROVE_ENV = "AXXON_EXPORT_APPROVE"`, `EXPORT_CONFIRMATION = "CONFIRM-export"`, and `EXPORT_TOOL_NAMES`, and it can be imported without credentials or live network access.

AC2. The export module provides first-class tools named `export_connect_axxon_profile`, `export_plan_snapshot`, `export_start_snapshot`, `export_status`, `export_download`, `export_stop`, `export_destroy`, and `export_cleanup_owned`, or clearly equivalent `export_*` names that cover connect, plan, start, status, download, stop, destroy, and cleanup. `EXPORT_TOOL_NAMES` matches the registered tool names.

AC3. `export_connect_axxon_profile` supports the env profile, constructs the client lazily, returns a sanitized public config summary, reports `mode` and `approval_env`, and does not expose password, token, CA contents, or other secrets.

AC4. `export_plan_snapshot` validates required camera/archive/timestamp inputs, applies maximum file-size and polling/download caps, returns only a sanitized plan/options summary, includes the required confirmation token and approval env var, and does not start a session or download bytes.

AC5. `export_start_snapshot` refuses unless `AXXON_EXPORT_APPROVE=1` and `confirmation == "CONFIRM-export"`. When allowed, it starts a short snapshot export through `ExportService.StartSession`, uses a codex-owned filename/marker, sets `store_result_by_export_agent=False`, records the session as owned in memory, and returns sanitized metadata including session id, caps, and ownership marker without raw media bytes.

AC6. `export_status` reads `ExportService.GetSessionState` for a known owned session and returns normalized state, progress, file metadata, and bounded result metadata only. It must not return raw file contents or secret-like fields.

AC7. `export_download` only downloads files belonging to an owned export session. It enforces max bytes, max chunks, chunk size, and timeout caps; returns metadata such as bytes seen, chunks seen, hash, truncation flag, MIME/type, and optional saved path; and never returns raw export bytes.

AC8. `export_download` saves files only under the module-owned export artifact directory using a sanitized destination name. It rejects absolute paths, parent traversal, path separators in filenames, symlink escapes, and any resolved destination outside the allowed root.

AC9. `export_stop`, `export_destroy`, and `export_cleanup_owned` refuse unless `AXXON_EXPORT_APPROVE=1` and `confirmation == "CONFIRM-export"`. They only operate on owned sessions, are idempotent where practical, and refuse arbitrary session ids rather than calling `StopSession` or `DestroySession` on unknown user sessions.

AC10. Cleanup coverage is complete: started sessions are tracked, destroyed sessions are removed from ownership, failed start/download/stop flows do not leak owned sessions silently, and `export_cleanup_owned` reports attempted, stopped, destroyed, skipped, and failed counts without exposing raw session payloads.

AC11. `tools/axxon_mcp_server.py` wires the export group through `CAPABILITY_GROUPS`, `create_server(export=...)`, `enabled_groups`, `register_export_tools`, `--enable-export`, `APPROVE_ENV_VARS`, default-open behavior, `--enable-all`, and `main()` construction. `list_capabilities` reports `export` disabled with `--enable-export` when absent and enabled when supplied.

AC12. Runtime count documentation is reconciled. Starting from the current documented baseline of 293 tools across 48 groups, the README and roadmap are updated to 49 capability groups and to the new all-enabled runtime tool total. With the required eight export tools, the expected total is 301 tools unless the implementation intentionally uses a different equivalent count and documents/proves it.

AC13. `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` no longer lists first-class `export` as an unresolved intent-polish backlog item; it describes the new `export` group with job caps, download path policy, and cleanup. `docs/COVERAGE.md` remains service-count stable because `ExportService` RPC coverage is already `6 / 0 / 0 / 6`.

AC14. New TDD red evidence is captured under `.agent/tasks/phase-2-first-class-export-group/raw/` before implementation: a focused new export module test fails with `ModuleNotFoundError`, and server tests fail for missing export registration/flag/capability/default approval behavior.

AC15. New offline unit tests cover the export module with fake proto/stub/client objects: connect laziness/redaction, planning, approval gate failures, confirmation failures, start option construction, `store_result_by_export_agent=False`, owned-session tracking, status normalization, download caps, safe-path rejection, no raw bytes in output, stop/destroy ownership checks, and cleanup counts.

AC16. Server tests cover `--enable-export`, `CAPABILITY_GROUPS`/`list_capabilities`, `create_server(export=...)`, all export tool registrations, duplicate-name protection in all-groups registration, `AXXON_EXPORT_APPROVE` inclusion in default-open approvals, and read-only/default-open behavior.

AC17. Adjacent regression tests remain green, including existing export smoke/preflight tests and generator/template tests. The new export group must not break existing HTTP or gRPC export smoke helpers.

AC18. Evidence is created after implementation: `.agent/tasks/phase-2-first-class-export-group/evidence.md`, `.agent/tasks/phase-2-first-class-export-group/evidence.json`, and raw command artifacts. Evidence must include sanitized red/green TDD logs, focused export/server test runs, adjacent regression runs, full unit discovery, `git diff --check`, tool-count proof, and a secret/raw-media scan or equivalent statement backed by command output.

AC19. Required verification commands pass on the final codebase:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Focused export/server tests and adjacent export/generator tests must also pass and be captured in raw artifacts.

AC20. A fresh verifier writes `.agent/tasks/phase-2-first-class-export-group/verdict.json` with `PASS` only after judging the current code and current command outputs against AC1-AC19. If the verifier does not pass, write `problems.md`, apply the smallest safe fix, and reverify.

AC21. If a controlled live smoke is attempted, it uses no committed secrets, may temporarily symlink a gitignored proto directory from the main repo, removes that symlink before commit, sanitizes all evidence, and treats remote stand timeouts as WARN/retry evidence rather than invalidating offline completion.

AC22. The completed implementation is committed and pushed to `main` only after verifier `PASS`.

## Verification Plan

1. Capture TDD red logs for the new export module and server wiring tests.
2. Implement the export module and server wiring against AC1-AC11.
3. Update README and roadmap counts/status, keeping coverage counts stable.
4. Run focused tests for `test_axxon_mcp_export.py` and `test_axxon_mcp_server.py`.
5. Run adjacent export/generator regression tests.
6. Run full `python3.12 -m unittest discover -s tools/tests`.
7. Run `git diff --check`, tool-count proof, and sanitized evidence checks.
8. Have a fresh verifier produce `verdict.json`; fix and reverify on any non-PASS.
9. Commit and push to `main` after PASS.
