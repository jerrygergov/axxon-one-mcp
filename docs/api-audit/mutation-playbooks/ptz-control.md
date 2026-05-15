# Mutation Playbook: PTZ Control

- PDF pages: 80-87, 487-488.
- APIs involved: telemetry sessions, move/zoom/focus/iris, presets, tours, Tag&Track PTZ mode.
- Fixture requirements: non-production PTZ-capable camera, known home preset, operator approval.
- Preflight read snapshot: telemetry availability, position, preset list, current session list.
- Mutation request: acquire session and perform the smallest approved movement or preset action.
- Verification command: read telemetry position/session state.
- Rollback request: return to home preset or saved absolute position, then release session.
- Post-rollback verification: position and session state match expected baseline.
- Read-only preflight result: `ptz-preflight-latest.md` found zero telemetry/PTZ access points and zero control panels on the demo stand, so telemetry position/preset/operation/tour reads and Tag&Track tracker reads were skipped.
- Approval-only operations: telemetry session acquisition/release, move/zoom/focus/iris, absolute move, point/area move, presets, tours, auxiliary operations, and Tag&Track mode/follow/move calls are intentionally not executed without a non-production PTZ fixture.
- Risk level: high.
- Approval requirement: explicit physical-camera movement approval.
