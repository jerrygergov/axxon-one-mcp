# Phase 5E - Detectors, Analytics, Archive Policies Design

**Date:** 2026-05-19
**Status:** Draft for implementation
**Spec type:** Phase implementation spec (one of seven from `2026-05-16-axxon-mcp-full-coverage-roadmap.md`)

## 1. Goal

Expose detector and analytics configuration as first-class MCP tools, then promote the already-studied archive policy and archive maintenance surfaces into guarded operator workflows.

After 5E ships:

- Customers can ask for a detector kind, parameter schema, and safe configuration plan without reading raw `ConfigurationService` descriptors.
- Operators can create persistent AVDetector and AppDataDetector units with full parameter trees, verify them through live inventory, and roll them back cleanly.
- Detector parameter and visual-element edits are snapshot-backed, diff-rendered, ETag/config-snapshot guarded where the API exposes the data, and reversible.
- Archive policy inspection is available as a read tool. Archive policy updates are gated, snapshot-backed, and fixture-aware.
- Archive maintenance RPCs (`FormatVolumes`, `Reindex`, `CancelReindex`, plus `ProbeVolume` where available) are exposed only behind high-risk safety gates and default to no-op/nonexistent-volume verification on the demo stand.

## 2. Source-of-truth references

- Roadmap: `docs/superpowers/specs/2026-05-16-axxon-mcp-full-coverage-roadmap.md` section 5E.
- Existing live detector discovery: `tools/axxon_mcp_live.py` (`list_detectors`, `list_appdata_detectors`, `list_detector_kinds`, `find_metadata_endpoints`, `pull_metadata_bounded`).
- Existing operator patterns: `tools/axxon_mcp_operator.py` (`temp_av_detector`, `temp_appdata_detector`, `set_unit_properties`, persistent workflow registry, audit log).
- Existing detector evidence:
  - `tools/axxon_config_model_study.py`
  - `tools/axxon_config_mutation_smoke.py`
  - `docs/api-audit/config-model-study-latest.md`
  - `docs/api-audit/config-mutation-smoke-latest.md`
  - `docs/api-audit/mutation-playbooks/detector-parameters.md`
- Existing metadata and event evidence:
  - `tools/metadata_tracker_stream.py` (if present in a worktree history) and `AxxonMcpLive.pull_metadata_bounded`
  - `tools/axxon_external_event_smoke.py`
  - `docs/api-audit/external-event-smoke-latest.md`
  - `docs/api-audit/external-event-detectorex-20260508.md`
- Existing archive evidence:
  - `tools/axxon_archive_management_preflight.py`
  - `tools/axxon_archive_management_noop_smoke.py`
  - `docs/api-audit/archive-management-preflight-latest.md`
  - `docs/api-audit/archive-management-noop-smoke-latest.md`
  - `docs/api-audit/mutation-playbooks/archive-management.md`
- Proto/catalog surfaces to cover:
  - `ConfigurationService`: detector unit reads, `ChangeConfig`, templates, factories, similar units.
  - `DynamicParametersService`: dynamic parameter discovery.
  - `MetadataService`: bounded VMDA/metadata stream sampling.
  - `ExternalDetectorService`: external event/tracklet injection, already used by operator workflows.
  - `ArchiveService` and `ArchiveVolumeService`: traits, volumes, disk space, format/reindex/cancel, probe.
  - Analytics-adjacent fixture surfaces: `GlobalTrackerService`, `HeatMapService`, `RealtimeRecognizerService`.

## 3. Tool inventory

### 3.1 Read tools (behind `--enable-detector-archive`)

These tools live in a new focused module, `tools/axxon_mcp_detector_archive.py`. They reuse `AxxonApiClient` and follow the dataclass-with-factories pattern used by `axxon_mcp_live.py`, `axxon_mcp_view.py`, `axxon_mcp_alarms.py`, and `axxon_mcp_view_objects.py`.

