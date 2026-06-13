# Phase 3: Bulk Camera Onboarding

## Original Task Statement

TASK_ID=`phase-3-bulk-camera-onboarding`

Freeze the repo-task-proof-loop spec at `.agent/tasks/phase-3-bulk-camera-onboarding/spec.md` for Phase 3: Bulk Camera Onboarding.

Repository: `/Users/jerrygergov/Documents/GitHub/axxon-one-mcp` on main.

User task source:
- Use repo-task-proof-loop for Phase 3: Bulk Camera Onboarding.
- Add CSV/JSON camera onboarding planner using DevicesCatalog, DiscoveryService, templates, ChangeConfig, archive assignment, detector defaults, rollback plans.
- Read docs/ALL_IN_ONE_VMS_API_ROADMAP.md, README.md, docs/COVERAGE.md, relevant tools/tests.
- Freeze spec before implementation, then execute with subagent-driven development, TDD, evidence.md/evidence.json/raw artifacts, full unittest discover, fresh verifier PASS, commit and push.
- Live stand is available but not required for offline unit-verifiable planner work; if direct gRPC is used, proto symlink must be removed before commit.

## Source Reconciliation

- `README.md` currently advertises 301 MCP tools across 49 capability groups: 296 server-local tools in `tools/axxon_mcp_server.py` plus 5 delegated translator tools.
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` lists IP device onboarding as strong for catalog/discovery/operator workflows but partial for bulk CSV/import UX. It explicitly calls for a bulk onboarding planner that validates CSV/JSON and emits one rollbackable plan per camera, and lists `bulk_onboarding` as a future first-class intent group.
- `docs/COVERAGE.md` currently reports 286 / 361 RPCs live-verified across 51 services. DevicesCatalog is 5 / 0 / 0 / 5 and DiscoveryService is 4 / 1 / 0 / 5. Adding an offline planner should not change those counts unless the API corpus is deliberately updated with fresh live evidence.
- Existing implementation ingredients:
  - `tools/axxon_mcp_devices_catalog.py` exposes read-only vendor/model/trait summaries and intentionally omits default credentials.
  - `tools/axxon_mcp_discovery.py` exposes read-only device discovery summaries keyed by IP/MAC-like fields.
  - `tools/axxon_mcp_site_graph.py` exposes a sanitized read-only graph of cameras, archives, detectors, layouts, maps, permissions, health, access points, event suppliers, and metadata endpoints.
  - `tools/axxon_mcp_operator.py` already implements plan/apply/verify/rollback, `create_camera`, `create_av_detector_full`, `create_appdata_detector_full`, `archive_policy_update`, template helpers, ChangeConfig-like payloads, confirmation tokens, per-plan state, and audit logging.
  - `tools/axxon_mcp_server.py` owns capability registration, `--enable-*` flags, open-by-default behavior, `APPROVE_ENV_VARS`, `--read-only`, and `list_capabilities`.
- "Templates" for this phase means Axxon/VMS camera configuration templates handled through ConfigurationService/ChangeTemplates-compatible behavior. It does not mean integration generator templates under `tools/templates/`.

## Scope

Add a first-class `bulk_onboarding` MCP capability group for planning and orchestrating bulk camera onboarding from inline CSV or JSON manifests. The group should validate input rows, correlate them with supported devices, discovery candidates, the existing site graph, existing archives/templates/detectors, and produce one rollbackable per-camera plan plus a batch-level orchestration plan.

Implementation is expected to touch:

- `tools/axxon_mcp_bulk_onboarding.py` (new)
- `tools/axxon_mcp_server.py`
- `tools/tests/test_axxon_mcp_bulk_onboarding.py` (new)
- `tools/tests/test_axxon_mcp_server.py`
- `README.md`
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md`

`docs/COVERAGE.md` should remain count-stable unless the implementation also changes the authoritative API corpus with real coverage evidence. The first implementation should be unit-verifiable offline; live stand use is optional.

