# MCP Generation Runtime Smoke

_run at 2026-05-16T09:30:02Z_

| template | status | exit | elapsed_s |
| --- | --- | --- | --- |
| grpc_consumer | ok | 0 | 3.2 |
| http_grpc_consumer | ok | 0 | 1.06 |
| legacy_http_consumer | ok | 0 | 0.98 |
| event_consumer | ok | 0 | 1.76 |
| external_event_producer | ok | 0 | 1.76 |
| export_job | ok | 0 | 1.95 |
| webhook_bridge | ok | 0 | 1.87 |
| inventory_sync | ok | 0 | 2.09 |

## Output detail (sanitized)

### grpc_consumer

stdout:
```
{"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits", "preview_chars": 849}
```

stderr:
```
2026-05-16 12:29:47,851 INFO axxon-one-mcp generated grpc_consumer
2026-05-16 12:29:47,851 INFO target=<demo-host> method=axxonsoft.bl.config.ConfigurationService.ListUnits
2026-05-16 12:29:47,851 INFO user=root password=ro*** tls_cn=<your-tls-cn>
2026-05-16 12:29:51,008 INFO response_chars=849
```

### http_grpc_consumer

stdout:
```
{"fqmn": "axxonsoft.bl.config.ConfigurationService.ListUnits", "status": 200, "bytes": 2101}
```

stderr:
```
2026-05-16 12:29:51,161 INFO user=root password=ro*** base=http://<demo-host>
2026-05-16 12:29:52,067 INFO status=200 bytes=2101
```

### legacy_http_consumer

stdout:
```
{"path": "/v1/security/checklogin", "status": 200, "bytes": 24}
```

stderr:
```
2026-05-16 12:29:52,206 INFO user=root password=ro*** base=http://<demo-host> path=/v1/security/checklogin
2026-05-16 12:29:53,037 INFO status=200 bytes=24
```

### event_consumer

stdout:
```
{"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "received": 0, "duration_cap": 10, "count_cap": 20}
```

stderr:
```
2026-05-16 12:29:53,198 INFO user=root password=ro*** host=<demo-host> subject=hosts/Server/AppDataDetector.27/EventSupplier
```

### external_event_producer

stdout:
```
{"access_point": "hosts/Server/DetectorEx.1/EventSupplier", "event_type": "Event1", "status": 200}
```

stderr:
```
2026-05-16 12:29:54,942 INFO user=root password=ro*** base=http://<demo-host> ap=hosts/Server/DetectorEx.1/EventSupplier type=Event1
2026-05-16 12:29:56,571 INFO raise status=200 bytes=14
```

### export_job

stdout:
```
{"camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "sessions_inspected": 0, "bytes_seen": 0}
```

stderr:
```
2026-05-16 12:29:56,690 INFO user=root password=ro*** host=<demo-host> camera=hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0 window=3600s
```

### webhook_bridge

stdout:
```
{"subject": "hosts/Server/AppDataDetector.27/EventSupplier", "forwarded": 0, "failed": 0, "duration_cap": 10, "count_cap": 20}
```

stderr:
```
2026-05-16 12:29:58,703 INFO user=root password=ro*** host=<demo-host> subject=hosts/Server/AppDataDetector.27/EventSupplier webhook_host=<demo-host>
```

### inventory_sync

stdout:
```
{"output": "/var/folders/_5/44bp9mmd7r7gf2q9vj6gzpxw0000gn/T/tmpjzdw05e7/inventory.json", "cameras": 38, "units": 1, "bytes": 28440}
```

stderr:
```
2026-05-16 12:30:00,527 INFO user=root password=ro*** host=<demo-host> output=/var/folders/_5/44bp9mmd7r7gf2q9vj6gzpxw0000gn/T/tmpjzdw05e7/inventory.json
```
