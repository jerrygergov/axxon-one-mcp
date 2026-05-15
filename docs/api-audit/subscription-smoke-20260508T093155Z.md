# Axxon One Subscription Smoke

- Started: `2026-05-08T09:31:55.463610+00:00`
- Finished: `2026-05-08T09:31:58.681664+00:00`
- HTTP target: `http://<demo-host>:80`
- gRPC target: `<demo-host>:20109`

## Summary

- PASS: 0
- WARN: 2
- SKIP: 0
- FAIL: 0

## Results

| Status | Mode | ms | Notes |
| --- | --- | ---: | --- |
| WARN | `websocket_camera_events` | 399 | Connection to remote host was lost.; stage=receive; schema=proto |
| WARN | `websocket_camera_track` | 518 | Connection to remote host was lost.; stage=receive; schema=proto |