## Assumptions

- The first-class group key and CLI flag are `bulk_onboarding` and `--enable-bulk-onboarding`.
- The public tool names are:
  - `bulk_onboarding_connect_axxon_profile`
  - `bulk_onboarding_schema`
  - `bulk_onboarding_validate_manifest`
  - `bulk_onboarding_plan`
  - `bulk_onboarding_apply_plan`
  - `bulk_onboarding_verify_plan`
  - `bulk_onboarding_rollback_plan`
  - `bulk_onboarding_audit_log`
- The manifest input accepts exactly one of `rows`, `csv_text`, or `json_text`. It does not accept arbitrary file paths, URLs, or server-side file reads.
- CSV parsing uses Python `csv.DictReader`. JSON parsing uses `json.loads`. JSON may be either an array of row objects or an object with a top-level `rows` array.
- A row is a camera intent. Minimal required row identity is a non-empty `display_name` plus enough device identity to onboard: `vendor` and `model`, and at least one of `ip`, `ip_address`, `mac`, or `mac_address`. Optional fields may include `display_id`, `host_uid`, `username` or `login`, `password`, `archive_uid` or `archive_access_point`, `template_id` or `template_name`, detector profile fields, and row-scoped overrides.
- Detector defaults are opt-in. No detector is planned unless a row or batch option names a supported detector profile. Supported first-pass profiles should map to existing operator workflows such as `create_av_detector_full` and `create_appdata_detector_full`.
- Archive assignment means assigning planned cameras to existing, validated archive targets or descriptor-backed archive policy changes. It does not include archive create, clear, format, reindex, resize, delete, or destructive archive maintenance.
- In-memory batch state is sufficient for this phase. If the MCP process restarts, previously held apply state may be lost; tools should report that limitation rather than claiming rollback certainty.

## Constraints

- Keep all task artifacts under `.agent/tasks/phase-3-bulk-camera-onboarding/`.
- Use subagent-driven development after this spec is frozen. Keep evidence ownership with one builder and verdict ownership with one fresh verifier.
- Use TDD. Capture failing red artifacts before implementation for the new module and server wiring.
- Preserve existing repository patterns for dataclass-with-factories modules, lazy env-profile connections, sanitized public config summaries, caps, `gap` responses, server capability registration, and fake-client offline tests.
- Do not invent a second broad mutation executor when existing `OperatorRegistry`, operator workflow builders, or ChangeConfig-style helper shapes can be reused or composed.
- Apply and rollback mutations require both `AXXON_BULK_ONBOARDING_APPROVE=1` and the exact confirmation token from the stored plan.
- `--read-only` must not default the bulk approval env var. In read-only mode, validation and planning can work, but apply and rollback must reject unless the explicit approval and confirmation gates are satisfied.
- Public tool responses, audit logs, docs examples, tests, and evidence must redact passwords, tokens, cookies, bearer values, session IDs, OTP/TFA secrets, authorization headers, CA contents, private keys, license keys, raw credential values, raw media bytes, and default device credentials.
- Intrinsic Axxon object identifiers such as `hosts/Server/...` may appear in sanitized outputs.
- The group must be unit-testable without live Axxon credentials, proto files, CA files, or network access.
- If direct gRPC or a live stand is used during optional verification, any temporary proto symlink must be removed before commit and evidence must be sanitized.

## Non-Goals

- No destructive archive maintenance: no archive clear, format, reindex, resize, delete, backup, restore, or license/domain/cloud destructive operations.
- No broad schema-first arbitrary config assistant beyond the fields needed for bulk camera onboarding.
- No generator template expansion and no changes to `tools/templates/` for Phase 3.
- No arbitrary file import from local/server paths, URLs, S3, network shares, or user-supplied filesystem locations.
- No mandatory live stand run.
- No committed proto files, CA material, credentials, passwords, tokens, or symlinks to gitignored proto directories.
- No claim that RPC live coverage changed unless the authoritative API corpus and evidence are updated separately.

