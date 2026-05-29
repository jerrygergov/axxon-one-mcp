# Axxon One Detector Archive Smoke

- Started: `2026-05-29T13:51:14.016830+00:00`
- Finished: `2026-05-29T13:51:32.691055+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>`
- Mutation: `False`
- Archive maintenance no-op: `False`

## Summary

- PASS: 11
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `connect` | 401 | keys=['connected', 'mode', 'profile', 'profile_name'] |
| PASS | `analytics_fixture_report` | 10238 | tool=analytics_fixture_report keys=['available', 'evidence', 'fixtures', 'missing', 'notes', 'status', 'tool'] |
| PASS | `detector_kind_catalog` | 764 | tool=detector_kind_catalog keys=['by_unit_type', 'count', 'include_live', 'status', 'tool'] |
| PASS | `av_detector_schema` | 845 | tool=detector_parameter_schema keys=['detector_kind', 'fixtures', 'provenance', 'schema', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `appdata_detector_schema` | 765 | tool=detector_parameter_schema keys=['detector_kind', 'fixtures', 'provenance', 'schema', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `detector_config_get` | 237 | tool=detector_config_get keys=['config', 'detector_kind', 'detector_uid', 'snapshot_metadata', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements', 'writable_parameters'] |
| PASS | `detector_visual_elements` | 203 | tool=detector_visual_elements keys=['count', 'detector_kind', 'detector_uid', 'snapshot_metadata', 'source_type', 'status', 'tool', 'unit_type', 'visual_elements'] |
| PASS | `metadata_schema_catalog` | 1432 | tool=metadata_schema_catalog keys=['endpoint_examples', 'notes', 'schema_source', 'schemas', 'status', 'tool'] |
| PASS | `metadata_sample_bounded` | 186 | tool=metadata_sample_bounded keys=['access_point', 'applied', 'count', 'frames', 'requested', 'status', 'tool'] |
| PASS | `archive_policy_get` | 1650 | tool=archive_policy_get keys=['archive_bindings', 'confidence', 'descriptor', 'descriptor_source', 'notes', 'recording_properties', 'retention_properties', 'schedule_properties', 'status', 'target', 'tool'] |
| PASS | `archive_management_status` | 1947 | tool=archive_management_status keys=['archive_access_point', 'disk_space', 'mutation_policy', 'status', 'tool', 'traits', 'volume_summary'] |
