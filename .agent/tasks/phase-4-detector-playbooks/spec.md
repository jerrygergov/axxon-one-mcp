# Phase 4 Detector Playbooks Spec

Task ID: `phase-4-detector-playbooks`
Spec path: `.agent/tasks/phase-4-detector-playbooks/spec.md`
Worktree: `/Users/jerrygergov/Documents/GitHub/axxon-one-mcp`

## Original Task Statement

```text
Use repo-task-proof-loop for Phase 4: Detector Playbooks. Add task-first detector creation/configuration for the major detector families, including masks/areas/lines/VMDA/AppData flows and parameter schemas. Read docs/ALL_IN_ONE_VMS_API_ROADMAP.md, README.md, docs/COVERAGE.md, and relevant tools/tests. Freeze spec first, then execute with subagent-driven development, TDD, evidence.md/evidence.json/raw artifacts, run python3.12 -m unittest discover -s tools/tests, fresh verifier PASS, commit and push main.

Important repo state from parent inspection:
- Current branch main aligned to origin/main, with only pre-existing untracked docs/Axxon_One_Integration_APIs.postman_collection.json.
- Current counts before Phase 4: README and roadmap state 309 MCP tools across 50 groups; all-enabled runtime is 304 server-local plus 5 delegated translator tools; tests 1147.
- Roadmap detector gap: docs/ALL_IN_ONE_VMS_API_ROADMAP.md product map says Detectors and analytics current status strong common detector workflows/reads, partial GlobalTracker/RealtimeRecognizerExternal fixtures, next gap: add detector playbooks for every documented detector family and fixture-gated global tracking profile workflows.
- README safety model has approval/env patterns for operator/export/bulk onboarding.
- docs/COVERAGE.md has 286/361 live-verified; ExternalDetectorService 2 pass, VMDAService 4 pass, GlobalTrackerService 1 pass/6 fixture-blocked, RealtimeRecognizerExternal 1 fixture-blocked, TagAndTrack fixture-blocked.
- Existing modules: tools/axxon_mcp_detector_archive.py is read-only and exposes detector_kind_catalog, detector_parameter_schema, detector_config_get, detector_visual_elements, metadata_schema_catalog, metadata_sample_bounded, archive_policy_get. It already has known detector fallback catalog AVDetector: MotionDetection/SceneDescription/NeuroTracker and AppDataDetector: MoveInZone/OneLineCrossing/LongInZone/LostObject/AbandonedObject; schema flattening, visual element shape discovery, sensitive redaction.
- Existing operator module tools/axxon_mcp_operator.py has plan/apply/verify/rollback workflows including create_av_detector_full, create_appdata_detector_full, update_detector_parameters, update_detector_visual_element, delete_detector, raise_external_event, raise_periodical_event. AppData supports chain-created SceneDescription AVDetector when vmda_source_ap is omitted.
- Existing server pattern in tools/axxon_mcp_server.py: CAPABILITY_GROUPS, create_server optional dependency, enabled_groups, register_*_tools, parser flag, APPROVE_ENV_VARS, main construction. Detector_archive group is read-only; new detector_playbooks should remain separate and mutation-gated.
- Explorers found dangling corpus references to docs/api-audit/mutation-playbooks/detector-parameters.md and external-events.md; current checkout lacks docs/api-audit/mutation-playbooks/.
- Masks/areas/lines must be typed config properties using descriptor value kinds (value_rectangle, value_polyline, value_mask, value_simple_polygon etc.) and VisualElement subunits, not guessed strings.
- Do not claim all detector families are live-supported from fallback catalog. Produce matrix distinguishing supported fallback/local, live/template/factory-discovered, and fixture-needed families (GlobalTracker, RealtimeRecognizerExternal/TagAndTrack where applicable).

Required scope for spec:
- Add first-class detector_playbooks MCP capability group with tools around task-first planning/applying/verifying/rolling back detector workflows.
- Expected tool surface should include at least: detector_playbooks_connect_axxon_profile, list_detector_playbooks, detector_playbook_parameter_schema (or similar schema helper), plan_detector_playbook, apply_detector_playbook_plan, verify_detector_playbook_plan, rollback_detector_playbook_plan, detector_playbooks_audit_log. Keep exact names stable in ACs if you choose them.
- New module should orchestrate existing detector_archive and operator APIs; no direct ChangeConfig implementation unless justified by a missing existing workflow.
- Support task intents for major families: AVDetector creation/configuration (MotionDetection/SceneDescription/NeuroTracker fallback plus discovered kinds), AppDataDetector creation/configuration (MoveInZone/OneLineCrossing/LongInZone/LostObject/AbandonedObject fallback plus discovered kinds), detector parameter updates, visual geometry updates for masks/areas/lines, delete detector, external detector occasional/periodical event flows, VMDA/AppData binding/preflight, metadata/VMDA/heatmap guidance, and fixture-needed GlobalTracker/RealtimeRecognizerExternal handling.
- Mutation gates: AXXON_DETECTOR_PLAYBOOKS_APPROVE=1 plus exact confirmation token CONFIRM-detector-playbooks for apply and CONFIRM-detector-playbooks-rollback for rollback, while delegating the operator's underlying per-plan confirmation internally from stored plan metadata. Planning must not call apply/rollback.
- Audit and responses must be sanitized: no passwords, tokens, CA/ticket material, license keys, raw media, raw biometric vectors, or raw metadata payloads.
- TDD: add failing tests before production code. Tests should include module tests and server registration/capability/approval tests, plus adjacent detector_archive/operator regression commands.
- Docs update: README counts/layer/safety/tests, roadmap counts/status/remaining gap; docs/COVERAGE.md should remain stable unless source coverage changes. Add docs/api-audit/mutation-playbooks/ files to resolve dangling recipe refs if within scope.
- Evidence requirements: .agent/tasks/phase-4-detector-playbooks/evidence.md, evidence.json, raw artifacts for RED/GREEN/full tests, counts, docs diff/stability, secret/proto scan, verifier outputs, git status.
- Verification required: python3.12 -m unittest discover -s tools/tests, git diff --check, fresh verifier PASS. Commit and push to main.
```