## Acceptance Criteria

AC1. A new `tools/axxon_mcp_bulk_onboarding.py` module exists, imports without credentials or network access, follows the existing dataclass-with-factories/lazy-client pattern, and exposes constants equivalent to `BULK_ONBOARDING_APPROVE_ENV = "AXXON_BULK_ONBOARDING_APPROVE"`, `BULK_ONBOARDING_CONFIRMATION = "CONFIRM-bulk-onboarding"`, and `BULK_ONBOARDING_TOOL_NAMES`.

AC2. `BULK_ONBOARDING_TOOL_NAMES` exactly matches the registered public tools: `bulk_onboarding_connect_axxon_profile`, `bulk_onboarding_schema`, `bulk_onboarding_validate_manifest`, `bulk_onboarding_plan`, `bulk_onboarding_apply_plan`, `bulk_onboarding_verify_plan`, `bulk_onboarding_rollback_plan`, and `bulk_onboarding_audit_log`.

AC3. `bulk_onboarding_connect_axxon_profile(profile="env")` supports the env profile, builds live dependencies lazily, returns a sanitized public profile summary, reports mode, approval env, and confirmation token metadata, and returns a `gap` response for non-env profiles without attempting a connection.

AC4. `bulk_onboarding_schema` returns the accepted manifest schema, required fields, optional fields, supported detector profiles, allowed input sources (`rows`, `csv_text`, `json_text`), approval env, confirmation token, and redaction policy. It must not require a live server.

AC5. Manifest parsing accepts exactly one of `rows`, `csv_text`, or `json_text`; rejects zero or multiple input sources; parses CSV with `csv.DictReader`; parses JSON with `json.loads`; accepts JSON arrays or `{"rows": [...]}` objects; normalizes row numbers; preserves deterministic row order; and rejects non-object rows with row-scoped errors.

AC6. The module rejects arbitrary file paths, filesystem reads, URL inputs, and path-like import options. Tests must prove that a field such as `path`, `file`, `filename`, or `manifest_path` is not treated as an import source.

AC7. Every public output from parsing, validation, planning, apply, verify, rollback, and audit redacts secret-like fields and nested secret-like values, including row `password`, `credentials.password`, tokens, cookies, authorization values, and default device credentials. Redaction must also apply to errors and audit entries.

AC8. Validation checks required row fields, duplicate rows within the manifest, duplicate IP/MAC/display name/display ID where supplied, invalid IP-like values, unsupported vendor/model values from a DevicesCatalog-compatible provider, discovery mismatches by IP/MAC from a DiscoveryService-compatible provider, existing camera conflicts from a site-graph-compatible provider, archive reference existence, VMS camera template reference existence, and detector profile validity.

AC9. Validation is batch-aware and row-aware. It returns top-level `status` (`ok`, `warn`, or `error`), a summary count, normalized sanitized rows, row-specific errors/warnings with row numbers and row IDs, and dependency section statuses for catalog/discovery/site graph/template/archive/detector checks. One bad row must not hide validation results for other rows.

AC10. Discovery correlation is advisory unless explicitly required by input options. A row may validate with a warning when live discovery data is unavailable, but must error when a supplied IP/MAC conflicts with a different discovered vendor/model or an existing camera in the site graph.

AC11. `bulk_onboarding_plan` first performs the same manifest validation, refuses to produce apply-ready plan entries for error rows, and emits a deterministic batch plan with a `batch_plan_id`, `status`, sanitized manifest summary, per-camera plans, dependency snapshots, `confirmation_token`, `rollback_confirmation_token`, and batch-level rollback order.

AC12. Each valid per-camera plan includes a stable row identifier, row number, normalized display name, intended host, vendor/model, IP/MAC metadata, expected camera access point or UID placeholder, risk classification, operator/ChangeConfig-compatible steps, expected outcomes, rollback strategy, and sanitized before/after or diff metadata where practical.

