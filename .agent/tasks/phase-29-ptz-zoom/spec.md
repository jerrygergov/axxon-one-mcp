# Spec: phase-29-ptz-zoom

## Original task statement
Close the pending TelemetryService.Zoom method. The `zoom` tool already exists in
tools/axxon_mcp_ptz.py (a `_common` wrapper over the Zoom RPC), but Zoom was never
live-exercised, so the corpus marks it pending. Live-verify Zoom reversibly through
the shipped tool and restamp it tested-pass.

Probe results (live, <demo-host>, source hosts/Server/DeviceIpint.53/TelemetryControl.0):
- The stand has a responsive simulated PTZ source. AcquireSessionId, GetPosition, and
  AbsoluteMove all return ok.
- Zoom(mode="continuous") -> server error 2 (rejected). Zoom(mode="absolute", value=0.4)
  -> ok. The device ACKs the absolute Zoom command (proving the RPC path end-to-end) but
  its optics are virtual, so reported zoom does not change.
- Full reversible sequence verified: capture position -> Zoom(absolute,0.4)=ok ->
  AbsoluteMove restore to captured -> final position equals captured exactly. The device
  is intermittently busy (error 1) on rapid commands; a small retry handles it and
  ReleaseSessionId failing is harmless (session auto-expires).

## Acceptance criteria

- AC1: A focused regression test in tools/tests/test_axxon_mcp_ptz.py pins the Zoom
  call contract: zoom(...) with mode="absolute" returns status ok and emits exactly one
  Zoom RPC with the absolute capability flag set (is_absolute=True), and the request
  carries the access_point, session_id, and value. (The device-accepted mode is
  absolute; continuous is rejected on this stand.)
- AC2: A reversible-pattern test asserting the capture -> zoom -> AbsoluteMove restore
  sequence drives a Zoom then an AbsoluteMove back to the captured pan/tilt/zoom, using
  the existing fakes (no new tool code). No mutation leaks: bad mode still refused.
- AC3: No production code change to the zoom path is required (it already works);
  if any change is made it is the smallest safe one. The zoom tool stays read-mode-safe
  in the sense that the phase only adds tests + restamp; the tool itself is a control op
  that the operator invokes explicitly.
- AC4: Full suite `python3.12 -m unittest discover -s tools/tests` stays green.
- AC5: Corpus restamp `("TelemetryService","Zoom") -> tested-pass`; restamp dry-run
  reports 0 after --write. Coverage doc updated (count + new item). Live verify through
  the shipped tool recorded under raw/live-verify.txt.

## Constraints
- Reversible against the live stand: every Zoom is bracketed by capturing the position
  and restoring it via AbsoluteMove (already tested-pass).
- Reuse the existing ptz module + test fakes; do not duplicate the _common path.
- Honest evidence: Zoom is passed because the server accepted and executed the command
  (status ok), restored reversibly. The simulated optics not physically moving is noted,
  not hidden.

## Non-goals
- Focus/Iris/AbsoluteMoveNormalized/PointMove/AreaZoom and all preset/tour pending
  methods (separate phases).
- Making continuous-mode Zoom work (the stand's simulated source rejects it; absolute is
  the supported mode here).

## Verification plan
- Build: pyimport smoke (server + ptz import clean)
- Unit tests: focused absolute-mode Zoom contract + reversible-pattern test
- Integration tests: full suite discover
- Lint: n/a (repo convention)
- Manual checks: live capture -> Zoom(absolute,0.4)=ok -> AbsoluteMove restore -> exact
  position match; restamp dry-run == 0 after write
