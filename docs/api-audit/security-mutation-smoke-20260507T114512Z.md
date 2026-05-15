# Axxon One Security Mutation Smoke

- Started: `2026-05-07T11:45:12.809436+00:00`
- Finished: `2026-05-07T11:45:19.339327+00:00`
- gRPC target: `<demo-host>:20109`

Controlled smoke for temporary `codex-*` security records. It does not store generated passwords in the report.

## Summary

- PASS: 0
- WARN: 0
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| FAIL | `security_user_role_lifecycle` | 4202 | <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INTERNAL
	details = "CORBA:Exception: user exception, ID 'IDL:ovsoft.ru/InfraServer/SecurityManager/SetConfigFailed:1.0'"
	debug_error_string = "UNKNOWN:Error received from peer ipv4:100.76.1 |
