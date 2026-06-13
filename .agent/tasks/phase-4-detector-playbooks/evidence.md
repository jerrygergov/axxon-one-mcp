# Phase 4 Detector Playbooks Evidence

Task ID: `phase-4-detector-playbooks`
Status: `BUILDER_READY_WITH_CONCERNS`
Current branch/head: `main` at `32d46b1d267e3f06c8f0eaa2634ce0d4946315dd`

## Summary

Implemented a first-class `detector_playbooks` capability group with eight public tools:

- `detector_playbooks_connect_axxon_profile`
- `list_detector_playbooks`
- `detector_playbook_parameter_schema`
- `plan_detector_playbook`
- `apply_detector_playbook_plan`
- `verify_detector_playbook_plan`
- `rollback_detector_playbook_plan`
- `detector_playbooks_audit_log`

The new module is `tools/axxon_mcp_detector_playbooks.py`. It orchestrates existing
`detector_archive` descriptor/catalog reads and existing `operator` workflows. Public apply
and rollback require `AXXON_DETECTOR_PLAYBOOKS_APPROVE=1` plus the fixed playbook confirmation
tokens. Underlying operator plan IDs and operator confirmation tokens are stored internally and
are not exposed in public responses or audit logs.

No commit or push was performed. No fresh verifier agent was spawned because the builder
instruction explicitly said not to spawn additional agents and not to commit or push.

## Verification Commands

- RED: `python3.12 -m unittest tools/tests/test_axxon_mcp_detector_playbooks.py tools/tests/test_axxon_mcp_server.py`
  - Raw: `raw/red_detector_playbooks_and_server_pipefail.txt`
  - Result: expected failure before implementation, including missing `axxon_mcp_detector_playbooks` and missing server wiring/env approval.
- GREEN focused: `python3.12 -m unittest tools/tests/test_axxon_mcp_detector_playbooks.py tools/tests/test_axxon_mcp_server.py`
  - Raw: `raw/green_detector_playbooks_and_server.txt`
  - Result: `Ran 42 tests ... OK`
- Adjacent regressions: `python3.12 -m unittest tools/tests/test_axxon_mcp_detector_archive.py tools/tests/test_axxon_api_client_detector_archive.py tools/tests/test_axxon_mcp_operator.py`
  - Raw: `raw/adjacent_regressions.txt`
  - Result: `Ran 126 tests ... OK`
- Full suite: `python3.12 -m unittest discover -s tools/tests`
  - Raw: `raw/full_unittest.txt`
  - Result: `Ran 1156 tests ... OK`
- Static diff check: `git diff --check`
  - Raw: `raw/final_git_diff_check.txt`
  - Result: exit 0, no output.
- Tool/group count script:
  - Raw: `raw/tool_group_counts.txt`
  - Result: `tool_count=317`, `server_local_count=312`, `translator_tool_count=5`, `group_count=51`, detector playbooks tool count `8`.
- Coverage stability:
  - Raw: `raw/docs_coverage_stability.txt`
  - Result: `docs/COVERAGE.md unchanged`.
- Added-lines secret/proto/material scan:
  - Raw: `raw/secret_proto_scan_added_lines.txt`
  - Result: no AxxonSoft proto files, CA files/material, tickets, credentials, raw media, raw metadata payloads, biometric vectors, or license keys added.
- Git status:
  - Raw: `raw/final_git_status.txt`
  - Result: task changes plus the pre-existing untracked `docs/Axxon_One_Integration_APIs.postman_collection.json`.

## Acceptance Criteria