## Pre-Spec Explorer Summary

- Parent local inspection found `main` aligned with `origin/main`; the only pre-existing untracked file was `docs/Axxon_One_Integration_APIs.postman_collection.json`.
- Two explorer children plus parent local inspection succeeded and agreed on the detector gap, existing `detector_archive` read APIs, existing `operator` mutation workflows, server wiring pattern, and documentation/count state.
- One implementation explorer failed because of a remote compact/network error. Its output is not treated as evidence.
- This spec reconciles those inputs against the current checkout by reading `AGENTS.md`, `README.md`, `docs/ALL_IN_ONE_VMS_API_ROADMAP.md`, `docs/COVERAGE.md`, `tools/axxon_mcp_server.py`, `tools/axxon_mcp_detector_archive.py`, `tools/axxon_mcp_operator.py`, and adjacent tests.

## Scope

Phase 4 adds a first-class, task-first `detector_playbooks` MCP capability group. It should guide users through detector creation/configuration tasks while reusing existing descriptor discovery and operator mutation machinery.

The public Phase 4 group is mutating-capable and separate from the existing read-only `detector_archive` group. It must provide planning, apply, verify, rollback, schema, catalog, connection, and audit surfaces, with apply/rollback behind both an env approval gate and a fixed Phase 4 confirmation token.

## Assumptions

- The new public tool surface is exactly the eight tools listed in AC2. With no extra tools, the documented all-enabled runtime count should move from 309 to 317 tools: 312 server-local tools plus 5 delegated translator tools, across 51 groups.
- The existing operator workflows are sufficient for Phase 4 mutations: `create_av_detector_full`, `create_appdata_detector_full`, `update_detector_parameters`, `update_detector_visual_element`, `delete_detector`, `external_event_inject`, and `raise_periodical_event`.
- `detector_archive` remains the source of detector kind catalogs, parameter schemas, visual element summaries, VMDA/metadata schema hints, and sensitive property redaction.
- `docs/COVERAGE.md` should not change because this phase adds task-first MCP orchestration and offline tests, not new live RPC verification. If a later builder changes API coverage source data, that must be separately evidenced.
- The pre-existing untracked Postman collection is not part of this task and must not be committed.

## Acceptance Criteria

### AC1 - Capability Group And Server Wiring

Pass when the repository adds a new `detector_playbooks` capability group that follows the existing server patterns:

