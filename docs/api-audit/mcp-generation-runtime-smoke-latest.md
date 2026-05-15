# MCP Generation Runtime Smoke

_run at 2026-05-15T18:08:12Z_

| template | status | exit | elapsed_s |
| --- | --- | --- | --- |
| grpc_consumer | ok | 0 | 2.46 |
| http_grpc_consumer | ok | 0 | 1.41 |
| legacy_http_consumer | ok | 0 | 1.27 |
| event_consumer | ok | 0 | 2.32 |
| external_event_producer | ok | 0 | 2.05 |
| export_job | ok | 0 | 2.11 |

## Output detail (sanitized)

### grpc_consumer

stdout:
```
{"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits", "preview_chars": 849}
```

stderr:
```
2026-05-15 21:08:01,128 INFO axxon-one-mcp generated grpc_consumer
2026-05-15 21:08:01,128 INFO target=<demo-host> method=axxonsoft.bl.config.ConfigurationService.ListUnits
2026-05-15 21:08:01,128 INFO user=root password=ro*** tls_cn=<your-tls-cn>
2026-05-15 21:08:03,539 INFO response_chars=849
```

### http_grpc_consumer

stdout:
```
{"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits", "status": 200, "bytes": 2101}
```

stderr:
```
2026-05-15 21:08:03,674 INFO user=root password=ro*** base=http://<demo-host>
2026-05-15 21:08:04,942 INFO status=200 bytes=2101
```

### legacy_http_consumer

stdout:
```
{"path": "/v1/security/checklogin", "status": 200, "bytes": 24}
```

stderr:
```
2026-05-15 21:08:05,082 INFO user=root password=ro*** base=http://<demo-host> path=/v1/security/checklogin
2026-05-15 21:08:06,221 INFO status=200 bytes=24
```

### event_consumer

stdout:
```
{"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "received": 0, "duration_cap": 10, "count_cap": 20}
```

stderr:
```
2026-05-15 21:08:06,328 INFO user=root password=ro*** host=<demo-host> subject=hosts/Server/AppDataDetector.27/EventSupplier
```

### external_event_producer

stdout:
```
{"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1", "status": 200}
```

stderr:
```
2026-05-15 21:08:08,682 INFO user=root password=ro*** base=http://<demo-host> ap=hosts/Server/DetectorEx.1/EventSupplier type=Event1
2026-05-15 21:08:10,603 INFO raise status=200 bytes=14
```

### export_job

stdout:
```
{"camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "sessions_inspected": 0, "bytes_seen": 0}
```

stderr:
```
2026-05-15 21:08:10,704 INFO user=root password=ro*** host=<demo-host> camera=hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0 window=3600s
```