| Tool | Primary API | Behavior |
| --- | --- | --- |
| `detector_archive_connect_axxon_profile(profile="env")` | auth/config | Connects using env-only credentials and returns a public config summary. |
| `detector_kind_catalog(include_live=True)` | `ConfigurationService.ListUnits`, `ListTemplates`, `BatchGetFactories` | Returns AVDetector/AppDataDetector kinds with source type, known parameters, fixture status, and provenance. Extends the existing `list_detector_kinds` shape. |
| `detector_parameter_schema(unit_type, detector_kind)` | `ConfigurationService.ListUnits`, `ListTemplates`, factories | Returns JSON-schema-like writable parameter descriptors for a detector kind. Redacts sensitive fields and preserves nested property paths. |
| `detector_config_get(detector_uid)` | `ConfigurationService.ListUnits` | Returns sanitized full detector config, writable parameters, visual elements, config metadata, and rollback snapshot key. |
| `detector_visual_elements(detector_uid)` | `ConfigurationService.ListUnits` | Lists editable visual child units such as masks, zones, lines, and rectangles. |
| `metadata_schema_catalog()` | proto descriptors + live endpoints | Returns VMDA/TargetList/tracklet/event metadata field shapes and known endpoint examples. |
| `metadata_sample_bounded(access_point, timeout_s, limit)` | `MetadataService.PullMetadata` | Bounded metadata sample with timeout and item caps. Never streams indefinitely. |
| `archive_policy_get(camera_or_archive)` | `DomainService`, `ConfigurationService`, `ArchiveService` | Returns recording/archive binding and policy-like fields the API exposes for the target camera/archive. |
| `archive_management_status()` | `ArchiveService.GetArchiveTraits`, `GetVolumesState`, `GetDiskSpace` | Read-only preflight summary suitable for deciding whether maintenance workflows are allowed. |
| `archive_volume_probe(path_or_volume_hint)` | `ArchiveVolumeService.ProbeVolume` | Fixture-aware read/probe. Returns `fixture-needed` unless a safe path/volume fixture is supplied. |
| `analytics_fixture_report()` | Global tracker, heatmap, recognizer reads | Reports which advanced analytics fixtures exist and which Phase 5E tools can live-verify on this stand. |

### 3.2 Operator workflows (behind `--enable-operator` + approval)

All workflows use the existing `OperatorRegistry` plan/apply/verify/rollback path and audit log. Detector mutations require `AXXON_OPERATOR_APPROVE=1`. Archive maintenance additionally requires `AXXON_ARCHIVE_MAINTENANCE_APPROVE=1` and an explicit fixture declaration unless the workflow uses a `codex-nonexistent-*` no-op target.

| Workflow | Wraps | Persistence | Rollback |
| --- | --- | --- | --- |
| `create_av_detector_full` | `ConfigurationService.ChangeConfig(added=AVDetector)` | persistent, caller-owned | remove created UID |
| `create_appdata_detector_full` | optional SceneDescription AVDetector + `AppDataDetector` | persistent, caller-owned | remove created UIDs in reverse order |
| `update_detector_parameters` | `ConfigurationService.ChangeConfig(changed=...)` | persistent state mutate | restore captured property snapshot |
| `update_detector_visual_element` | `ConfigurationService.ChangeConfig(changed=VisualElement)` | persistent state mutate | restore captured visual snapshot |
| `delete_detector` | `ConfigurationService.ChangeConfig(removed=...)` | persistent delete | restore captured detector snapshot |
| `archive_policy_update` | `ConfigurationService.ChangeConfig(changed=...)` for archive/camera policy fields | persistent state mutate | restore captured archive/camera snapshot |
| `archive_format_volume` | `ArchiveService.FormatVolumes` | high-risk maintenance | no automatic undo; fixture-only |
| `archive_reindex` | `ArchiveService.Reindex` | high-risk maintenance | `archive_cancel_reindex` if this workflow started it |
| `archive_cancel_reindex` | `ArchiveService.CancelReindex` | high-risk maintenance | no-op after cancel |

`set_unit_properties` remains available as a low-level escape hatch, but Phase 5E should prefer `update_detector_parameters` because it captures a pre-apply snapshot and offers rollback.

## 4. Data contracts

### 4.1 Detector schema shape

`detector_parameter_schema` returns a stable, sanitized schema:

```json
{
  "status": "ok",
  "unit_type": "AVDetector",
  "detector_kind": "MotionDetection",
  "source_type": "Video",
  "schema": {
    "type": "object",
    "properties": {
      "input.detector": {
        "value_kind": "value_string",
        "readonly": false,
        "enum": ["MotionDetection"],
        "required": true
      }
    }
  },
  "visual_elements": [
    {"unit_type": "VisualElement", "editable_shapes": ["value_simple_polygon", "value_rectangle"]}
  ],
  "provenance": ["live-unit", "template", "known-catalog"],
  "fixtures": {"required": ["video_source_ap"], "missing": []}
}
```

The schema is intentionally JSON-schema-like rather than strict JSON Schema. Axxon descriptors expose value kinds, nested property bags, ranges, enums, and shape fields that do not map cleanly to generic JSON Schema without losing API-specific information.

### 4.2 Detector create plan shape

Persistent detector creation plans include:

- `caller_owns_lifecycle: true`
- `expected.display_name`
- `expected.detector`
- `expected.video_source_ap`
- `expected.vmda_source_ap` for AppDataDetector
- `schema_source` showing which schema produced the payload
- `diff` containing only the properties to be added

The apply path records created UIDs. Verify reads the created unit and confirms detector kind, source binding, and display name. Rollback removes all created UIDs in reverse order.

### 4.3 Archive policy shape

Archive policy read/update is fixture-aware because Axxon installations expose archive policy fields through configuration units differently by version and installation shape. The read tool returns:

