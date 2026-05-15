# Axxon One Arm State Smoke

- Started: `2026-05-07T11:58:02.011569+00:00`
- Finished: `2026-05-07T11:58:09.244919+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Creates a temporary virtual camera, calls `LogicService.ChangeArmState` with a short timeout, then removes the camera.

## Summary

- PASS: 1
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `armstate_lifecycle` | 6316 | camera=hosts/Server/DeviceIpint.9802 timeout=2 arm_keys=[] remove_keys=['added', 'added_macros', 'failed', 'failed_reason', 'removed_macros'] |