AC13. Camera creation planning composes or mirrors the existing operator `create_camera` workflow shape where practical, including ChangeConfig-compatible `DeviceIpint` creation steps, without exposing raw passwords in the plan.

AC14. VMS camera template handling is represented as ConfigurationService/ChangeTemplates-compatible validation and plan metadata. The implementation may support `template_id` and/or `template_name`, but it must not use integration generator templates or edit `tools/templates/`.

AC15. Archive assignment planning validates that archive targets exist and emits only non-destructive, rollbackable assignment or descriptor-backed policy steps. Plans must explicitly reject archive create, clear, format, reindex, resize, delete, or any operation marked as destructive archive maintenance.

AC16. Detector defaults are opt-in. When no detector profile is requested, no detector creation step is emitted. When a supported profile is requested, the plan emits detector steps compatible with existing `create_av_detector_full` and/or `create_appdata_detector_full` workflows and includes row/batch overrides without changing unrelated detector defaults.

AC17. `bulk_onboarding_apply_plan(batch_plan_id, confirmation)` refuses unknown plans, stale/non-planned plans, missing or mismatched confirmation, and missing `AXXON_BULK_ONBOARDING_APPROVE=1`. When allowed, it applies per-camera steps in deterministic row order and records per-row partial state after each successful step.

AC18. Apply handles partial failure safely. If a row fails, already-applied rows and steps remain recorded, later row behavior is deterministic and documented by the result, the batch status becomes partial/error as appropriate, and `bulk_onboarding_rollback_plan` can roll back only the recorded applied steps.

AC19. `bulk_onboarding_rollback_plan(batch_plan_id, confirmation)` requires `AXXON_BULK_ONBOARDING_APPROVE=1` plus the plan rollback confirmation token, rejects unknown plans, and rolls back applied rows in reverse apply order with per-row step details. It must not attempt to roll back rows or steps that were never applied.

AC20. `bulk_onboarding_verify_plan(batch_plan_id)` verifies known planned/applied/rolled-back state using injectable fake/live readers. It reports per-row camera/template/archive/detector expectations, created UID presence, still-present items, missing items, and snapshot/rollback status without leaking secrets.

AC21. `bulk_onboarding_audit_log` returns an in-memory sanitized audit trail for connect, schema, validate, plan, apply, verify, and rollback events, including timestamps or sequence numbers, batch IDs, row counts, status, and rejection reasons. It must not expose passwords or raw manifest secrets.

AC22. `tools/axxon_mcp_server.py` wires the group through `CAPABILITY_GROUPS`, `create_server(bulk_onboarding=...)`, `enabled_groups`, `register_bulk_onboarding_tools`, `--enable-bulk-onboarding`, `APPROVE_ENV_VARS`, default-open behavior, `--enable-all`, `--read-only`, and `main()` construction. `list_capabilities` reports `bulk_onboarding` disabled with `--enable-bulk-onboarding` when absent and enabled when supplied.

AC23. Server startup remains lazy: enabling `bulk_onboarding` must not require Axxon credentials, proto files, CA files, or a live network connection until a live-backed method actually needs them.

AC24. Documentation is reconciled. Starting from the current documented baseline of 301 tools across 49 groups (296 server-local plus 5 delegated translator tools), adding the eight required bulk onboarding tools should update README and roadmap counts to 309 tools across 50 groups (304 server-local plus 5 delegated translator tools), unless the final implementation intentionally uses a different count and proves/documents it. The roadmap must no longer list `bulk_onboarding` only as future intent polish.

AC25. `docs/COVERAGE.md` remains service/RPC count-stable unless the authoritative API corpus changes. If it remains unchanged, evidence must note that Phase 3 adds planner/orchestrator tooling and does not claim new live RPC coverage.