```json
{
  "status": "ok",
  "target": "hosts/.../DeviceIpint.1",
  "archive_bindings": [],
  "recording_properties": [],
  "retention_properties": [],
  "schedule_properties": [],
  "confidence": "observed-live|partial|fixture-needed"
}
```

If a policy field cannot be found safely, the tool returns `fixture-needed` with the exact missing object or descriptor, not a guessed mutation payload.

## 5. Safety rules

- Read-only tools are enabled separately from operator workflows via `--enable-detector-archive`.
- Mutations require `--enable-operator`, `AXXON_OPERATOR_APPROVE=1`, and per-workflow confirmation tokens.
- Archive maintenance requires the additional env gate `AXXON_ARCHIVE_MAINTENANCE_APPROVE=1`.
- Archive maintenance plans refuse real volume ids unless `params.fixture_id` or `params.safe_volume_id` is present and the preflight snapshot marks it as isolated/test-owned.
- Metadata reads enforce timeout and item caps. The default is `timeout_s=5`, `limit=20`; max is `timeout_s=30`, `limit=200`.
- Sensitive descriptor fields are redacted by property id tokens: password, token, secret, certificate, private_key, serial, license.
- Evidence must replace the demo host with `<demo-host>` and must not include passwords or bearer tokens.
- Archive maintenance evidence on the shared demo stand should default to no-op/nonexistent-volume dispatch unless a dedicated storage fixture is provided.

## 6. Module and file layout

| Path | Purpose |
| --- | --- |
| `tools/axxon_mcp_detector_archive.py` | New read-only Phase 5E module and normalizers. |
| `tools/axxon_api_client.py` | Add wrappers for dynamic parameters, factories/similar units, archive probe/maintenance, and detector config helpers where useful. |
| `tools/axxon_mcp_operator.py` | Add detector full-create/update/delete and archive policy/maintenance workflows. |
| `tools/axxon_mcp_server.py` | Register `--enable-detector-archive` tools. |
| `tools/axxon_detector_archive_smoke.py` | Live read smoke plus guarded mutation/no-op maintenance smoke. |
| `tools/tests/test_axxon_mcp_detector_archive.py` | Offline read-module tests. |
| `tools/tests/test_axxon_api_client_detector_archive.py` | Wrapper dispatch tests. |
| `tools/tests/test_axxon_mcp_operator.py` | Append operator workflow tests. |
| `tools/tests/test_axxon_mcp_server.py` | Registration flag tests. |
| `docs/api-audit/phase-5e-detector-archive-smoke-latest.md` | Sanitized live evidence. |

## 7. Live verification strategy

Default smoke mode is read-only:

1. Connect using env-only credentials.
2. Discover detector kind catalog.
3. Build at least one AVDetector schema (`MotionDetection` preferred).
4. Build at least one AppDataDetector schema (`MoveInZone` preferred).
5. Inspect an existing detector config if present.
6. List visual elements for the detector or report `fixture-needed`.
7. Catalog metadata schemas and pull a bounded metadata sample if a VMDA endpoint exists.
8. Read archive policy/config for the first camera/archive.
9. Run archive management status preflight.
10. Run analytics fixture report.

Mutation smoke mode requires approval:

1. Create a temporary persistent AVDetector with a `codex-` name, verify it, update one reversible scalar parameter, verify readback, restore the snapshot, then rollback/remove.
2. Create a temporary persistent AppDataDetector. If no VMDA endpoint is supplied, chain-create a SceneDescription AVDetector, verify both, then rollback/remove both.
3. Exercise visual-element update only if the created detector exposes a writable visual child; otherwise record `fixture-needed`.
4. Run archive policy update only against an isolated `codex-` archive/camera fixture. If unavailable, record `fixture-needed`.
5. Run archive maintenance no-op using a `codex-nonexistent-*` volume id. Real format/reindex is skipped unless a dedicated storage fixture is explicitly supplied.

## 8. Acceptance

- `detector_parameter_schema` can generate the payload used by `create_av_detector_full` and `create_appdata_detector_full`.
- Created detectors are visible through existing `list_detectors` / `list_appdata_detectors` and through `detector_config_get`.
- Parameter and visual updates are diff-rendered before apply and restore the captured snapshot on rollback.
- Archive policy updates never guess fields. They either apply a descriptor-backed diff or return `fixture-needed`.
- Archive maintenance workflows refuse real volume ids without the extra maintenance gate and fixture proof.
- Live smoke against `<demo-host>` produces sanitized evidence under `docs/api-audit/phase-5e-detector-archive-smoke-latest.md`.
- Full unit suite remains green with `python3.12 -m unittest discover -s tools/tests`.

## 9. Explicitly deferred

- PTZ/TagAndTrack hardware control remains Phase 5B and fixture-gated.
- Security, users, roles, schedules, license, and system health remain Phase 5F.
- Realtime recognizer list mutation, global tracker profile mutation, and heatmap build mutation may be cataloged as analytics fixture gaps in 5E, but full authoring is deferred unless live fixtures prove a safe rollback path during implementation.