- `tools/axxon_mcp_server.py` includes `detector_playbooks` in `CAPABILITY_GROUPS` with enable flag `--enable-detector-playbooks`.
- `create_server(...)` accepts an optional `detector_playbooks` dependency, reports it in `enabled_groups`, and registers it only when provided.
- `build_parser()` accepts `--enable-detector-playbooks`; `--enable-all` and default-open mode enable it; `--read-only` still registers groups but does not default mutation approval.
- `APPROVE_ENV_VARS` includes `AXXON_DETECTOR_PLAYBOOKS_APPROVE`.
- `main()` constructs the detector playbooks group lazily, without requiring credentials at server boot, and without enabling or exposing the existing operator group as a public side effect.
- `list_capabilities` reports the group as disabled with `--enable-detector-playbooks` when absent and enabled with no `enable_flag` when present.
- The all-enabled tool/group counts in docs and evidence are consistent with actual registration. If only the AC2 tools are added, the expected count is 317 tools across 51 groups, with 312 server-local tools plus 5 delegated translator tools.

### AC2 - Stable Public Tool Surface

Pass when exactly these eight public tools are registered for `detector_playbooks` and none are registered when the group is disabled:

- `detector_playbooks_connect_axxon_profile(profile: str = "env")`
- `list_detector_playbooks(include_live: bool = True)`
- `detector_playbook_parameter_schema(unit_type: str, detector_kind: str, intent: str = "")`
- `plan_detector_playbook(intent: str, params: dict[str, Any] | None = None)`
- `apply_detector_playbook_plan(playbook_plan_id: str, confirmation: str)`
- `verify_detector_playbook_plan(playbook_plan_id: str)`
- `rollback_detector_playbook_plan(playbook_plan_id: str, confirmation: str)`
- `detector_playbooks_audit_log()`

The tool names above are stable and must be used in tests, README, and roadmap updates.

### AC3 - Connection, Catalog, And Schema Helper Behavior

Pass when the read/planning helpers work offline with injectable dependencies and live when connected:

- `detector_playbooks_connect_axxon_profile("env")` returns a sanitized profile summary, `mode: "detector-playbooks"`, `approval_env: "AXXON_DETECTOR_PLAYBOOKS_APPROVE"`, `confirmation_token: "CONFIRM-detector-playbooks"`, and `rollback_confirmation_token: "CONFIRM-detector-playbooks-rollback"`.
- Non-`env` profiles return a `status: "gap"` response and do not build live clients.
- `list_detector_playbooks` returns supported intent names, required/optional parameter summaries, geometry value-kind policy, gate information, and the detector family matrix from AC4.
- `detector_playbook_parameter_schema` delegates to `detector_archive.detector_parameter_schema` for detector descriptors and augments it with playbook-specific required params for the requested intent without leaking secrets.
- Schema responses preserve descriptor paths, `value_kind`, enum/range information, and `visual_elements` data from `detector_archive`.

### AC4 - Detector Family Matrix

Pass when `list_detector_playbooks` and relevant plan/schema responses include a matrix that clearly separates:

- `supported_fallback_local`: AVDetector `MotionDetection`, `SceneDescription`, `NeuroTracker`; AppDataDetector `MoveInZone`, `OneLineCrossing`, `LongInZone`, `LostObject`, `AbandonedObject`.
- `live_unit_discovered`, `template_discovered`, and `factory_discovered`: additional AVDetector/AppDataDetector kinds returned by `detector_archive.detector_kind_catalog(include_live=True)` with provenance preserved.
- `fixture_needed`: GlobalTracker profile workflows (`ChangeGlobalTrackerProfiles`, `ChangeProfiles`, `ClearProfiles`, `BindGlobalTrackProfile`, `GetGlobalTrackBestVisibilityPositions`), `RealtimeRecognizerExternalService.GetData`, and TagAndTrack workflows (`ListTrackers`, `SetMode`, `FollowTrack`, `MoveToCoords`) unless a future fixture-backed implementation is actually present and evidenced.

The matrix must not claim all fallback/local catalog kinds are live-supported. It must expose the source/provenance and fixture requirements in a way tests can assert.

### AC5 - Task-First Planning For Core Detector Mutations

