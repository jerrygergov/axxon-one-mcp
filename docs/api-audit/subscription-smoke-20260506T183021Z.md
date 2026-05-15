# Axxon One Subscription Smoke

- Started: `2026-05-06T18:30:21.680297+00:00`
- Finished: `2026-05-06T18:30:25.608224+00:00`
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
| WARN | `websocket_camera_events` | 375 | Connection to remote host was lost.; stage=receive; schema= |
| WARN | `websocket_camera_track` | 401 | Connection to remote host was lost.; stage=receive; schema= |
| PASS | `grpc_event_subscription` | 1174 | events=24 |
