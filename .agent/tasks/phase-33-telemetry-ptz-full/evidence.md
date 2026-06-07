# Evidence Bundle: phase-33-telemetry-ptz-full

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-07

## AC1 — new read tools — PASS
- get_position_normalized (GetPositionInformationNormalized), get_tours (GetTours),
  get_tour_points (GetTourPoints) added to axxon_mcp_ptz.py; return decoded bodies +
  error_code.
- Proof: tests test_get_position_normalized/test_get_tours_shape/
  test_get_tour_points_shape; live ok (raw/live-verify.txt).

## AC2 — new write tools — PASS
- absolute_move_normalized (AbsoluteMoveNormalized), save_preset (bare SetPreset),
  configure_preset (ConfigurePreset) added; emit the right RPCs.
- Proof: tests test_absolute_move_normalized_emits_rpc/test_save_preset_uses_bare_setpreset/
  test_configure_preset_emits_rpc; live ok, fresh-session verification for the
  contention-sensitive preset ops (raw/live-verify.txt).

## AC3 — no regression to existing tools — PASS
- KeepAlive/ReleaseSessionId/Move/GetPresetsInfo/SetPreset2/GoPreset/RemovePreset/
  GetAuxiliaryOperations already covered; existing ptz tests still green; all 6 new
  tools registered in register_ptz_tools.

## AC4 — unit + full suite green — PASS
- ptz suite 16 OK (6 new). Full suite `Ran 836 ... OK` (raw/test-integration.txt), up
  from 830.

## AC5 — restamp 14 supported, document 12 unsupported — PASS
- 14 TelemetryService methods -> tested-pass; restamp dry-run 0 after --write.
  TelemetryService now 19/32. Coverage 227 pass-class / 107 pending / 27 fixture-warn;
  item 10t. The 13 device-unsupported methods (Focus/FocusAuto/Iris/IrisAuto/PointMove/
  AreaZoom/PerformAuxiliaryOperation + 6 tour writes) NOT restamped, documented as
  closeable only on real PTZ hardware.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_ptz" (import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_ptz.py -v (16 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 836 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (14 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-33-telemetry-ptz-full/raw/build.txt
- .agent/tasks/phase-33-telemetry-ptz-full/raw/test-unit.txt
- .agent/tasks/phase-33-telemetry-ptz-full/raw/test-integration.txt
- .agent/tasks/phase-33-telemetry-ptz-full/raw/lint.txt
- .agent/tasks/phase-33-telemetry-ptz-full/raw/live-verify.txt

## Stand hygiene
- Reversible PTZ control: presets created (90/97/98/99) all removed, captured position
  restored, sessions released. The transient device-busy "error 1" was handled by
  fresh-session re-verification, not faked. No proto/CA/PDF committed; secrets env-only.

## Known gaps
- 13 TelemetryService methods unsupported by the simulated source (documented); 1
  remains fixture-warn-class (GetPositionInformationNormalized was warn, now passed).
  TagAndTrackService (PTZ auto-follow) is a separate service.