| AC | Status | Evidence |
| --- | --- | --- |
| AC1 Capability Group And Server Wiring | PASS | `tools/axxon_mcp_server.py` includes `detector_playbooks` in `CAPABILITY_GROUPS`, create_server dependency/enabled group, CLI flag, approval env, lazy main construction, and registration. Verified by `raw/green_detector_playbooks_and_server.txt` and `raw/tool_group_counts.txt`. |
| AC2 Stable Public Tool Surface | PASS | Exactly eight public detector playbook tools registered when enabled and absent when disabled. Verified by server tests and `raw/tool_group_counts.txt`. |
| AC3 Connection, Catalog, Schema Helper | PASS | Module tests cover env connection summary, non-env gap response, catalog gates/intents, schema delegation/augmentation, VisualElement preservation, and redaction. Verified by `raw/green_detector_playbooks_and_server.txt`. |
| AC4 Detector Family Matrix | PASS | `list_detector_playbooks` and schema responses include fallback/local, live/template/factory discovered, and fixture-needed GlobalTracker/RealtimeRecognizerExternal/TagAndTrack buckets. Verified by module tests in `raw/green_detector_playbooks_and_server.txt`. |
| AC5 Task-First Planning | PASS | Plans map to `create_av_detector_full`, `create_appdata_detector_full`, `update_detector_parameters`, `update_detector_visual_element`, `delete_detector`, `external_event_inject`, and `raise_periodical_event`; guidance/fixture intents are non-apply-ready. Verified by module tests. |
| AC6 Typed Geometry | PASS | Geometry planner resolves VisualElement descriptors and builds exact `value_rectangle`, `value_polyline`, `value_mask`, and `value_simple_polygon` payloads; mismatches reject before operator planning. Verified by module tests. |
| AC7 External Detector Events | PASS | Occasional and periodical event intents map to operator workflows, bound/strip unsafe tracklet content, classify noop rollback, and keep operator errors/status sanitized. Verified by module tests and adjacent operator regressions. |
| AC8 VMDA/AppData, Metadata, Heatmap Guidance | PASS | `preflight_vmda_appdata` and `metadata_vmda_heatmap_guidance` return non-mutating guidance with SceneDescription chain path, next tools, endpoint expectations, and caps. Verified by module tests. |
| AC9 Fixture-Gated Families | PASS | GlobalTracker, RealtimeRecognizerExternal, and TagAndTrack return fixture-needed, non-apply-ready plans; apply rejects without operator/live calls. Verified by module tests. |
| AC10 Approval Gates, Delegation, Verify, Rollback | PASS | Apply/rollback reject unknown, non-apply-ready, missing env, and bad confirmation; valid calls delegate internally with stored operator tokens; reapply/rerollback deterministic. Verified by module tests. |
| AC11 Sanitized Responses And Audit Trail | PASS | Recursive sanitizer redacts secret-like keys/values, raw payload markers, operator plan IDs, and operator confirmations from responses/audit. Verified by module tests and `raw/secret_proto_scan_added_lines.txt`. |
| AC12 TDD And Test Coverage | PASS | RED captured before production code in `raw/red_detector_playbooks_and_server_pipefail.txt`; new module tests and server tests pass in focused and full runs. |
| AC13 Documentation Updates And Coverage Stability | PASS | README/roadmap updated to 317 tools, 51 groups, 312 local + 5 translator, 1156 tests; added detector mutation playbooks; `docs/COVERAGE.md` unchanged. Verified by docs grep and `raw/docs_coverage_stability.txt`. |
| AC14 Evidence Artifacts | PASS | `evidence.md`, `evidence.json`, and raw artifacts exist under `.agent/tasks/phase-4-detector-playbooks/`. Raw artifacts cover RED/GREEN/full/adjacent tests, counts, coverage stability, scan, git status/diff, and no verifier/commit/push note. |
| AC15 Final Verification, Fresh Verifier, Commit, Push | UNKNOWN | Builder verification passed: full unittest and `git diff --check`. Fresh verifier agent, commit, and push were not run because the user explicitly instructed no additional agents and no commit/push. See `raw/no_commit_push_or_verifier_agent.txt`. |

## Changed Files

- `tools/axxon_mcp_detector_playbooks.py`
- `tools/axxon_mcp_server.py`
- `tools/tests/test_axxon_mcp_detector_playbooks.py`
- `tools/tests/test_axxon_mcp_server.py`
- `README.md`
- `docs/ALL_IN_ONE_VMS_API_ROADMAP.md`
- `docs/api-audit/mutation-playbooks/detector-parameters.md`
- `docs/api-audit/mutation-playbooks/external-events.md`

## Explicit Material Statement

No AxxonSoft proto files, CA files or CA material, tickets, credentials, raw media,
raw metadata payloads, biometric vectors, or license keys were added. The only
secret-like strings added are synthetic `SHOULD_NOT_LEAK` test fixtures used to prove
redaction behavior.
