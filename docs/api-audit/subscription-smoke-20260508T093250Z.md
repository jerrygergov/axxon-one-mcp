# Axxon One Subscription Smoke

- Started: `2026-05-08T09:32:50.288228+00:00`
- Finished: `2026-05-08T09:32:54.752214+00:00`
- HTTP target: `http://<demo-host>:80`
- gRPC target: `<demo-host>:20109`

## Summary

- PASS: 1
- WARN: 2
- SKIP: 0
- FAIL: 0

## Results

| Status | Mode | ms | Notes |
| --- | --- | ---: | --- |
| WARN | `websocket_camera_events` | 487 | Connection to remote host was lost.; stage=receive; schema=proto |
| WARN | `websocket_camera_track` | 412 | Connection to remote host was lost.; stage=receive; schema=proto |
| PASS | `grpc_event_subscription` | 1283 | events=20 |