Pass when `plan_detector_playbook` supports these stable intent names and maps them to existing operator workflows:

- `create_av_detector` -> operator `create_av_detector_full`.
- `create_appdata_detector` -> operator `create_appdata_detector_full`; missing `vmda_source_ap` is allowed and must be represented as the existing SceneDescription chain-created VMDA flow.
- `update_detector_parameters` -> operator `update_detector_parameters`.
- `update_detector_geometry` -> operator `update_detector_visual_element`.
- `delete_detector` -> operator `delete_detector`.
- `raise_external_event` -> operator `external_event_inject`.
- `raise_periodical_external_event` -> operator `raise_periodical_event`.
- `preflight_vmda_appdata` -> read-only preflight/guidance response.
- `metadata_vmda_heatmap_guidance` -> read-only guidance response.
- `global_tracker_profile` -> fixture-needed response unless fixture-backed support is present.
- `realtime_recognizer_external` -> fixture-needed response.
- `tag_and_track` -> fixture-needed response.

For operator-backed intents, planning must call only `operator.plan(...)`, never `operator.apply(...)`, `operator.rollback(...)`, or any direct mutation client method. Public plan responses must use a Phase 4 plan id such as `detector-playbook-plan-*`, include a normalized task summary, expected source bindings, public diff/steps, rollback classification, and only the Phase 4 confirmation tokens. The delegated operator plan id and underlying operator confirmation tokens must be stored internally and not exposed in public responses or audit output.

### AC6 - Typed Geometry For Masks, Areas, And Lines

Pass when geometry updates are descriptor-backed, not string-guessed:

- `detector_playbook_parameter_schema` exposes editable VisualElement subunits and shape fields from `detector_archive`, including at least `value_rectangle`, `value_polyline`, `value_mask`, and `value_simple_polygon` when descriptors provide them.
- `plan_detector_playbook("update_detector_geometry", ...)` requires a `visual_element_uid` or descriptor-resolved visual element path plus a property path and `value_kind`.
- The planner builds ChangeConfig property nodes using the descriptor's exact value field, for example `value_rectangle`, `value_polyline`, `value_mask`, or `value_simple_polygon`; it rejects mismatched or unknown value kinds with `status: "error"` or `status: "gap"` and does not create an operator plan.
- Tests cover representative area/line/mask shapes and prove the public plan carries typed property metadata while the stored operator plan receives the correct `properties` payload for `update_detector_visual_element`.

### AC7 - External Detector Event Playbooks

Pass when external detector event flows are task-first wrappers over existing operator workflows:

- `raise_external_event` plans an occasional event through `external_event_inject` and requires an external detector event supplier access point.
- `raise_periodical_external_event` plans periodical target-list/tracklet events through `raise_periodical_event`, with bounded tracklet count and no raw biometric vectors or raw media.
- Public responses distinguish no-rollback/noop event injection from rollbackable config mutations while still requiring the Phase 4 rollback confirmation token for a rollback call.
- Rejected HTTP/body error states from the underlying operator remain visible as sanitized status/error summaries.

### AC8 - VMDA/AppData, Metadata, And Heatmap Guidance

Pass when playbooks guide VMDA/AppData flows without inventing unsupported mutations:

- `preflight_vmda_appdata` reports required `video_source_ap`, optional/existing `vmda_source_ap`, and the SceneDescription chain-creation path used by `create_appdata_detector`.
- It reports whether the AppData detector kind is supported from fallback/local data, live units, templates, factories, or fixture-needed status.
- `metadata_vmda_heatmap_guidance` returns safe next-tool guidance for `metadata_schema_catalog`, `metadata_sample_bounded`, metadata/VMDA query tools, and heatmap tools, including endpoint type expectations and count/time caps.
- Guidance responses do not include raw metadata frames, raw media bytes, copied proto text, or credentials.

### AC9 - Fixture-Gated Families Remain Honest

Pass when unsupported or fixture-blocked detector-adjacent families are handled explicitly:

- GlobalTracker profile workflows return `status: "fixture-needed"` or a non-apply-ready plan unless safe fixture-backed implementation and evidence are added in the same task.
- RealtimeRecognizerExternal and TagAndTrack intents return fixture-needed guidance with required fixtures and source service/RPC names.
- Existing read-only `global_tracker.get_profile` support may be referenced as a read-only prerequisite, but Phase 4 must not add unaudited GlobalTracker, RealtimeRecognizerExternal, or TagAndTrack mutations.
- Applying a fixture-needed/non-apply-ready plan is rejected without calling the operator or live clients.

