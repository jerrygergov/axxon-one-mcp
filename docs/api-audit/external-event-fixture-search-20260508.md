# Axxon One External Event Fixture Search

- Date: `2026-05-08`
- Target: demo stand `<demo-host>`
- Scope: destructive but rollback-scoped search for a usable `DetectorEx.*` fixture path.

## Summary

- Temporary `Plugin` objects using `module_name=LocalMonitoring` and both advertised `type` values (`common=0`, `grpc=1`) created and removed cleanly.
- Enabling those plugins did not expose a `DetectorEx` or `ExternalDetector` factory, and no DetectorEx-like config object appeared in the host tree.
- Direct child creation probes for `DetectorEx` and `ExternalDetector` under host, AVDetector, AppDataDetector, DeviceIpint, and TextEventSource parents did not create any object.
- Direct gRPC `ExternalDetectorService.RaiseOccasionalEvent` matches the HTTP `/v1/detectors/external:raiseOccasionalEvent` behavior: unresolved `DetectorEx.*` access points return gRPC 14, while AppDataDetector returns gRPC 13 `BAD_OPERATION`.
- Cleanup check confirmed `hosts/Server/Plugin.1`, `hosts/Server/Plugin.2`, and `hosts/Server/DetectorEx.0/1/2` are not present.

## Plugin Probe

| Probe | Result |
| --- | --- |
| Add enabled `Plugin` with `module_name=LocalMonitoring`, `type=0` | Added `hosts/Server/Plugin.1`, removed cleanly |
| After `type=0` add | `DetectorEx` and `ExternalDetector` factories still `NOT_FOUND`; no DetectorEx-like units found |
| Add enabled `Plugin` with `module_name=LocalMonitoring`, `type=1` | Added `hosts/Server/Plugin.2`, removed cleanly |
| After `type=1` add | `DetectorEx` and `ExternalDetector` factories still `NOT_FOUND`; no DetectorEx-like units found |

## Parent Creation Probe

| Parent | Type | Result |
| --- | --- | --- |
| `hosts/Server` | `DetectorEx` | HTTP 200 but empty `added`, `failed`, and `failed_reason` |
| `hosts/Server` | `ExternalDetector` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/AVDetector.1` | `DetectorEx` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/AVDetector.1` | `ExternalDetector` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/AppDataDetector.22` | `DetectorEx` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/AppDataDetector.22` | `ExternalDetector` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/DeviceIpint.24` | `DetectorEx` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/DeviceIpint.24` | `ExternalDetector` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/DeviceIpint.24/TextEventSource.0` | `DetectorEx` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |
| `hosts/Server/DeviceIpint.24/TextEventSource.0` | `ExternalDetector` | `failed_reason=CONFIG_ERROR_UNKNOWN`, `fanout request has failed` |

## Direct gRPC Raise Probe

| Access point | Result |
| --- | --- |
| `DetectorEx.1` | gRPC 14 `Can't resolve reference` |
| `hosts/Server/DetectorEx.1` | gRPC 14 `Can't resolve reference` |
| `hosts/Server/DetectorEx.1/EventSupplier` | gRPC 14 `Can't resolve reference` |
| `hosts/Server/AppDataDetector.22/EventSupplier` | gRPC 13 `BAD_OPERATION` |
| `hosts/Server/DeviceIpint.24/TextEventSource.0` | gRPC 14 `Can't resolve reference` |

## Conclusion

The demo stand currently has no reachable or creatable `DetectorEx.*` fixture through the tested public configuration paths. `DeviceIpint.24` is a `PosXml` text event source, not a virtual-trigger DetectorEx source. Successful `RaiseOccasionalEvent` / `RaisePeriodicalEvent` examples still require a product-supported DetectorEx fixture, config import, license/module enablement, or vendor-provided setup workflow.
