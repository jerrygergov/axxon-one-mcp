# Demo Stand AppDataDetector Study

This note records the corrected detector/event model for the demo stand at `<demo-host>`.

## Key Finding

The parent `AVDetector.*` tracker objects are not the right default event-subscription subjects for semantic detector events. In Axxon One, tracker-style parent detectors often generate metadata and service events, while child `AppDataDetector.*` objects generate configured analytic events such as motion in area, line crossing, loitering, multiple objects, and masking.

Use recent event history to choose an active `AppDataDetector.*` subject, then subscribe to `DomainNotifier.PullEvents` with:

- `event_type`: `ET_DetectorEvent`
- `subject`: the child `AppDataDetector.*` `EventSupplier`

## Inventory Summary

- Cameras in full view: 33
- Detector objects in full camera view: 45
- Parent `AVDetector.*` detector objects: 30
- Child `AppDataDetector.*` detector objects: 15

## Configuration Tree Check

The configuration tree has one more `AppDataDetector` unit than the full-camera detector list:

- `ConfigurationService.ListUnits` reports 16 `AppDataDetector` units under `hosts/Server`.
- The camera-view detector inventory reports 15 child `AppDataDetector.*` event suppliers.
- The extra config-tree unit is `hosts/Server/AppDataDetector.4/EventSupplier` (`Line crossing`), which is present in configuration but was not part of the sampled recent-event table.

This is the important distinction for API-book examples: camera inventory gives you the event-producing child subjects, while the config tree can expose additional detector objects that are configured but not active in the same event sample window.

## AppDataDetector Objects

Counts are `EventHistoryService.ReadCount` totals for `ET_DetectorEvent` over the sampled two-hour window.

| Recent 2h | Camera | Child detector | Subject | Parent tracker | Type | Event ids |
| ---: | --- | --- | --- | --- | --- | --- |
| 60 | `1.Tracker` | `22.Vehicle` | `hosts/Server/AppDataDetector.22/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `MoveInZone` / Motion in area | `moveInZone`, `moveInZoneGroup` |
| 49 | `1.Tracker` | `11.Person` | `hosts/Server/AppDataDetector.11/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `MoveInZone` / Motion in area | `moveInZone`, `moveInZoneGroup` |
| 20 | `1.Tracker` | `6.Line crossing Right Side Road` | `hosts/Server/AppDataDetector.6/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `CrossOneLine` / Line crossing | `oneLine` |
| 18 | `10.LPR + MMR` | `14.Vehicle_OUT` | `hosts/Server/AppDataDetector.14/EventSupplier` | `hosts/Server/AVDetector.74/EventSupplier` | `CrossOneLine` / Line crossing | `oneLine` |
| 12 | `1.Tracker` | `16.Line crossing Left Side Road` | `hosts/Server/AppDataDetector.16/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `CrossOneLine` / Line crossing | `oneLine` |
| 4 | `1.Tracker` | `5.Loitering In Area` | `hosts/Server/AppDataDetector.5/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `LongInZone` / Loitering in area | `equalInZone`, `equalInZoneGroup`, `lessInZone`, `lessInZoneGroup`, `longInZone`, `longInZoneGroup` |
| 1 | `1.Tracker` | `15.Multiple objects` | `hosts/Server/AppDataDetector.15/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `LotsObjects` / Multiple objects | `lotsObjects` |
| 0 | `2.Pose detection` | `2.Man Down Detection` | `hosts/Server/AppDataDetector.2/EventSupplier` | `hosts/Server/AVDetector.34/EventSupplier` | `RecumbentDetector` / Person down detector | `recumbent` |
| 0 | `2.Pose detection` | `3.Sitting Person Detection` | `hosts/Server/AppDataDetector.3/EventSupplier` | `hosts/Server/AVDetector.34/EventSupplier` | `SitDownDetector` / Sitting person detector | `sitDown` |
| 0 | `10.LPR + MMR` | `13.Vehicle_IN` | `hosts/Server/AppDataDetector.13/EventSupplier` | `hosts/Server/AVDetector.74/EventSupplier` | `CrossOneLine` / Line crossing | `oneLine` |
| 0 | `43.Door` | `19.Line crossing` | `hosts/Server/AppDataDetector.19/EventSupplier` | `hosts/Server/AVDetector.96/EventSupplier` | `CrossOneLine` / Line crossing | `oneLine` |
| 0 | `45.Parking Lot Occupancy` | `18.Loitering in area` | `hosts/Server/AppDataDetector.18/EventSupplier` | `hosts/Server/AVDetector.95/EventSupplier` | `LongInZone` / Loitering in area | `equalInZone`, `equalInZoneGroup`, `lessInZone`, `lessInZoneGroup`, `longInZone`, `longInZoneGroup` |
| 0 | `46.Cyclists` | `17.Motion in area` | `hosts/Server/AppDataDetector.17/EventSupplier` | `hosts/Server/AVDetector.94/EventSupplier` | `MoveInZone` / Motion in area | `moveInZone`, `moveInZoneGroup` |
| 0 | `47.Bulltet` | `20.Motion in area` | `hosts/Server/AppDataDetector.20/EventSupplier` | `hosts/Server/AVDetector.98/EventSupplier` | `MoveInZone` / Motion in area | `moveInZone`, `moveInZoneGroup` |
| 0 | `47.Bulltet` | `21.Track masking` | `hosts/Server/AppDataDetector.21/EventSupplier` | `hosts/Server/AVDetector.98/EventSupplier` | `MaskingObject` / Track masking | `PrivateMask` |

