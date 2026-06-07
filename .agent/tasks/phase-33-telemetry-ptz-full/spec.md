# Spec: phase-33-telemetry-ptz-full

## Original task statement
Close every TelemetryService method the live PTZ device actually supports, taking the
service from 5/32 to its honest maximum on this stand. The simulated PTZ source
(hosts/Server/DeviceIpint.53/TelemetryControl.0) is live; reuse the proven
capture/restore + acquire/release pattern. Add the missing tools, live-verify, and
restamp.

Live probe results (DeviceIpint.53/TelemetryControl.0):
- PASS (device executes): KeepAlive, ReleaseSessionId, Move(absolute),
  GetPositionInformationNormalized, AbsoluteMoveNormalized, GetPresetsInfo, SetPreset,
  SetPreset2, GoPreset, RemovePreset, ConfigurePreset, GetTours, GetTourPoints,
  GetAuxiliaryOperations (returns empty list, RPC clean).
- FAIL (device does not support; honest non-goals): Focus, FocusAuto, Iris, IrisAuto
  ("Device does not support" / error 2), PointMove, AreaZoom (error 2),
  PerformAuxiliaryOperation (no aux ops exist), and the tour writes PlayTour, StopTour,
  StartFillTour, SetTourPoint, StopFillTour, RemoveTour (RPC returns
  error_code=GeneralError; the simulated device does not create tours).

## Acceptance criteria

- AC1: New read tools `get_position_normalized(access_point)` and
  `get_tours(access_point)` + `get_tour_points(access_point, tour_name)` call
  GetPositionInformationNormalized / GetTours / GetTourPoints and return their decoded
  bodies with error_code.
- AC2: New write tools `absolute_move_normalized(access_point, session_id, pan, tilt,
  zoom, mask)`, `set_preset(... )` (the bare SetPreset RPC, distinct from the existing
  set_preset which uses SetPreset2 — rename existing usage preserved), and
  `configure_preset(access_point, position, label, pan, tilt, zoom)` call
  AbsoluteMoveNormalized / SetPreset / ConfigurePreset.
- AC3: Existing tools already cover KeepAlive, ReleaseSessionId, Move, GetPresetsInfo,
  SetPreset2, GoPreset, RemovePreset, GetAuxiliaryOperations; no behavior regression.
  All new tools added to the ptz registration in the server.
- AC4: Unit tests for the new tools (call the right RPC, return shape). Full suite
  `python3.12 -m unittest discover -s tools/tests` green.
- AC5: Corpus restamp the 14 device-supported methods to tested-pass: KeepAlive,
  ReleaseSessionId, Move, GetPositionInformationNormalized, AbsoluteMoveNormalized,
  GetPresetsInfo, SetPreset, SetPreset2, GoPreset, RemovePreset, ConfigurePreset,
  GetTours, GetTourPoints, GetAuxiliaryOperations. The 13 device-unsupported methods
  stay pending/fixture-warn with a documented reason (NOT restamped). Restamp dry-run 0
  after --write; coverage doc updated. Live verify recorded.

## Constraints
- Live verification is reversible: presets created on probe slots (97/98/99) are
  removed; positions captured and restored; sessions released.
- Honest: only restamp methods the device actually executes. Device-unsupported
  methods (Focus/Iris/auto/point/area/tour-writes/aux-perform) are documented as
  stand-limited, not faked.
- Reuse the existing ptz module idiom and capability/session helpers.

## Non-goals
- Focus, FocusAuto, Iris, IrisAuto, PointMove, AreaZoom, PerformAuxiliaryOperation,
  PlayTour, StopTour, StartFillTour, SetTourPoint, StopFillTour, RemoveTour — the
  simulated PTZ source rejects these; closeable only on real PTZ hardware.

## Verification plan
- Build: pyimport smoke (server + ptz)
- Unit tests: new tool RPC-binding tests
- Integration tests: full suite discover
- Lint: n/a
- Manual checks: live probe of all 14 supported methods (reversible); restamp dry 0
