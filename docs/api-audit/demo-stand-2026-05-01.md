# Demo Stand API Evidence - 2026-05-01

This page records sanitized findings from the richer Axxon One demo stand used to expand the API book.

Credentials, bearer tokens, license keys, serial numbers, and full license plate values are intentionally omitted.

## Target

- HTTP API: `http://<demo-host>:80`
- Direct gRPC: `<demo-host>:20109`
- Node name: `Server`
- TLS CN override: `Server`
- Version: `3.0.0.46`
- Temporary certificate used during testing: `/tmp/axxon-demo-server.crt`
- Certificate subject CN: `Server`
- Certificate issuer CN: `api.ngp Root CA`
- Certificate SHA256 fingerprint: `FF:7D:24:92:ED:0D:2C:28:E4:95:3E:F3:30:E7:6E:01:2D:94:B0:00:82:BC:5A:AD:02:F7:97:82:36:B7:29:0A`

Use environment variables for credentials:

```bash
export AXXON_HOST=<demo-host>
export AXXON_GRPC_PORT=20109
export AXXON_HTTP_PORT=80
export AXXON_HTTP_URL=http://<demo-host>:80
export AXXON_TLS_CN=<your-tls-cn>
export AXXON_CA=/tmp/axxon-demo-server.crt
export AXXON_USERNAME=root
export AXXON_PASSWORD='<password>'
```

## Sweep Summary

Reports were generated under `/tmp/axxon-demo-api-test-runs` and `/tmp/axxon-demo-api-audit` to avoid committing target-specific raw output.

| Probe | Result |
| --- | --- |
| Comprehensive probe | PASS=23, WARN=0, FAIL=1 |
| Direct gRPC read-only sweep | PASS=119, WARN=30, FAIL=0 |
| HTTP `/grpc` sweep | PASS=64, WARN=11, FAIL=0 |
| HTTP `/v1` sweep | PASS=67, WARN=11, FAIL=0 |
| Legacy HTTP read sweep | PASS=6, WARN=12, FAIL=0 |
| Bounded media/snapshot smoke | PASS=0, WARN=6, FAIL=0 |
| Bounded subscription smoke | PASS=1, WARN=0, SKIP=0, FAIL=0 |
| Archive search smoke | PASS=3, WARN=0, SKIP=0, FAIL=0 |
| Configuration detail sweep | PASS=5, WARN=0, FAIL=0 |
| Fixture discovery | FOUND=2, MISSING=5, WARN=0 |

The original comprehensive probe failure was `MetadataService.PullMetadata(VMDA)` with no samples from the generic endpoint choice. Active candidate selection now picks `hosts/Server/AVDetector.1/SourceEndpoint.vmda`; a focused run returned a live sample with 21 tracklets.

Media and subscription notes:

- Legacy media and snapshot endpoints were byte-limited to 1 MB per request. Live/snapshot paths returned HTTP 403 on the demo stand; archive media/frame paths returned HTTP 401.
- WebSocket camera-event subscription was skipped because `websocket-client` is not installed in the probe venv.
- gRPC `DomainNotifier.PullEvents` reached the server but returned no events before the 10 second deadline.
- Archive search smoke verified `ReadLprEvents` dispatch against camera `LPR + MMR` with a redacted predicate, VMDA scheme enumeration, and `HeatMapService.ExecuteHeatmapQuery`; no plate values or raw image bytes were stored.
- Configuration detail sweep verified template, macro, user/role, map, and detector read groups. Security data was reduced to counts and shapes.
- Fixture discovery found map fixtures and detector/VMDA fixtures. It did not find PTZ, control panel, water level, or export agent fixtures on the demo stand. Device templates were later covered by a controlled temporary-template lifecycle smoke.
- Device-template mutation smoke created an isolated virtual camera, created and edited a `codex-*` template, assigned and unassigned it, verified `assigned_templates` readback, removed the template, verified `BatchGetTemplates.not_found`, and removed the camera.

## Inventory

