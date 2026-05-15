# Axxon One DetectorEx External Event Proof

- Date: `2026-05-08`
- Target: demo stand `<demo-host>`
- DetectorEx fixture: `hosts/Server/DetectorEx.1`
- DetectorEx access point: `hosts/Server/DetectorEx.1/EventSupplier`
- DetectorEx VMDA endpoint: `hosts/Server/DetectorEx.1/SourceEndpoint.vmda`
- Source camera: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`

## Fixture Shape

`ConfigurationService.ListUnits` confirms `hosts/Server/DetectorEx.1` is a `DetectorEx` unit named `External Detection`.

Important properties:

- `detector=ExternalDetector`
- `enabled=true`
- `event_types=Event1:DetectorOnePhaseEventType,Event2:DetectorTwoPhaseEventType,TargetList:DetectorPeriodicalEventType`
- `streaming_id=hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- `EnableRecordingObjectsTracking=true`

The unit has a child `AppDataDetector.27` (`CrossOneLine`) whose input VMDA endpoint is `hosts/Server/DetectorEx.1/SourceEndpoint.vmda`. The legacy camera detector inventory also lists `hosts/Server/DetectorEx.1/EventSupplier` as `type=ExternalDetector`.

## JIRA / Internal Notes

The exported JIRA issue `[ACR-85402]` states that DetectorEx is the virtual-trigger detector type. A DetectorEx object must exist before events are raised. Each `DetectorEx.N` acts as a separate service. `RaiseOccasionalEvent` handles one-phase and two-phase events, while `RaisePeriodicalEvent` sends external tracks. The event flow is Public API or direct gRPC -> NativeBL -> DetectorEx -> event channel, where consumers such as database, macros, and subscribers can receive detector events. The JIRA export lists attachments named `detectorex-analyze.md`, `detectorex-plugin-server-interaction.md`, and `ExternalDetector.rep`, but the HTML export does not include their bodies.

The separate `Virtual trigger_2 2.docx` confirms the public request fields:

- `RaiseOccasionalEvent`: `access_point`, `event_type` (`Event1` or `Event2`), `timestamp`, `data` as `google.protobuf.Struct`, `event_id`, and `event_state` (`HAPPENED`, `BEGAN`, `ENDED`).
- `RaisePeriodicalEvent`: `access_point`, `event_type=TargetList`, `timestamp`, and `data.target_list.tracklets[]`.
- Tracklet fields: `object_id`, `object_unique_id`, `object_type` from 1 to 127, `rectangle`, optional `logical_center`, and optional HSV `color`.

## RaiseOccasionalEvent

HTTP `/v1/detectors/external:raiseOccasionalEvent` with Bearer auth passed against `hosts/Server/DetectorEx.1/EventSupplier`.

Request shape:

```json
{
  "accessPoint": "hosts/Server/DetectorEx.1/EventSupplier",
  "eventType": "Event1",
  "timestamp": "2026-05-08T09:14:43.370603Z",
  "eventId": "codex-external-event-20260508T091443370541Z",
  "eventState": "HAPPENED",
  "data": {
    "codex_marker": "codex-external-event-20260508T091443370541Z",
    "source": "axxon_external_event_smoke"
  }
}
```

Response:

```json
{"error": "OK"}
```

Verification:

- `EventHistoryService.ReadEvents` returned one matching event for the injected event id.
- Latest runnable report: `external-event-smoke-latest.md` / `external-event-smoke-latest.json`.

## RaisePeriodicalEvent

HTTP `/v1/detectors/external:raisePeriodicalEvent` with Bearer auth passed against `hosts/Server/DetectorEx.1/EventSupplier`.

Request shape:

```json
{
  "accessPoint": "hosts/Server/DetectorEx.1/EventSupplier",
  "eventType": "TargetList",
  "timestamp": "2026-05-08T09:17:17.037000Z",
  "data": {
    "targetList": {
      "tracklets": [
        {
          "objectId": 3001,
          "objectUniqueId": 3001,
          "objectType": 1,
          "rectangle": {"x": 0.12, "y": 0.10, "width": 0.12, "height": 0.20},
          "logicalCenter": {"x": 0.18, "y": 0.20},
          "color": {"hue": 60.0, "saturation": 0.4, "value": 0.9}
        }
      ]
    }
  }
}
```

Response:

```json
{"error": "OK"}
```

Direct gRPC `ExternalDetectorService.RaisePeriodicalEvent` also returned the default OK response for an equivalent `TargetList` tracklet request.

Metadata verification:

- `MetadataService.PullMetadata` must be opened on `hosts/Server/DetectorEx.1/SourceEndpoint.vmda` before or during track injection.
- With the stream open first, five `TargetList` raises returned OK and the metadata stream returned one sample with one tracklet.
- First observed tracklet:
  - `id=3001`
  - `state=OBJECT_STATE_APPEARED`
  - `rectangle={x=0.12, y=0.1, w=0.12, h=0.2}`
  - `logical_center={x=0.18, y=0.2}`
  - `color={hue=60.0, saturation=0.4, value=0.9}`
  - `type=OBJECT_TYPE_HUMAN`

## Conclusions

- Virtual trigger / external event injection is verified on the demo stand once a real `DetectorEx` fixture exists.
- `DetectorEx.1/EventSupplier` is the correct access point for `RaiseOccasionalEvent` and `RaisePeriodicalEvent`.
- `DetectorEx.1/SourceEndpoint.vmda` is the metadata endpoint for externally injected tracklets.
- `Event1` one-phase occasional events are persisted/readable through event history.
- `TargetList` periodical tracklets are visible through `MetadataService.PullMetadata` when the metadata stream is active during injection.
- API-side creation of a DetectorEx fixture is still not documented as verified; earlier public `ChangeConfig` attempts failed or returned no uid. Treat DetectorEx fixture setup as a prerequisite unless a supported creation/import workflow is available.