## Exact Access-Point Reads

The event-supplier APs expose the writable parameter descriptors that the tree view strips out:

| Access Point | Returned Units | Root Type | Writable Props | Total Props | Child Units |
| --- | ---: | --- | --- | ---: | ---: |
| `hosts/Server/AppDataDetector.2/EventSupplier` | 1 | `AppDataDetector` | `display_name`, `enabled`, `measurementsCount` | 7 | 0 |
| `hosts/Server/AppDataDetector.3/EventSupplier` | 1 | `AppDataDetector` | `display_name`, `enabled`, `measurementsCount` | 7 | 0 |
| `hosts/Server/AppDataDetector.4/EventSupplier` | 1 | `AppDataDetector` | `display_name`, `enabled`, `MinObjWidth`, `MinObjHeight`, `MaxObjWidth`, `MaxObjHeight`, `ObjectRelaxationOffsetX`, `ObjectRelaxationOffsetY`, `MinSpeed`, `MaxSpeed`, `ObjectClass` | 15 | 0 |
| `hosts/Server/AppDataDetector.5/EventSupplier` | 1 | `AppDataDetector` | `display_name`, `enabled`, `TimeAlarm`, `TimeComparisonMode`, `MinObjWidth`, `MinObjHeight`, `MaxObjWidth`, `MaxObjHeight`, `ObjectRelaxationOffsetX`, `ObjectRelaxationOffsetY`, `MinSpeed`, `MaxSpeed`, `ObjectClass`, `AlarmObjectCount`, `PeriodAlarmObjectHolding`, `EnableGroupEvent` | 20 | 0 |
| `hosts/Server/AppDataDetector.6/EventSupplier` | 1 | `AppDataDetector` | `display_name`, `enabled`, `MinObjWidth`, `MinObjHeight`, `MaxObjWidth`, `MaxObjHeight`, `ObjectRelaxationOffsetX`, `ObjectRelaxationOffsetY`, `MinSpeed`, `MaxSpeed`, `ObjectClass` | 15 | 0 |

## Subscription Proof

Report: `demo-appdata-subscription-2026-05-02.md`

Subject: `hosts/Server/AppDataDetector.22/EventSupplier`

Result:

- PASS=1, WARN=0, SKIP=0, FAIL=0
- Events received: 8
- Elapsed: 1130 ms

Representative event-history shape:

- Camera: `1.Tracker`
- Detector: `22.Vehicle`
- Detector subject: `hosts/Server/AppDataDetector.22/EventSupplier`
- Event type: `moveInZone`
- State pattern: `BEGAN` / `ENDED`
- Group: `DG_SITUATION_DETECTOR`

## Corrected Guidance

- For metadata or tracklets, use parent tracker VMDA endpoints such as `hosts/Server/AVDetector.1/SourceEndpoint.vmda`.
- For semantic analytics events, use child `AppDataDetector.*` event suppliers.
- For subscription examples, first run a short `ReadCount` or `ReadEvents` scan across configured child detectors and choose a recently active child.
- Do not assume the camera AP or parent `AVDetector.*` AP is the best event subject; those can work for broad searches, but they hide which configured rule actually produced the event.