### AC10 - Approval Gates, Delegation, Verify, And Rollback

Pass when apply/rollback behavior is safe and stateful:

- `apply_detector_playbook_plan` rejects unknown plan ids, non-apply-ready plans, missing `AXXON_DETECTOR_PLAYBOOKS_APPROVE=1`, and any confirmation other than `CONFIRM-detector-playbooks`, without delegating to the operator.
- On a valid apply, the module retrieves the stored operator plan metadata and calls `operator.apply(operator_plan_id, stored_operator_confirmation_token)` internally.
- `verify_detector_playbook_plan` delegates to `operator.verify` for operator-backed plans and returns normalized `planned`, `applied`, `verified`, `rolled_back`, `error`, or `fixture-needed` status as appropriate.
- `rollback_detector_playbook_plan` rejects missing env approval and any confirmation other than `CONFIRM-detector-playbooks-rollback`; on valid rollback it calls `operator.rollback(operator_plan_id, stored_operator_rollback_confirmation_token)` internally.
- Reapply and rerollback edge cases are deterministic and tested: already-applied plans are not applied twice; rollback of a never-applied mutation is rejected or a documented noop; event noop rollback is explicit.

### AC11 - Sanitized Responses And Audit Trail

Pass when every public response and `detector_playbooks_audit_log` is recursively sanitized:

- Redact or omit passwords, bearer/basic tokens, cookies, session ids, CA material, ticket material, license keys, private keys, raw media, raw biometric vectors, raw metadata payloads, and secret-like ChangeConfig property values.
- Intrinsic object identifiers such as `hosts/Server/...` may remain.
- Audit entries include sequence/timestamp/action/plan id/intent/status/reason fields, but no stored operator confirmation tokens, raw params with secrets, or raw payload blobs.
- Unit tests inject secret markers in params, schema descriptors, external event data, and simulated operator responses, and assert those markers do not appear in public responses or audit logs.

### AC12 - TDD And Test Coverage

Pass when implementation follows TDD and leaves focused offline coverage:

- New failing tests are written and captured before production code changes. Evidence includes a RED command output proving the tests fail for the missing Phase 4 behavior.
- Add module tests, expected as `tools/tests/test_axxon_mcp_detector_playbooks.py`, covering catalog/schema behavior, planning for each supported intent family, typed geometry validation, approval gates, internal operator token delegation, verify/rollback state, fixture-needed families, and redaction.
- Add server tests in `tools/tests/test_axxon_mcp_server.py` covering registration only when enabled, `CAPABILITY_GROUPS`, parser flag, default-open/read-only approval env behavior, list_capabilities, no duplicate tool names, and no-credentials lazy construction.
- Run adjacent regressions for detector/archive and operator behavior after changes.

### AC13 - Documentation Updates And Coverage Stability

Pass when docs reflect the new public surface without overstating live coverage:

