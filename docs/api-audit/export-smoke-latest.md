# Axxon One Export Smoke

- Started: `2026-05-11T08:08:09.943229+00:00`
- Finished: `2026-05-11T08:08:19.892996+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Starts only temporary `codex-*` export sessions and destroys every session it creates.

## Summary

- PASS: 2
- WARN: 0
- FAIL: 0

## Fixtures

- camera_ap: `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`
- archive_ap: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`
- export_agent_ap: `hosts/Server/MMExportAgent.0`
- archive_timestamp: `20260511T080814.064000`

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `snapshot_export_lifecycle` | 4736 | state=S_COMPLETED files=1 first_size=70817 downloaded=70817 destroyed=True |
| PASS | `stop_running_session_lifecycle` | 1148 | running_state=S_RUNNING stopped_shape={'session_state': {'type': 'object', 'keys': 3}} destroyed=True |