- Nodes: 1
- Cameras: 33
- Archives: 14
- Components: 200
- Main archive AP: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`

### Cameras

| ID | Camera | Enabled |
| --- | --- | --- |
| 1 | `Tracker` | true |
| 2 | `Pose detection` | true |
| 3 | `Sim Search 1` | true |
| 4 | `Sim Search 2` | true |
| 5 | `Privacy Masking` | true |
| 6 | `Sim Search 3` | true |
| 7 | `Sim Search 4` | true |
| 8 | `Permanent masking` | true |
| 9 | `Face` | true |
| 10 | `LPR + MMR` | true |
| 11 | `No Mask` | true |
| 13 | `PPE` | true |
| 14 | `Immersion 1` | null |
| 15 | `Immersion 2` | null |
| 16 | `Immersion 3` | null |
| 17 | `Fire Smoke` | true |
| 29 | `Crowd detection` | true |
| 32 | `Meta Detector` | true |
| 33 | `Counter` | true |
| 34 | `Visitors` | true |
| 36 | `Multicamera Tracking 1` | true |
| 37 | `Multicamera Tracking 2` | true |
| 38 | `Traffic Analyzer RR 1` | true |
| 39 | `Traffic Analyzer RR 2` | true |
| 40 | `Traffic Analyzer RR 3` | true |
| 41 | `Multicamera Tracking 3` | true |
| 42 | `Fight` | true |
| 43 | `Door` | true |
| 44 | `Real Traffic Monitor` | true |
| 45 | `Parking Lot Occupancy` | true |
| 46 | `Cyclists` | true |
| 47 | `Bulltet` | null |
| 48 | `Dome` | null |

### Archives

The demo stand has 13 embedded storage APs and one shared AliceBlue archive:

- `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- Embedded storage on cameras `5`, `11`, `32`, `33`, `34`, `38`, `39`, `40`, `42`, `43`, `44`, `47`, and `48`.

## Event Fixture Findings

The general event search over the last 24 hours returned 24,257 events. The latest sample mixed detector events and alert state events.

### Camera `Face`

Command shape:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera Face --limit 5 --json
```

Findings:

- Total count in 24 hours: 8,661.
- Categories: `face`.
- Event types: `ET_DetectorEvent`, `ET_AlertState`.
- Detector examples:
  - `93.Face detector VA`, event `faceAppeared`, text `Face detected`.
  - `0.Real-time recognizer`, event `listed_face_detected`, text `Check in face lists`.
  - Alert state close events for the same camera.
- Useful for: face detector, realtime recognizer, and alarm examples.

### Camera `LPR + MMR`

Command shape:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'LPR + MMR' --limit 5 --json
```

Findings:

- Total count in 24 hours: 4,244.
- Categories: `lpr`.
- Event type: `ET_DetectorEvent`.
- Detector examples:
  - `74.License plate recognition RR`, event `plateRecognized`, text `Recognized LP`.
  - `74.License plate recognition RR`, event `plateUnrecognized`, text `Unrecognized LP`.
  - `0.Real-time recognizer`, event `listed_lpr_detected`, text `Check in LP lists`.
  - `14.Vehicle_OUT`, event `oneLine`, text `Object crossing line detected`.
- Plate values were present in raw output and are redacted from durable docs.
- Useful for: LPR, MMR vehicle attributes, and recognizer-list examples.

### Camera `Traffic Analyzer RR 1`

Command shape:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'Traffic Analyzer RR 1' --limit 5 --json
```

Findings:

- Total count in 24 hours: 4,525.
- Categories: `vehicle`.
- Detector examples:
  - `80.Traffic analyzer RR`, event `WrongDirectionDetected`, text `Movement in prohibited direction detected`.
  - `80.Traffic analyzer RR`, event `OverspeedDetected`, text `Overspeed detected`.
  - `80.Traffic analyzer RR`, event `StatisticsInfo`, text `Lane statistics`.
- Useful for: traffic analytics, lane statistics, wrong-direction, and overspeed examples.

### Camera `Tracker`

Command shape:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera Tracker --limit 5 --json
```

Findings:

- Total count in 24 hours: 1,310.
- Categories: `situation`, `vehicle`.
- Detector examples:
  - `11.Person`, event `moveInZone`, text `Object moving in area detected`.
  - `22.Vehicle`, event `moveInZone`, text `Object moving in area detected`.
  - `6.Line crossing Right Side Road`, event `oneLine`, text `Object crossing line detected`.
- Useful for: tracker, line-crossing, and zone-movement examples.

## VMDA And Metadata Findings

Generic probe selection:

- `gRPC MetadataService.PullMetadata(VMDA)` failed because the selected VMDA endpoint returned no samples in the short window.

Focused working endpoint:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py \
  --timeout 12 \
  --samples 1 \
  --idle-ms 5000 \
  --endpoint hosts/Server/AVDetector.1/SourceEndpoint.vmda
