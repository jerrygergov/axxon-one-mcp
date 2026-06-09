# Phase B — PTZ / Telemetry live verification

**Date:** 2026-06-09
**Target:** `%3Cdemo-host%3E`, PTZ access point `hosts/Server/DeviceIpint.54/TelemetryControl.0`
**Module:** `tools/axxon_mcp_ptz.py` (the existing `ptz` group, on by default)
**Method:** live exercise through the actual tool wrappers, with strict position rollback. The
camera is a real physical PTZ; it was moved only via a no-op `AbsoluteMove` and returned to its
exact start. **The camera was never displaced from START.**

## Fixture discovery (stand probe)

| Fixture | Status | Evidence |
| --- | --- | --- |
| PTZ / Telemetry | **PRESENT** | `DeviceIpint.54` exposes `TelemetryControl.{0,1,2}`; `AcquireSessionId` succeeds; 250 preset slots, continuous + absolute capabilities |
| Tag & Track tracker | absent | `ListTrackers` → `NOT_FOUND` on all PTZ APs |
| Control panels | absent | `ListControlPanels` → 0 items |
| LDAP server | absent | `ListLDAPServers` → `[]` |
| Recording archive (online) | absent | 20 archives listed but all `ArchiveService` calls fail (CORBA `BAD_OPERATION` / `UNAVAILABLE`) |
| GDPR settings | PRESENT | `GetGDPRSettings` returns an etag (reversibly updatable) |
| `StateControlService` | reachable | `GetCurrentState`/`GetDefaultState` work on PTZ patrol APs |

## PTZ verification result

START position: `pan=693, tilt=200, zoom=10` (normalized `1.0/1.0/1.0` — device parked at axis max).
Final read-back after rollback: `pan=693, tilt=200, zoom=10` — exact.

| Tool (module) | RPC | Verdict | Detail |
| --- | --- | --- | --- |
| list_telemetry_sources | DomainService.ListComponents | PASS | 3 sources (TelemetryControl.0/1/2) |
| session_available | IsSessionAvailable | PASS | available=True |
| acquire_session | AcquireSessionId | PASS | session_id assigned, NotError |
| get_position | GetPositionInformation | PASS | pan=693 tilt=200 zoom=10 |
| get_position_normalized | GetPositionInformationNormalized | PASS | 1.0/1.0/1.0 |
| list_presets | GetPresetsInfo | PASS | 0 presets configured |
| auxiliary_operations | GetAuxiliaryOperations | PASS | 0 aux ops |
| keepalive_session | KeepAlive | PASS | result=True |
| absolute_move (no-op + rollback) | AbsoluteMove | PASS | 0 drift; rollback exact |
| release_session | ReleaseSessionId | PASS | clean release on a fresh session |

**10 TelemetryService RPCs verified live through the module wrappers, PASS.**

## Device-specific findings (not module bugs)

- **`Move` (continuous/relative joystick) → `GeneralError`** on every axis/direction on this
  device. `AbsoluteMove` works on the same device, so the module is correct; the device does not
  support continuous-speed Move (and is parked at physical max on all axes). The module surfaces
  the gRPC error cleanly — no silent swallow.
- **`ReleaseSessionId` → `SessionUnavailable`** only when the session had already expired (8 s
  window) after the Move error; a fresh-session acquire→release is clean. Module behavior correct.
- `error_code` is omitted by protobuf JSON when it is the default `NotError(0)`; the module
  normalizes this via `body.get("error_code", "NotError")`.

## Fixture-blocked Telemetry RPCs that remain unattainable on this stand

- **Tours** (`PlayTour`, `StopTour`, `StartFillTour`, `SetTourPoint`, `StopFillTour`,
  `RemoveTour`): the device reports no tour support.
- **`PerformAuxiliaryOperation`**: `GetAuxiliaryOperations` returns 0 ops.
- **`AreaZoom` / `FocusAuto` / `IrisAuto`**: not exercised — the device rejects continuous Move,
  so these motor/auto operations are unlikely to be supported; left fixture-blocked.

These stay `tested-warn-fixture-needed` pending a PTZ device with tours / aux ops / auto modes.

## Sanitization

Host → `%3Cdemo-host%3E`, credentials → `%3Credacted%3E`. `AXXON_TLS_CN=Server` retained.
`hosts/Server/DeviceIpint.54/...` UIDs retained (intrinsic, non-sensitive). No proto / CA /
credentials / symlink committed.
