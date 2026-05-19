# Phase 5E - Detectors, Analytics, Archive Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task ends with a commit.

**Goal:** Ship Phase 5E as a focused detector/archive capability set: detector kind catalog, parameter schemas, detector config reads, metadata schemas/samples, archive policy/status reads, full detector authoring workflows, reversible detector edits, and high-risk archive maintenance workflows with strict fixture gates.

**Architecture:** Add `tools/axxon_mcp_detector_archive.py` for read-only Phase 5E tools. Extend `tools/axxon_api_client.py` with thin wrappers only where repeated RPC dispatch would otherwise leak transport details. Extend `tools/axxon_mcp_operator.py` with guarded workflows. Register the read module behind `--enable-detector-archive`; all mutations stay behind the existing operator flag and env approval, with an extra archive-maintenance env gate.

**Tech Stack:** Python 3.11+, `AxxonApiClient`, `unittest`, FastMCP. No new third-party dependencies.

---

## Source-of-truth references

- Spec: `docs/superpowers/specs/2026-05-19-phase-5e-detectors-archive-policies-design.md`.
- Existing live pattern: `tools/axxon_mcp_live.py`.
- Existing Phase 5 read-module patterns: `tools/axxon_mcp_view.py`, `tools/axxon_mcp_alarms.py`, `tools/axxon_mcp_view_objects.py`.
- Existing operator workflows: `tools/axxon_mcp_operator.py`.
- Existing detector smokes: `tools/axxon_config_model_study.py`, `tools/axxon_config_mutation_smoke.py`.
- Existing archive smokes: `tools/axxon_archive_management_preflight.py`, `tools/axxon_archive_management_noop_smoke.py`.
- Live stand for verification: `<demo-host>` with credentials supplied only through `AXXON_*` env vars.

---

## File structure

| Path | Purpose |
| --- | --- |
| `tools/axxon_mcp_detector_archive.py` | New Phase 5E read module and normalizers. |
| `tools/tests/test_axxon_mcp_detector_archive.py` | Offline unit tests for read tools. |
| `tools/tests/test_axxon_api_client_detector_archive.py` | Thin wrapper dispatch tests. |
| `tools/axxon_api_client.py` | Wrapper additions for Phase 5E RPCs. |
| `tools/axxon_mcp_operator.py` | New detector/archive workflows. |
| `tools/tests/test_axxon_mcp_operator.py` | Workflow tests appended. |
| `tools/axxon_mcp_server.py` | `--enable-detector-archive` registration. |
| `tools/tests/test_axxon_mcp_server.py` | Registration tests appended. |
| `tools/axxon_detector_archive_smoke.py` | Live read + guarded mutation smoke. |
| `docs/api-audit/phase-5e-detector-archive-smoke-latest.md` | Sanitized evidence. |
| `docs/api-audit/pdf-gap-coverage-matrix.md` | Phase 5E row/updates. |
| `README.md`, `STATUS.md` | Handoff and operator documentation updates. |

---

## Constants

Place these in `tools/axxon_mcp_detector_archive.py`:

```python
DETECTOR_LIST_LIMIT_CAP = 200
METADATA_SAMPLE_TIMEOUT_DEFAULT = 5.0
METADATA_SAMPLE_TIMEOUT_CAP = 30.0
METADATA_SAMPLE_LIMIT_DEFAULT = 20
METADATA_SAMPLE_LIMIT_CAP = 200
SENSITIVE_PROPERTY_TOKENS = ("password", "token", "secret", "certificate", "private_key", "serial", "license")
DETECTOR_UNIT_TYPES = ("AVDetector", "AppDataDetector")
KNOWN_DETECTOR_KINDS = {
    "AVDetector": ("MotionDetection", "SceneDescription", "NeuroTracker"),
    "AppDataDetector": ("MoveInZone", "OneLineCrossing", "LongInZone", "LostObject", "AbandonedObject"),
}
```

Archive maintenance workflows use confirmation tokens:

- `CONFIRM-archive_format_volume`
- `CONFIRM-archive_reindex`
- `CONFIRM-archive_cancel_reindex`

and require `AXXON_ARCHIVE_MAINTENANCE_APPROVE=1`.

---

## Task 1: Add Phase 5E API wrappers

**Files:**
- Modify: `tools/axxon_api_client.py`
- Create: `tools/tests/test_axxon_api_client_detector_archive.py`

- [ ] Write failing wrapper tests for:
  - `batch_get_factories(factory_ids)`
  - `list_similar_units(unit_uid)`
  - `acquire_dynamic_parameters(unit_uid, property_path=None)`
  - `acquire_device_additional_data(unit_uid)`
  - `archive_format_volumes(access_point, volume_ids)`
  - `archive_reindex(access_point, volume_ids, full=True)`
  - `archive_cancel_reindex(access_point, volume_ids)`
  - `archive_probe_volume(path_or_volume_hint)`
