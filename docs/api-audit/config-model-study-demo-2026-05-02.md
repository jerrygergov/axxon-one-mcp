# Axxon One Configuration Object Model Study

- Started: `2026-05-02T17:39:49.842795+00:00`
- Finished: `2026-05-02T17:39:52.952339+00:00`
- gRPC target: `<demo-host>:20109`

This is a read-only study. It inventories domain objects, configuration units, factories, and writable property shapes before any `ChangeConfig` mutation.

## Summary

- PASS: 5
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `domain` | 268 | cameras=33 archives=14 components=200 appdata=15 av=30 |
| PASS | `unit_tree` | 149 | total_units=95 top_types=[('AVDetector', 34), ('DeviceIpint', 34), ('AppDataDetector', 16), ('EMailModule', 2)] |
| PASS | `factories` | 187 | requested=14 statuses=[('NOT_FOUND', 7), ('OK', 7)] |
| PASS | `properties` | 3 | representatives=5 |
| PASS | `similar_units` | 523 | samples=3 |

## Mutation Model

- Read a full `UnitDescriptor` with `ConfigurationService.ListUnits` or `ListUnitsByAccessPoints`.
- For creation, inspect the parent unit `factory` entries or call `BatchGetFactories(RequestedFactory(unit_type, parent_uid, ignore_possible_limits=true))`.
- Convert only writable, non-internal property descriptors into `Property` values when building `ChangeConfigRequest.added` or `changed` units.
- Use stable test names such as `codex-*`, read back the generated uid from `ChangeConfigResponse.added`, verify inventory deltas, then remove the created unit.
- Do not persist credentials, tokens, serial numbers, license keys, private keys, or raw plate values in reports.

## Object Kinds Observed

- Domain inventory: 33 cameras, 14 archives, 200 components.
- Full camera detector inventory: 45 detector objects, split into 30 parent `AVDetector.*` metadata/VMDA producers and 15 child `AppDataDetector.*` semantic event producers.
- Configuration unit tree: 95 units under `hosts/Server`: 34 `AVDetector`, 34 `DeviceIpint`, 16 `AppDataDetector`, 2 `EMailModule`, and one each of `Node`, `ACFA`, `GlobalTracker`, `HeatMapBuilder`, `HttpServer`, `MMExportAgent`, `MultimediaStorage`, `VMDA2_DB`, and `VMDA_DB`.
- Component AP families in `DomainService.ListComponents`: `ACFA`, `DeviceIpint`, `AVDetector`, `MultimediaStorage`, `AppDataDetector`, and `AVIFilePlayer`.

## Factory Findings

The host node exposes creation factories for:

`DeviceIpint`, `AudioMonitor`, `MultimediaStorage`, `AVDetector`, `AppDataDetector`, `OfflineAnalytics`, `GlobalTracker`, `MMExportAgent`, `GSMModule`, `EMailModule`, `ACFA`, `RealtimeRecognizerExternal`, `Plugin`, and `Script`.

Useful factory/default properties:

- `DeviceIpint`: `vendor`, `model`, `firmware`, `address`, `port`, `display_name`, `display_id`, `user`, `password`, `blockingConfiguration`, `archiveBinding`, `recordingMode`.
- `MultimediaStorage`: `display_name`, `color`, `storage_type`, `day_depth`.
- `AVDetector`: `display_name`, `detector`, `onlyKeyFrames`; detector enum had 33 values including `SceneDescription`, `MotionDetection`, and `NeuroTracker`.
- `AppDataDetector`: `display_name`, `detector`; detector enum had 18 values including `CrossOneLine`, `LongInZone`, `MoveInZone`, `LotsObjects`, and pose rules.

## Readback Gotchas

- `ListUnits(hosts/Server, VM_FULL)` can still show stripped child detector descriptors in the host tree.
- Use `ListUnitsByAccessPoints` with exact APs such as `hosts/Server/AppDataDetector.22/EventSupplier`, `hosts/Server/AVDetector.1/EventSupplier`, or `hosts/Server/AVDetector.1/SourceEndpoint.vmda` to retrieve full detector parameter descriptors.
- Existing detector units returned writable fields such as `enabled`, `streaming_id`, `target_fps`, decoder/model settings, object filters, line/zone parameters, and event type metadata when read by exact AP.
