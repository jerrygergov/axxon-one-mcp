# Evidence Bundle: phase-29-ptz-zoom

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — absolute-mode Zoom contract test — PASS
- `test_zoom_absolute_mode_emits_single_zoom_with_absolute_flag` asserts zoom(...,
  mode="absolute") returns status ok and emits exactly one Zoom RPC whose CommonRequest
  carries the access_point, session_id, value, and a Capabilities with is_absolute=True
  (is_continuous=False).
- Proof: tools/tests/test_axxon_mcp_ptz.py; live zoom(absolute,0.4)=ok
  (raw/live-verify.txt).

## AC2 — reversible capture/restore test — PASS
- `test_zoom_reversible_capture_restore_sequence` captures position, drives
  Zoom(absolute), then AbsoluteMove back to the captured pan/tilt/zoom and asserts the
  Zoom call precedes the AbsoluteMove. Bad-mode move is still refused
  (test_move_bad_mode_refused). No new tool code.
- Proof: tools/tests/test_axxon_mcp_ptz.py; live sequence restored position exactly
  (raw/live-verify.txt: restored exactly: True).

## AC3 — no production change to the zoom path — PASS
- The zoom tool (axxon_mcp_ptz.py _common/zoom) was already correct; this phase added
  only tests + restamp + doc. git diff shows no change to tools/axxon_mcp_ptz.py.

## AC4 — full suite green — PASS
- ptz suite 10 OK (2 new Zoom tests). Full suite `Ran 807 tests ... OK`
  (raw/test-integration.txt), up from 805.

## AC5 — corpus restamp + coverage doc — PASS
- TelemetryService.Zoom -> tested-pass. Coverage 208 pass-class / 115 pending / 38
  fixture-warn; item 10p added. Restamp dry-run reports 0 after --write.

## Commands run
- python3.12 -c "import axxon_mcp_server; import axxon_mcp_ptz" (build.txt: import ok)
- python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_ptz.py -v (10 OK)
- python3.12 -m unittest discover -s tools/tests (Ran 807 ... OK)
- python3.12 tools/axxon_corpus_restamp.py [--write] (1 written; 0 on re-dry)

## Raw artifacts
- .agent/tasks/phase-29-ptz-zoom/raw/build.txt
- .agent/tasks/phase-29-ptz-zoom/raw/test-unit.txt
- .agent/tasks/phase-29-ptz-zoom/raw/test-integration.txt
- .agent/tasks/phase-29-ptz-zoom/raw/lint.txt
- .agent/tasks/phase-29-ptz-zoom/raw/live-verify.txt

## Stand hygiene
- Reversible: the camera position was captured before and restored after Zoom; final
  position equals the captured position exactly. continuous mode rejected by the
  simulated source (noted, not hidden). No proto/CA/PDF committed; secrets env-only.

## Known gaps
- Zoom verified in absolute mode on a simulated source (virtual optics; reported zoom
  unchanged but the RPC executed). Focus/Iris/AbsoluteMoveNormalized/PointMove/AreaZoom
  and preset/tour pending methods are separate phases.
