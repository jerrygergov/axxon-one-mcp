# Axxon One Arm State Smoke

- Started: `2026-05-07T11:56:04.604802+00:00`
- Finished: `2026-05-07T11:56:10.471641+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary virtual camera, calls `LogicService.ChangeArmState` with a short timeout, then removes the camera.

## Summary

- PASS: 0
- WARN: 0
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| FAIL | `armstate_lifecycle` | 4560 | Enum ECameraArmState has no value defined for name 'ARMED' |
