# Axxon One Archive Search Smoke

- Started: `2026-05-03T09:36:40.065924+00:00`
- Finished: `2026-05-03T09:36:59.057672+00:00`
- gRPC target: `<demo-host>:20109`

## Summary

- PASS: 2
- WARN: 3
- SKIP: 2
- FAIL: 0

## Results

| Status | Mode | ms | Notes |
| --- | --- | ---: | --- |
| PASS | `lpr` | 679 | items=0 |
| SKIP | `face` | 0 | missing --face-image fixture |
| PASS | `vmda` | 116 | items=1 |
| WARN | `heatmap` | 412 | <_MultiThreadedRendezvous of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: user exception, ID 'IDL:ovsoft.ru/vmda/InvalidQuery:1.0'"
	debug_e |
| SKIP | `stranger` | 0 | missing --face-image fixture |
| WARN | `legacy_vmda` | 7680 | items=0 |
| WARN | `legacy_heatmap` | 7864 | items=0 |