- [ ] Run `cd tools && python3.12 -m unittest tests.test_axxon_api_client_detector_archive -v` and verify failures.
- [ ] Implement minimal thin wrappers using existing `http_grpc`, direct stubs only where the existing archive code already uses stubs.
- [ ] Re-run the focused test.
- [ ] Commit: `feat: add detector archive api wrappers`.

## Task 2: Scaffold detector/archive read module

**Files:**
- Create: `tools/axxon_mcp_detector_archive.py`
- Create: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for module import and `detector_archive_connect_axxon_profile`.
- [ ] Implement dataclass skeleton with `client_factory`, `config_factory`, `ensure_client`, and public config summary redaction.
- [ ] Add normalizer helpers for sensitive property redaction.
- [ ] Run `cd tools && python3.12 -m unittest tests.test_axxon_mcp_detector_archive -v`.
- [ ] Commit: `feat: scaffold detector archive read tools`.

## Task 3: Implement detector kind catalog

**Files:**
- Modify: `tools/axxon_mcp_detector_archive.py`
- Modify: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for `detector_kind_catalog(include_live=True)` with fake live units, template/factory descriptors, and known fallback kinds.
- [ ] Implement catalog merging from:
  - known detector kinds,
  - live detector `input.detector` enum constraints,
  - template/factory descriptor data where available.
- [ ] Ensure output includes provenance and fixture requirements per kind.
- [ ] Run focused tests.
- [ ] Commit: `feat: add detector kind catalog`.

## Task 4: Implement detector parameter schemas

**Files:**
- Modify: `tools/axxon_mcp_detector_archive.py`
- Modify: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for nested descriptor flattening, enum/range capture, visual element detection, and sensitive property redaction.
- [ ] Implement `detector_parameter_schema(unit_type, detector_kind)`.
- [ ] Return JSON-schema-like property descriptors preserving Axxon value kinds and nested paths.
- [ ] Return `fixture-needed` when the requested kind cannot be resolved from known/live/template sources.
- [ ] Run focused tests.
- [ ] Commit: `feat: add detector parameter schemas`.

## Task 5: Implement detector config and visual reads

**Files:**
- Modify: `tools/axxon_mcp_detector_archive.py`
- Modify: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for `detector_config_get(detector_uid)` and `detector_visual_elements(detector_uid)`.
- [ ] Implement sanitized config reads using `ConfigurationService.ListUnits`.
- [ ] Include writable parameter summaries, child visual element summaries, and snapshot metadata needed by operator rollback.
- [ ] Run focused tests.
- [ ] Commit: `feat: add detector config read tools`.

## Task 6: Implement metadata schema catalog and bounded sample

**Files:**
- Modify: `tools/axxon_mcp_detector_archive.py`
- Modify: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for `metadata_schema_catalog()` and cap enforcement in `metadata_sample_bounded`.
- [ ] Implement schema catalog from proto descriptors plus live metadata endpoint examples.
- [ ] Reuse the existing bounded `MetadataService.PullMetadata` strategy from `AxxonMcpLive`.
- [ ] Clamp timeout and limit and report applied caps.
- [ ] Run focused tests.
- [ ] Commit: `feat: add metadata schema tools`.

## Task 7: Implement archive policy/status reads

**Files:**
- Modify: `tools/axxon_mcp_detector_archive.py`
- Modify: `tools/tests/test_axxon_mcp_detector_archive.py`

- [ ] Write failing tests for `archive_policy_get`, `archive_management_status`, `archive_volume_probe`, and `analytics_fixture_report`.
- [ ] Implement policy/config discovery from domain inventory, `ConfigurationService.ListUnits`, and archive traits/volume/disk APIs.
- [ ] Return `fixture-needed` instead of guessed archive policy mutations when descriptors are absent.
- [ ] Implement archive volume probe as fixture-aware and non-mutating.
- [ ] Run focused tests.
- [ ] Commit: `feat: add archive policy read tools`.

## Task 8: Add detector full-create workflows

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] Write failing tests for `_build_create_av_detector_full_plan` and `_build_create_appdata_detector_full_plan`.
- [ ] Implement plans with `caller_owns_lifecycle: True`, schema provenance, source bindings, and rollback via `remove_created_uids`.
- [ ] Reuse existing AV/AppData payload builders where possible, extending them to accept full parameter trees.
- [ ] Add registry entries.
- [ ] Run `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`.
- [ ] Commit: `feat: add detector full create workflows`.

