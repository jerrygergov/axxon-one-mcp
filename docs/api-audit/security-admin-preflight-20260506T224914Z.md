# Axxon One Security Admin Preflight

- Started: `2026-05-06T22:49:14.822791+00:00`
- Finished: `2026-05-06T22:49:18.826936+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`
- Node: `Server`

Read-only preflight for security administration mutations. It does not create users, change passwords, edit roles, change permissions, start LDAP synchronization, or change policy/IP filters.

## Summary

- PASS: 3
- WARN: 1
- FAIL: 1

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `security_inventory` | 388 | roles=4 users=35 ldap_servers=0 assignments=35 |
| FAIL | `security_policies` | 370 | <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Can't get connection channel!"
	debug_error_string = "UNKNOWN:Error received from peer ipv4:<demo-host>:20109 {grpc_status:14 |
| PASS | `security_permissions` | 646 | global_roles=1 object_items=36 group_items=1 macros=16 |
| PASS | `restricted_config` | 151 | keys=6 |
| WARN | `approval_only_mutations` | 0 | SecurityService.ChangeConfig, SecurityService.SetGlobalPermissions, SecurityService.SetObjectPermissions, SecurityService.SetGroupsPermissions, SecurityService.SetMacrosPermissions, SecurityService.StartLDAPSynchronizati |
