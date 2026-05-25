# Axxon One Detector Archive Smoke

- Started: `2026-05-25T19:42:41.642333+00:00`
- Finished: `2026-05-25T19:43:13.431162+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>`
- Mutation: `True`
- Archive maintenance no-op: `True`

## Summary

- PASS: 12
- WARN: 3
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `connect` | 610 | keys=['connected', 'mode', 'profile', 'profile_name'] |
| PASS | `analytics_fixture_report` | 9836 | tool=analytics_fixture_report keys=['available', 'evidence', 'fixtures', 'missing', 'notes', 'status', 'tool'] |
| PASS | `detector_kind_catalog` | 771 | tool=detector_kind_catalog keys=['by_unit_type', 'count', 'include_live', 'status', 'tool'] |
| PASS | `av_detector_schema` | 785 | tool=detector_parameter_schema keys=['detector_kind', 'fixtures', 'provenance', 'schema', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `appdata_detector_schema` | 778 | tool=detector_parameter_schema keys=['detector_kind', 'fixtures', 'provenance', 'schema', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `detector_config_get` | 224 | tool=detector_config_get keys=['config', 'detector_kind', 'detector_uid', 'snapshot_metadata', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements', 'writable_parameters'] |
| PASS | `detector_visual_elements` | 209 | tool=detector_visual_elements keys=['count', 'detector_kind', 'detector_uid', 'snapshot_metadata', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `metadata_schema_catalog` | 1401 | tool=metadata_schema_catalog keys=['endpoint_examples', 'notes', 'schema_source', 'schemas', 'status', 'tool'] |
| PASS | `metadata_sample_bounded` | 195 | tool=metadata_sample_bounded keys=['access_point', 'applied', 'count', 'frames', 'requested', 'status', 'tool'] |
| WARN | `archive_policy_get` | 1605 | Resolved descriptor did not expose archive policy fields; provide policy-like archive, recording, retention, or schedule descriptors. |
| PASS | `archive_management_status` | 1979 | tool=archive_management_status keys=['archive_access_point', 'disk_space', 'mutation_policy', 'status', 'tool', 'traits', 'volume_summary'] |
| WARN | `mutation_av_detector` | 8492 | keys=['create', 'rollback', 'rollback_verify', 'scalar_update', 'status', 'visual_update'] |
| PASS | `mutation_appdata_detector` | 3345 | keys=['apply', 'plan', 'rollback', 'rollback_verify', 'status', 'verify'] |
| WARN | `mutation_archive_policy` | 0 | No isolated codex archive/camera fixture was supplied; real archive policy update skipped. |
| PASS | `archive_maintenance_noop` | 1548 | keys=['access_point', 'noop_volume_id_len', 'noop_volume_id_prefix', 'results', 'status'] |