## Task 9: Add reversible detector update/delete workflows

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] Write failing tests for `update_detector_parameters`, `update_detector_visual_element`, and `delete_detector`.
- [ ] Implement plan diff rendering and snapshot capture fields.
- [ ] Implement apply/verify/rollback branches that restore captured snapshots.
- [ ] Keep `set_unit_properties` unchanged as a low-level existing workflow.
- [ ] Run focused operator tests.
- [ ] Commit: `feat: add reversible detector workflows`.

## Task 10: Add archive policy and maintenance workflows

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] Write failing tests for `archive_policy_update`, `archive_format_volume`, `archive_reindex`, and `archive_cancel_reindex`.
- [ ] Implement archive policy update with snapshot rollback and descriptor-backed fields only.
- [ ] Implement archive maintenance env gate `AXXON_ARCHIVE_MAINTENANCE_APPROVE=1`.
- [ ] Refuse real volume ids unless a fixture/safe-volume declaration is present.
- [ ] Allow no-op/nonexistent-volume dispatch for smoke verification.
- [ ] Run focused operator tests.
- [ ] Commit: `feat: add archive maintenance workflows`.

## Task 11: Register MCP tools

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

- [ ] Write failing registration test for `--enable-detector-archive`.
- [ ] Add `register_detector_archive_tools`.
- [ ] Register all Phase 5E read tools, not operator workflows (operator workflows continue through `plan_operator_workflow`).
- [ ] Run focused server tests.
- [ ] Commit: `feat: register detector archive tools`.

## Task 12: Add live smoke

**Files:**
- Create: `tools/axxon_detector_archive_smoke.py`
- Create: `tools/tests/test_axxon_detector_archive_smoke.py`

- [ ] Write failing tests for CLI approval handling, cap defaults, and evidence sanitization helpers.
- [ ] Implement read-only smoke flow from the spec.
- [ ] Implement `--mutation` mode requiring `AXXON_OPERATOR_APPROVE=1`.
- [ ] Implement archive maintenance no-op mode using `codex-nonexistent-*` volume ids.
- [ ] Run focused smoke tests.
- [ ] Commit: `feat: add detector archive live smoke`.

## Task 13: Run live verification and commit sanitized evidence

**Files:**
- Modify: `docs/api-audit/phase-5e-detector-archive-smoke-latest.md`
- Modify: `docs/api-audit/phase-5e-detector-archive-smoke-latest.json`

- [ ] Run the read-only live smoke against `<demo-host>`.
- [ ] Run mutation smoke for detector create/update/rollback if the fixture discovery finds a video source access point.
- [ ] Run archive no-op maintenance verification only against a nonexistent test volume unless a dedicated fixture is explicitly provided.
- [ ] Sanitize evidence: host -> `<demo-host>`, no passwords, no bearer tokens.
- [ ] Inspect the diff for secrets with `rg -n "100\\.76\\.150\\.18|Bearer |root"` on changed evidence files and fix any hit.
- [ ] Commit: `test: add phase 5e live smoke evidence`.

## Task 14: Update docs and coverage matrix

**Files:**
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `README.md`
- Modify: `STATUS.md`
- Modify: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md`

- [ ] Add Phase 5E coverage row(s) and link the live evidence.
- [ ] Document `--enable-detector-archive` and Phase 5E operator workflows.
- [ ] Update roadmap status and next concrete step.
- [ ] Run `python3.12 -m unittest discover -s tools/tests`.
- [ ] Commit: `docs: document phase 5e detector archive coverage`.

## Task 15: Final verification

**Files:** none expected

- [ ] Run `python3.12 -m unittest discover -s tools/tests`.
- [ ] Run a final secret scan over changed docs/evidence.
- [ ] Ensure `git status --short` is clean.
- [ ] Commit only if verification required tracked metadata changes. Otherwise, no commit.

---

## Live command template

Use env vars, not CLI secrets:

```bash
export AXXON_HOST=<demo-host>
export AXXON_HTTP_URL=http://<demo-host>
export AXXON_USERNAME=<demo-user>
export AXXON_PASSWORD=<redacted>
export AXXON_TLS_CN=<your-tls-cn>
export AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt

python3.12 tools/axxon_detector_archive_smoke.py

AXXON_OPERATOR_APPROVE=1 \
python3.12 tools/axxon_detector_archive_smoke.py --mutation

AXXON_OPERATOR_APPROVE=1 \
AXXON_ARCHIVE_MAINTENANCE_APPROVE=1 \
python3.12 tools/axxon_detector_archive_smoke.py --archive-maintenance-noop
```

Do not commit output until it is sanitized.