AC26. New focused unit tests cover CSV parsing, JSON parsing, schema output, input-source exclusivity, no-file-path import, required-field errors, row numbering, duplicate rows, existing-camera conflicts, catalog unsupported vendor/model, discovery IP/MAC matching and mismatch behavior, archive reference validation, template validation, detector profile defaults and overrides, sanitized outputs, planning diffs, per-camera rollback metadata, approval/confirmation gates, apply state, partial failure, reverse rollback, verify behavior, and audit redaction.

AC27. Server tests cover disabled-by-default registration in docs-only `create_server`, enabled registration of all eight tools, `--enable-bulk-onboarding`, `CAPABILITY_GROUPS` and `list_capabilities`, duplicate-name protection in all-groups registration, inclusion of `AXXON_BULK_ONBOARDING_APPROVE` in `APPROVE_ENV_VARS`, default-open approval behavior, and read-only non-defaulting behavior.

AC28. TDD red evidence is captured under `.agent/tasks/phase-3-bulk-camera-onboarding/raw/` before implementation. At minimum, a focused bulk onboarding module test fails for missing `axxon_mcp_bulk_onboarding`, and a server wiring test fails for missing `bulk_onboarding` registration/flag/capability/default approval behavior.

AC29. Evidence is created after implementation: `.agent/tasks/phase-3-bulk-camera-onboarding/evidence.md`, `.agent/tasks/phase-3-bulk-camera-onboarding/evidence.json`, and raw command artifacts. Evidence must include sanitized red/green TDD logs, focused bulk onboarding/server tests, full unit discovery, `git diff --check`, count proof, documentation reconciliation proof, and a secret/proto-symlink scan or equivalent command output.

AC30. Required final verification commands pass on the final codebase:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

Focused bulk onboarding and server tests must also pass and be captured in raw artifacts.

AC31. A fresh verifier writes `.agent/tasks/phase-3-bulk-camera-onboarding/verdict.json` with `PASS` only after judging current code and current command outputs against AC1-AC30. If verification is not `PASS`, write `problems.md`, apply the smallest defensible fix, rerun checks, and reverify.

AC32. If optional live evidence is attempted, it uses no committed secrets, sanitizes host/user/password/token/CA details, treats remote stand timeouts as WARN/retry evidence rather than invalidating offline completion, and removes any temporary direct-gRPC proto symlink before commit.

AC33. The completed implementation is committed and pushed to `main` only after every acceptance criterion is `PASS` and the fresh verifier has passed.

## Verification Plan

1. Capture TDD red logs for the missing bulk onboarding module and missing server wiring under `.agent/tasks/phase-3-bulk-camera-onboarding/raw/`.
2. Implement `tools/axxon_mcp_bulk_onboarding.py` with injectable catalog, discovery, site graph, operator/config, template, archive, and detector providers so offline fake tests drive behavior.
3. Wire `tools/axxon_mcp_server.py` for the new group, flag, capability discovery, approval env, default-open behavior, read-only behavior, and lazy main construction.
4. Add focused offline tests for parsing, validation, planning, gating, apply, partial failure, rollback, verify, audit, and redaction.
5. Update README and roadmap counts/status. Leave `docs/COVERAGE.md` count-stable unless authoritative corpus evidence changes.
6. Run focused tests:

```bash
python3.12 -m unittest discover -s tools/tests -p 'test_axxon_mcp_bulk_onboarding.py'
python3.12 -m unittest tools/tests/test_axxon_mcp_server.py
```

7. Run full required checks:

```bash
python3.12 -m unittest discover -s tools/tests
git diff --check
```

8. Capture count proof, documentation diff proof, secret redaction/proto-symlink scan, and all command outputs as raw artifacts.
9. Have a fresh verifier produce `verdict.json`; on non-PASS, write `problems.md`, make the smallest safe fix, and reverify.
10. Commit and push to `main` only after verifier `PASS`.
