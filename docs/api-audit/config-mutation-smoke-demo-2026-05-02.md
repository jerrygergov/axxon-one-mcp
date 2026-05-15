# Axxon One ChangeConfig Mutation Smoke

- Started: `2026-05-02T17:56:04.017538+00:00`
- Finished: `2026-05-02T17:56:40.662267+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

All created objects use `codex-temp-*` names and are removed before the tool exits.

## Summary

- PASS: 5
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `archive` | 3801 | added=['hosts/Server/MultimediaStorage.Gray'] changed_failed=0 removed_failed=0 |
| PASS | `camera` | 4421 | added=['hosts/Server/DeviceIpint.9608'] changed_failed=0 removed_failed=0 |
| PASS | `av_detector` | 13270 | created_and_removed=['hosts/Server/AVDetector.109', 'hosts/Server/AVDetector.110', 'hosts/Server/AVDetector.111'] |
| PASS | `appdata_detector` | 8995 | added=['hosts/Server/AppDataDetector.28'] readback=1 events=25 subject=hosts/Server/AppDataDetector.28/EventSupplier |
| PASS | `appdata_visual_element` | 5870 | added=['hosts/Server/AppDataDetector.29'] visual_element=hosts/Server/AppDataDetector.29/VisualElement.73bd2531-1e52-47fe-93b6-e25a31fa94ae readback_points=4 |

## Request Shapes Verified

- Add objects by sending `added[].uid=hosts/Server` and placing the new object in `added[].units[]`.
- Change objects with `changed[].uid=<generated uid>`, the unit `type`, and only the properties being changed.
- Remove objects with `removed[].uid=<generated uid>`.
- The generated UIDs from `ChangeConfigResponse.added` were used for all readback, change, and rollback steps.

## Object Families Verified

- Archive: `MultimediaStorage` with `display_name`, `color=Gray`, `storage_type=object`, and `day_depth=0`.
- Camera: `DeviceIpint` with `vendor=Virtual`, nested `model=Virtual several streams`, `display_name`, `display_id`, and `blockingConfiguration=false`.
- Parent detectors: `AVDetector` with nested `input=Video`, `camera_ref=<video AP>`, `streaming_id=<video AP>`, and detector values `SceneDescription`, `MotionDetection`, and `NeuroTracker`.
- Child detector: `AppDataDetector` with nested `input=TargetList`, `camera_ref=<video AP>`, `streaming_id=hosts/Server/AVDetector.1/SourceEndpoint.vmda`, and `detector=MoveInZone`.
- Child detector visual element: generated `VisualElement.*` was changed with `value_simple_polygon` on property `polyline`, then read back with 4 points.

## Event And Mask Verification

- The temporary child detector was read back through its `EventSupplier`; `EventHistoryService.ReadCount` found 25 `ET_DetectorEvent` records for that subject in the bounded verification window before rollback.
- The temporary visual element was read back as `Detection area (polygon)`, and the updated polygon contained the four requested normalized points.
