# Axxon One Configuration Object Model Study

- Started: `2026-05-06T18:17:04.575623+00:00`
- Finished: `2026-05-06T18:17:07.450617+00:00`
- gRPC target: `<demo-host>:20109`

This is a read-only study. It inventories domain objects, configuration units, factories, and writable property shapes before any `ChangeConfig` mutation.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `appdata_detectors` | 918 | count=16 factory_options=18 |

## Mutation Model

- Read a full `UnitDescriptor` with `ConfigurationService.ListUnits` or `ListUnitsByAccessPoints`.
- For creation, inspect the parent unit `factory` entries or call `BatchGetFactories(RequestedFactory(unit_type, parent_uid, ignore_possible_limits=true))`.
- Convert only writable, non-internal property descriptors into `Property` values when building `ChangeConfigRequest.added` or `changed` units.
- Use stable test names such as `codex-*`, read back the generated uid from `ChangeConfigResponse.added`, verify inventory deltas, then remove the created unit.
- Do not persist credentials, tokens, serial numbers, license keys, private keys, or raw plate values in reports.

## AppDataDetector Inventory

- Host UID: `hosts/Server`
- AppDataDetector units: 16
- Factory detector options: 18

| UID | Display ID | Display Name | Access Point | Detector | Enabled | Writable Props | Child Units | Visual Elements |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| `hosts/Server/AppDataDetector.2` | `2` | Man Down Detection | `hosts/Server/AppDataDetector.2/EventSupplier` | `RecumbentDetector` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.3` | `3` | Sitting Person Detection | `hosts/Server/AppDataDetector.3/EventSupplier` | `SitDownDetector` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.4` | `4` | Line crossing | `hosts/Server/AppDataDetector.4/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.5` | `5` | Loitering In Area | `hosts/Server/AppDataDetector.5/EventSupplier` | `LongInZone` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.6` | `6` | Line crossing Right Side Road | `hosts/Server/AppDataDetector.6/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.11` | `11` | Person | `hosts/Server/AppDataDetector.11/EventSupplier` | `MoveInZone` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.13` | `13` | Vehicle_IN | `hosts/Server/AppDataDetector.13/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.14` | `14` | Vehicle_OUT | `hosts/Server/AppDataDetector.14/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.15` | `15` | Multiple objects | `hosts/Server/AppDataDetector.15/EventSupplier` | `LotsObjects` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.16` | `16` | Line crossing Left Side Road | `hosts/Server/AppDataDetector.16/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.17` | `17` | Motion in area | `hosts/Server/AppDataDetector.17/EventSupplier` | `MoveInZone` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.18` | `18` | Loitering in area | `hosts/Server/AppDataDetector.18/EventSupplier` | `LongInZone` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.19` | `19` | Line crossing | `hosts/Server/AppDataDetector.19/EventSupplier` | `CrossOneLine` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.20` | `20` | Motion in area | `hosts/Server/AppDataDetector.20/EventSupplier` | `MoveInZone` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.21` | `21` | Track masking | `hosts/Server/AppDataDetector.21/EventSupplier` | `MaskingObject` | `None` |  | 0 | 0 |
| `hosts/Server/AppDataDetector.22` | `22` | Vehicle | `hosts/Server/AppDataDetector.22/EventSupplier` | `MoveInZone` | `None` |  | 0 | 0 |

## Exact Access-Point Reads

| Access Point | Returned Units | Root Type | Writable Props | Total Props | Child Units |
| --- | ---: | --- | --- | ---: | ---: |
| `hosts/Server/AppDataDetector.2/EventSupplier` | 1 | `AppDataDetector` | display_name, enabled, measurementsCount | 7 | 0 |
| `hosts/Server/AppDataDetector.3/EventSupplier` | 1 | `AppDataDetector` | display_name, enabled, measurementsCount | 7 | 0 |
| `hosts/Server/AppDataDetector.4/EventSupplier` | 1 | `AppDataDetector` | display_name, enabled, MinObjWidth, MinObjHeight, MaxObjWidth, MaxObjHeight, ObjectRelaxationOffsetX, ObjectRelaxationOffsetY, MinSpeed, MaxSpeed, ObjectClass | 15 | 0 |
| `hosts/Server/AppDataDetector.5/EventSupplier` | 1 | `AppDataDetector` | display_name, enabled, TimeAlarm, TimeComparisonMode, MinObjWidth, MinObjHeight, MaxObjWidth, MaxObjHeight, ObjectRelaxationOffsetX, ObjectRelaxationOffsetY, Mi | 20 | 0 |
| `hosts/Server/AppDataDetector.6/EventSupplier` | 1 | `AppDataDetector` | display_name, enabled, MinObjWidth, MinObjHeight, MaxObjWidth, MaxObjHeight, ObjectRelaxationOffsetX, ObjectRelaxationOffsetY, MinSpeed, MaxSpeed, ObjectClass | 15 | 0 |