- `README.md` updates the tool count, group count, tool layers, safety model, and unit test count. If only the eight AC2 tools are added, it should state 317 MCP tools across 51 groups, with 312 server-local plus 5 delegated translator tools.
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md` updates current numbers and detector/analytics status to say Phase 4 added task-first detector playbooks, while remaining honest about fixture-needed GlobalTracker, RealtimeRecognizerExternal, and TagAndTrack work.
- `docs/COVERAGE.md` remains unchanged unless `docs/api-audit/mcp-corpus/api_methods.json` statuses are intentionally changed and evidenced.
- Add `docs/api-audit/mutation-playbooks/detector-parameters.md` and `docs/api-audit/mutation-playbooks/external-events.md` with sanitized, concise recipes that resolve the detector-related dangling corpus references. Do not broaden this into unrelated playbooks unless separately justified.
- Do not commit or modify the pre-existing untracked `docs/Axxon_One_Integration_APIs.postman_collection.json`.

### AC14 - Evidence Artifacts

Pass when `.agent/tasks/phase-4-detector-playbooks/` contains:

- `evidence.md` summarizing each AC with PASS/FAIL, commands, important outputs, and links to raw artifacts.
- `evidence.json` with machine-readable `task_id`, final status, commit SHA if committed, pushed branch, and an `acceptance_criteria` array containing `id`, `status`, and evidence references for every AC.
- Raw artifacts under `.agent/tasks/phase-4-detector-playbooks/raw/` for RED tests, GREEN targeted tests, full test run, adjacent regression runs, tool/group counts, docs diff/coverage stability check, secret/proto scan, fresh verifier output, push output, and final git status.
- Evidence explicitly records that no AxxonSoft proto files, CA files, tickets, credentials, raw media, raw metadata payloads, or license keys were added.

### AC15 - Final Verification, Fresh Verifier, Commit, And Push

Pass when the builder completes these checks against the final codebase:

- `python3.12 -m unittest discover -s tools/tests` passes.
- `git diff --check` passes.
- A fresh verifier pass returns `PASS` for all ACs and its output is saved in raw artifacts.
- The final git status is clean except for the pre-existing untracked Postman collection, or the evidence explains any remaining non-task file.
- The accepted changes are committed on `main` and pushed to `origin/main`; evidence includes the commit SHA and push result.

## Constraints

- Keep all workflow artifacts under `.agent/tasks/phase-4-detector-playbooks/`.
- Do not implement production code before this spec is frozen.
- Use subagent-driven development after spec freeze, with one builder owning evidence and one fresh verifier owning the final verdict.
- Preserve existing module boundaries: `detector_archive` is read-only schema/config discovery; `operator` owns mutation transport; `detector_playbooks` orchestrates task-first plans.
- Do not add direct `ChangeConfig`, HTTP external-event, or GlobalTracker mutation implementation in the new module unless a missing workflow is proven and documented; the expected path is to delegate to existing operator workflows.
- Do not commit AxxonSoft proto files, Integration API PDFs, CA material, tickets, credentials, raw media, raw metadata payloads, or biometric vectors.
- Keep `detector_playbooks` separate from `detector_archive`; enabling one group must not accidentally expose the other group's tools.

## Non-Goals

- Live-verifying every detector family.
- Claiming fallback/local detector kinds are present on a live stand.
- Adding first-class TagAndTrack, RealtimeRecognizerExternal, or GlobalTracker mutation groups.
- Reworking generic `config_change`, `operator`, `detector_archive`, `metadata`, `heatmap`, or `recognizer` behavior beyond the minimal integration needed for Phase 4.
- Regenerating the full API corpus or creating unrelated mutation playbooks.
- Changing `docs/COVERAGE.md` live coverage numbers without new source coverage data.

## Implementation Approach

1. Add failing tests first for the new module and server wiring, then capture RED output in the task raw artifacts.
2. Implement `tools/axxon_mcp_detector_playbooks.py` as a small stateful orchestrator with injectable dependencies for `detector_archive`, `operator`, optional metadata/heatmap/global-tracker readers, config factory, env mapping, and audit storage.
3. Reuse `detector_archive` for detector family catalog, schema flattening, VisualElement shape fields, config snapshots, metadata schema guidance, and redaction where possible. Reuse the operator registry for all existing mutations.
4. Add server registration and CLI/default-open wiring following the Phase 3 `bulk_onboarding` pattern.
5. Update README, roadmap, and detector-related mutation playbook docs after code/tests establish the final count.
6. Run targeted tests, adjacent regressions, full unittest discovery, diff/secret scans, and the fresh verifier before commit/push.

## Verification Plan

- RED: run the new detector playbooks tests and server registration tests before implementation and save failure output.
- GREEN targeted: run new module tests plus `tools/tests/test_axxon_mcp_server.py`.
- Adjacent regressions: run `tools/tests/test_axxon_mcp_detector_archive.py`, `tools/tests/test_axxon_api_client_detector_archive.py`, and `tools/tests/test_axxon_mcp_operator.py`.
- Full suite: run `python3.12 -m unittest discover -s tools/tests`.
- Static checks: run `git diff --check`, count registered tools/groups, compare docs counts, verify `docs/COVERAGE.md` stability, and scan changed files for secrets/proto/CA/ticket/raw media indicators.
- Fresh verification: run the repo-task-proof-loop verifier against the final code and save a PASS verdict before committing and pushing.