```

Sanitized result:

```json
{
  "endpoint": "hosts/Server/AVDetector.1/SourceEndpoint.vmda",
  "samples": 1,
  "config_updates": 1,
  "heartbeats": 0,
  "items": [
    {
      "timestamp": "20260501T175457.605000",
      "tracklet_count": 20,
      "shape": {
        "timestamp": {"type": "str", "present": true},
        "tracklets": {"type": "object", "keys": 1}
      }
    }
  ]
}
```

VMDA endpoint map from `DomainService.GetCamerasByComponents`:

| VMDA endpoint | Camera | Detector | Detector type | Notes |
| --- | --- | --- | --- | --- |
| `hosts/Server/AVDetector.72/SourceEndpoint.vmda` | `Immersion 1` | `Neurotracker` | `NeuroTracker` | mapped |
| `hosts/Server/AVDetector.96/SourceEndpoint.vmda` | `Door` | `Neural tracker` | `NeuroTracker` | mapped |
| `hosts/Server/AVDetector.78/SourceEndpoint.vmda` | `Immersion 2` | `Neurotracker` | `NeuroTracker` | mapped |
| `hosts/Server/AVDetector.55/SourceEndpoint.vmda` | `Sim Search 3` | `Neurotracker` | `NeuroTracker` | mapped |
| `hosts/Server/AVDetector.1/SourceEndpoint.vmda` | `Tracker` | `Neurotracker` | `NeuroTracker` | live samples verified |
| `hosts/Server/AVDetector.15/SourceEndpoint.vmda` | `PPE` | `Equipment detection (PPE)` | `SelfMaskSegmentDetector` | mapped |
| `hosts/Server/AVDetector.34/SourceEndpoint.vmda` | `Pose detection` | `Pose Detection` | `PoseDetector` | mapped but no sample in short test |
| `hosts/Server/AVDetector.95/SourceEndpoint.vmda` | `Parking Lot Occupancy` | `Neural tracker` | `NeuroTracker` | mapped but no sample in short test |
| `hosts/Server/AVDetector.4/SourceEndpoint.vmda` | n/a | n/a | n/a | not found by reverse lookup |
| `hosts/Server/AVDetector.42/SourceEndpoint.vmda` | n/a | n/a | n/a | not found by reverse lookup |
| `hosts/Server/AVDetector.5/SourceEndpoint.vmda` | n/a | n/a | n/a | not found by reverse lookup |

## Direct gRPC Read Sweep Highlights

Additional demo coverage beyond the local Docker lab:

- `DomainService.ListCameras`: 33 cameras.
- `DomainService.ListArchives`: 14 archives.
- `DomainService.ListComponents`: 200 components over multiple pages.
- `DomainService.ListGlobalTrackers`: 1 item.
- `DomainService.ListGlobalTrackerCameras`: 12 items.
- `DomainService.ListAcfaComponents` and `ListAcfaComponents2`: paginated results.
- `ArchiveService.GetHistory`, `GetHistory2`, `GetHistoryStream`: real intervals.
- `ArchiveService.GetCalendar`: one recording day in the tested window.
- `EventHistoryService` read/search methods: dispatch and stream wrappers pass.
- `GroupManager.ListGroups`: 5 groups.
- `LayoutManager.ListLayouts`: 20 layouts and 1 slideshow.
- `LogicService.ListMacros`: 16 macros.
- `LogicService.ChangeMacros`: temporary disabled macro create/change/remove passed on 2026-05-03 with rollback; `LaunchMacro` was not called.
- `MapService.ListMaps`: 5 maps.
- `MapService.ListMapProviders`: 2 providers.
- `MapService.ChangeMaps`, `GetMapImage`, `GetMarkers`, and `UpdateMarkers`: temporary `codex-*` map and marker lifecycle passed on 2026-05-03 with rollback.
- `RealtimeRecognizerService.GetLists`: 1 list.
- `RealtimeRecognizerService.GetItems`: streamed 2 item shapes.
- `VMDAService.EnumerateSchemes`: 1 scheme.
- `NgpNodeService.ListSceneDescription`: 32 scene descriptions.

## HTTP `/grpc` Highlights

The HTTP `/grpc` sweep passed 64 methods and warned on 11.

Useful passes:

- Archive traits, recording info, history, calendar, size, volumes state, disk space.
- Domain version, host platform info, host timezone, node enumeration.
- Config list/get/templates and device catalog reads.
- Groups, layouts, maps, license restrictions/domain info.
- Logic macros and config reads.
- Security role/user/permission reads.
- Domain settings and timezone reads.
- `VMDAService.EnumerateSchemes`.

Useful warnings:

- Some methods returned HTTP 500 through the wrapper while direct gRPC had a clearer fixture/subsystem result.
- `LicenseService.GetHostInfo` closed the HTTP connection and should not be used as a generic HTTP wrapper smoke.
- `SharedKVStorageService` reads returned HTTP 500 through the wrapper on this stand; use direct gRPC for SharedKV tests.

## HTTP `/v1` Highlights

The HTTP `/v1` sweep passed 67 endpoints and warned on 11.

Useful passes:

- `/v1/domain/cameras` and batch camera endpoints returned `text/event-stream`.
- `/v1/domain/archives` and batch archive endpoints returned `text/event-stream`.
- `/v1/archive/historyStream` returned `text/event-stream`.
- `/v1/archive/history`, `/history2`, `/calendar`, `/traits`, `/volumes/state`, and `/volumes/diskSpace` passed.
- `/v1/security/*`, `/v1/groups/*`, `/v1/layouts`, `/v1/maps/list`, `/v1/logic_service/*`, and timezone endpoints passed.

Transport parity note:

- `/v1/archive/size` returned HTTP 500 even though direct gRPC and HTTP `/grpc` `ArchiveService.GetSize` passed.

## Controlled Mutation Run On 2026-05-02

With explicit demo-stand mutation approval, a bounded SharedKV fixture was executed against direct gRPC on `<demo-host>:20109`.

- Report: `demo-mutating-fixture-2026-05-02.md`
- Mutation: temporary `SharedKVStorageService.Commit` set, `BatchGetRecords`, `GetRecordsStream`, then remove.
- Result: PASS=1, WARN=0, FAIL=0.
- Rollback: verified; the temporary record was not present after removal and no full key value was persisted in the repo evidence.
- Event wait: `demo-subscription-during-mutation-2026-05-02.md` opened `DomainNotifier.PullEvents` during the mutation for 25 seconds.
- Subscription result: PASS=0, WARN=1, SKIP=0, FAIL=0; no events arrived before the deadline.

## Filtered Subscription Proof On 2026-05-02

Recent detector history showed active `ET_DetectorEvent` traffic on `34.Visitors`. A filtered `DomainNotifier.PullEvents` run used subject `hosts/Server/DeviceIpint.34/SourceEndpoint.video:0:0` and event type `detector`.

- Report: `demo-filtered-subscription-2026-05-02.md`
- Result: PASS=1, WARN=0, SKIP=0, FAIL=0.
- Events received: 5 within a bounded 20-second window.
- Lesson: unfiltered subscriptions can sit idle; use event type plus active camera/detector subjects from recent event history.
- WebSocket follow-up: `demo-websocket-subscription-2026-05-02.md` used the PDF-style `/events?schema=proto` URL after installing `websocket-client`; the remote host closed the connection before events arrived.

## AppDataDetector Event Model On 2026-05-02

Full camera view exposed 45 detector objects:

- 30 parent `AVDetector.*` objects.
- 15 child `AppDataDetector.*` objects.

The child `AppDataDetector.*` objects are the configured event producers for semantic tracker rules such as motion in area, line crossing, loitering, multiple objects, and track masking. The parent `AVDetector.*` objects provide tracker metadata and VMDA endpoints.

Reports:

- `appdata-detectors-demo-2026-05-02.md`
- `demo-appdata-subscription-2026-05-02.md`

Most active child subjects in the sampled two-hour window:

| Count | Camera | Child detector | Subject |
| ---: | --- | --- | --- |
| 60 | `1.Tracker` | `22.Vehicle` | `hosts/Server/AppDataDetector.22/EventSupplier` |
| 49 | `1.Tracker` | `11.Person` | `hosts/Server/AppDataDetector.11/EventSupplier` |
| 20 | `1.Tracker` | `6.Line crossing Right Side Road` | `hosts/Server/AppDataDetector.6/EventSupplier` |
| 18 | `10.LPR + MMR` | `14.Vehicle_OUT` | `hosts/Server/AppDataDetector.14/EventSupplier` |
| 12 | `1.Tracker` | `16.Line crossing Left Side Road` | `hosts/Server/AppDataDetector.16/EventSupplier` |

Subscription proof using `hosts/Server/AppDataDetector.22/EventSupplier` returned 8 events in 1130 ms.

## Configuration Object Model And ChangeConfig Proof On 2026-05-02

Reports:

- `config-model-study-demo-2026-05-02.md`
- `config-mutation-smoke-demo-2026-05-02.md`

Read-only model study:

- `DomainService.ListCameras(view=FULL)` showed 33 cameras and 45 detector objects: 30 parent `AVDetector.*` objects and 15 child `AppDataDetector.*` objects.
- `ConfigurationService.ListUnits(hosts/Server, VM_FULL)` showed 95 configuration units: 34 `AVDetector`, 34 `DeviceIpint`, 16 `AppDataDetector`, plus node services/storage modules.
- The host node exposed 14 creation factories: `DeviceIpint`, `AudioMonitor`, `MultimediaStorage`, `AVDetector`, `AppDataDetector`, `OfflineAnalytics`, `GlobalTracker`, `MMExportAgent`, `GSMModule`, `EMailModule`, `ACFA`, `RealtimeRecognizerExternal`, `Plugin`, and `Script`.
- Existing detector units looked stripped in the host tree, but `ListUnitsByAccessPoints` against exact `EventSupplier` and `SourceEndpoint` APs returned full writable detector parameters.

Controlled `ChangeConfig` mutation smoke:

- Temporary `MultimediaStorage.Gray` archive was created, renamed, and removed.
- Temporary virtual `DeviceIpint` camera was created with `vendor=Virtual`, renamed, and removed. The PDF-style `vendor=axxonsoft` value failed on this demo with `fanout request has failed`; `Virtual` is the correct fixture vendor here.
- Temporary `AVDetector` units for `SceneDescription`, `MotionDetection`, and `NeuroTracker` were created, renamed, and removed.
- Temporary `AppDataDetector.MoveInZone` was created under `hosts/Server/AVDetector.1/SourceEndpoint.vmda`, renamed/enabled, read back by `EventSupplier`, produced 22 detector events in the bounded verification window, and was removed.
- Temporary `AppDataDetector.MoveInZone` visual element mask was changed by updating its generated `VisualElement.*` child `polyline` with `value_simple_polygon`; readback returned 4 normalized points and rollback removed the parent detector.

## Metadata Tracklets Proof On 2026-05-02

The PDF `Get tracks using GO` section maps to `MetadataService.PullMetadata`. The demo VMDA endpoint returned the same `MetadataSample_Tracklets` data shape used by the Go example.

- Report: `demo-metadata-tracklets-2026-05-02.md`
- Endpoint: `hosts/Server/AVDetector.1/SourceEndpoint.vmda`
- Samples: 3.
- Tracklets per sample: 21, 21, 21.
- Config updates: 1.

## Heatmap Query Proof On 2026-05-02

`HeatMapService.ExecuteHeatmapQuery` was tested against `hosts/Server/AVDetector.1/SourceEndpoint.vmda` with a PDF-style VMDA zone query over a bounded two-hour window.

- Report: `demo-heatmap-query-2026-05-02.md`
- Result: PASS=1, WARN=0, SKIP=0, FAIL=0.
- Streamed pages: 3.
- Empty query behavior: the same endpoint returned `InvalidQuery`, so callers need a real VMDA query expression.
- Fixture note: no `HeatMapBuilder.*` component was found in inventory, so `BuildHeatmap` image generation remains dependent on a dedicated builder fixture.

## Recommended Demo Fixtures

Use these fixtures for future examples:

| Goal | Fixture |
| --- | --- |
| Inventory examples | Full demo camera list with 33 cameras |
| Event search | `Tracker`, `Face`, `LPR + MMR`, `Traffic Analyzer RR 1` |
| Metadata stream | `hosts/Server/AVDetector.1/SourceEndpoint.vmda` |
| Archive history/calendar | AliceBlue archive plus camera archive source APs resolved by `AxxonApiClient` |
| Layout examples | `LayoutManager.ListLayouts` |
| Map examples | `MapService.ListMaps`, `ListMapProviders`, and controlled temporary map/marker lifecycle |
| Macros | `LogicService.ListMacros` and controlled disabled macro create/change/remove; do not launch macros without approval |
| Security reads | Count/shape only from security list methods |

## Follow-Up Work

- Add a dedicated metadata endpoint selection helper that prefers active VMDA endpoints by sampling candidates instead of taking the first candidate.
- Add HTTP `/grpc` event-search parity examples.
- Add a redacted LPR predicate example that proves `ReadLprEvents` behavior without storing a real plate.
- Add safe fixture inputs for archive search: known time window, known camera, sample face image, and VMDA query request.
- Keep demo reports temporary unless they are sanitized before copying into repo docs.
